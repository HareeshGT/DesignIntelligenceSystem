from __future__ import annotations

import base64
import os
import re
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.core.repository_models import RepositoryFileEvidence, RepositoryInspection
from app.services.llm import LLMProvider, ProviderError
from app.services.platform_adapters import resolve_platform_profiles


API_ROOT = "https://api.github.com"
MAX_TREE_ENTRIES = 20_000
MAX_FILES_TO_READ = 24
MAX_FILE_BYTES = 32_000
MAX_TOTAL_BYTES = 240_000
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|client[_-]?secret|password|secret)\s*([:=])\s*['\"`]?([A-Za-z0-9_./+=:-]{12,})"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
]
SKIP_PARTS = {
    ".git", ".next", ".nuxt", ".venv", "venv", "node_modules", "dist",
    "build", "coverage", "vendor", "__pycache__", "target",
}
SENSITIVE_NAMES = {
    ".env", ".env.local", ".env.production", "id_rsa", "id_ed25519",
    "credentials", "secrets.yaml", "secrets.yml",
}
PRIORITY_NAMES = {
    "readme.md", "package.json", "pyproject.toml", "requirements.txt",
    "pom.xml", "build.gradle", "cargo.toml", "go.mod", "pubspec.yaml",
    "composer.json", "vite.config.ts", "vite.config.js", "next.config.js",
    "next.config.mjs", "next.config.ts", "angular.json", "nuxt.config.ts",
    "tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs",
    "components.json", "tsconfig.json", "pytest.ini",
}
SOURCE_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss", ".less", ".py", ".qss"}
WEB_UI_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss", ".less", ".qss"}
PYTHON_UI_TOKENS = ("ui", "view", "window", "widget", "dialog", "tab", "theme", "static_content")


class RepositoryInspectionError(RuntimeError):
    """Safe, user-facing error while inspecting a repository."""


def _redact_text(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _parse_repository(value: str) -> tuple[str, str]:
    raw = value.strip()
    if raw.startswith(("https://", "http://")):
        parsed = urlparse(raw)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            raise RepositoryInspectionError("Only github.com repository URLs are supported.")
        raw = parsed.path.strip("/")
        if raw.endswith(".git"):
            raw = raw[:-4]
    parts = raw.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise RepositoryInspectionError("Use a GitHub URL or owner/name repository identifier.")
    if parts[0] in {".", ".."} or parts[1] in {".", ".."}:
        raise RepositoryInspectionError("Invalid repository identifier.")
    return parts[0], parts[1]


def _safe_path(path: str) -> bool:
    parts = path.split("/")
    if any(part in {"", ".", ".."} or part.lower() in SKIP_PARTS for part in parts):
        return False
    lowered = path.lower()
    if any(part.lower() in SENSITIVE_NAMES or part.lower().startswith(".env.") for part in parts):
        return False
    if lowered.endswith((".pem", ".key", ".p12", ".pfx", ".keystore", ".jks")):
        return False
    return True


def _category(path: str) -> str:
    name = path.rsplit("/", 1)[-1].lower()
    suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if name in PRIORITY_NAMES:
        return "manifest"
    if any(token in path.lower() for token in ("route", "pages/", "app/")):
        return "route_or_entry"
    if any(token in path.lower() for token in ("component", "widget", "layout")):
        return "component"
    if suffix in {".css", ".scss", ".less", ".qss"}:
        return "style"
    if suffix in SOURCE_SUFFIXES:
        return "source"
    return "config"


class GitHubRepositoryInspector:
    """Read-only repository inventory. It never checks out or executes repository code."""

    def __init__(self, llm: LLMProvider | None = None, timeout: float = 15.0, token: str | None = None):
        self.llm = llm
        self.timeout = timeout
        self.token = (token if token is not None else os.getenv("DIS_GITHUB_TOKEN", "")).strip()

    def _request(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Design-Intelligence-System",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise RepositoryInspectionError("Could not reach the GitHub API.") from exc
        if response.status_code == 404:
            raise RepositoryInspectionError(
                "Repository or ref was not found, or it is private and DIS_GITHUB_TOKEN lacks access."
            )
        if response.status_code == 401:
            raise RepositoryInspectionError("GitHub rejected DIS_GITHUB_TOKEN.")
        if response.status_code == 403:
            raise RepositoryInspectionError(
                "GitHub denied the request or rate limit was reached. Configure a least-privilege token."
            )
        if response.status_code >= 400:
            raise RepositoryInspectionError(f"GitHub API returned HTTP {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise RepositoryInspectionError("GitHub returned an invalid JSON response.") from exc
        if not isinstance(data, dict):
            raise RepositoryInspectionError("GitHub returned an unexpected response.")
        return data

    def inspect(self, repository: str, ref: str | None = None, include_file_samples: bool = True) -> RepositoryInspection:
        owner, name = _parse_repository(repository)
        base = f"{API_ROOT}/repos/{owner}/{name}"
        metadata = self._request(base)
        resolved_ref = ref or metadata.get("default_branch") or "main"
        branch_data = self._request(f"{base}/git/trees/{quote(resolved_ref, safe='')}", {"recursive": "1"})
        entries = branch_data.get("tree", [])
        if not isinstance(entries, list):
            raise RepositoryInspectionError("GitHub returned an invalid repository tree.")
        if len(entries) > MAX_TREE_ENTRIES:
            raise RepositoryInspectionError(
                f"Repository tree has more than {MAX_TREE_ENTRIES} entries; inspection was stopped."
            )
        files = [
            item for item in entries
            if item.get("type") == "blob" and isinstance(item.get("path"), str)
            and _safe_path(item["path"])
        ]
        files.sort(key=self._priority)
        selected = files[:MAX_FILES_TO_READ] if include_file_samples else []
        contents: dict[str, str] = {}
        evidence: list[RepositoryFileEvidence] = []
        total_bytes = 0
        for item in selected:
            path = item["path"]
            if total_bytes >= MAX_TOTAL_BYTES:
                break
            try:
                data = self._request(f"{base}/contents/{path}", {"ref": resolved_ref})
            except RepositoryInspectionError:
                continue
            if data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
                continue
            try:
                raw = base64.b64decode(data["content"], validate=False)
            except (ValueError, TypeError):
                continue
            remaining = min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total_bytes)
            clipped = raw[:remaining]
            total_bytes += len(clipped)
            text = clipped.decode("utf-8", errors="replace")
            # Redact likely embedded credentials before any model prompt is assembled.
            contents[path] = _redact_text(text)
            evidence.append(RepositoryFileEvidence(
                path=path, category=_category(path), bytes_read=len(clipped),
                truncated=len(raw) > len(clipped),
            ))

        stacks, managers, frameworks = self._detect_stack(files, contents)
        paths = [item["path"] for item in files]
        entry_points = self._entry_points(paths)
        route_files = [p for p in paths if self._is_route(p)][:40]
        component_files = [
            p for p in paths if self._is_component_or_style(p)
        ][:60]
        design_evidence = [
            p for p in paths
            if any(token in p.lower() for token in (
                "tokens", "theme", "design-system", "designsystem", "tailwind",
                "variables.css", "components.json",
            ))
        ][:30]
        commands = self._commands(contents)
        signals = [
            f"Repository tree contains {len(entries)} entries ({len(files)} eligible files).",
            f"Inspected {len(contents)} text files within bounded byte limits.",
            "Inspection is read-only; repository commands and application code were not executed.",
        ]
        summary = self._summary(owner + "/" + name, resolved_ref, stacks, frameworks,
                                entry_points, route_files, design_evidence, contents)
        limitations = [
            "Analysis covers repository metadata and a bounded sample of text files, not every file.",
            "Dependencies and framework detections are inferred from manifests and file paths.",
            "No build, test, browser, screenshot, or visual-regression command was executed.",
        ]
        if branch_data.get("truncated"):
            limitations.append("GitHub marked the recursive tree as truncated; file inventory may be incomplete.")
        return RepositoryInspection(
            repository=f"{owner}/{name}", ref=resolved_ref,
            default_branch=metadata.get("default_branch"),
            description=metadata.get("description"), primary_language=metadata.get("language"),
            detected_stacks=stacks, package_managers=managers, frameworks=frameworks,
            platform_profiles=resolve_platform_profiles(frameworks, stacks),
            app_entry_points=entry_points, route_and_page_files=route_files,
            component_and_style_files=component_files, design_system_evidence=design_evidence,
            test_and_lint_commands=commands, repository_signals=signals,
            file_evidence=evidence, architecture_summary=summary, limitations=limitations,
            inspected_file_count=len(contents), tree_entry_count=len(entries),
        )

    @staticmethod
    def _priority(item: dict[str, Any]) -> tuple[int, int, str]:
        path = item["path"]
        name = path.rsplit("/", 1)[-1].lower()
        if name in PRIORITY_NAMES or name in {"main.py", "main_window.py", "themes.py", "ui_kit.py", "static_content.py"}:
            score = 0
        elif name == "readme.md":
            score = 1
        elif any(part in path.lower() for part in ("src/", "app/", "pages/", "components/")):
            score = 2
        elif _category(path) in {"manifest", "route_or_entry", "component", "style"}:
            score = 3
        else:
            score = 4
        return score, path.count("/"), path.lower()

    @staticmethod
    def _detect_stack(files: list[dict[str, Any]], contents: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
        paths = [f["path"].lower() for f in files]
        stacks, managers, frameworks = [], [], []
        indicators = [
            ("JavaScript/TypeScript", ["package.json", "tsconfig.json", "vite.config", "next.config"]),
            ("Python", ["pyproject.toml", "requirements.txt", "setup.py", "pdm.lock", "poetry.lock"]),
            ("Java/JVM", ["pom.xml", "build.gradle", "build.gradle.kts"]),
            ("Go", ["go.mod"]),
            ("Rust", ["cargo.toml"]),
            ("PHP", ["composer.json"]),
            (".NET", [".csproj", ".sln"]),
            ("Ruby", ["gemfile"]),
        ]
        for label, markers in indicators:
            if any(any(p.endswith(marker) for marker in markers) for p in paths):
                stacks.append(label)
        if "pubspec.yaml" in contents and "flutter:" in contents["pubspec.yaml"].lower() and any(path.endswith(".dart") for path in paths):
            stacks.append("Dart/Flutter")
            frameworks.append("Flutter")
        if "package.json" in contents:
            managers.append("npm-compatible (package.json)")
            if "pnpm-lock.yaml" in paths:
                managers.append("pnpm")
            if "yarn.lock" in paths:
                managers.append("Yarn")
            if "bun.lock" in paths or "bun.lockb" in paths:
                managers.append("Bun")
        if "pyproject.toml" in contents or "requirements.txt" in contents:
            managers.append("pip/Python")
        if any(p.endswith(("pom.xml", "build.gradle", "build.gradle.kts")) for p in paths):
            managers.append("Maven/Gradle")
        if "package.json" in contents:
            package = contents["package.json"].lower()
            for token, label in [
                ('"next"', "Next.js"), ('"react"', "React"), ('"vite"', "Vite"),
                ('"vue"', "Vue"), ('"nuxt"', "Nuxt"), ('"svelte"', "Svelte"),
                ('"@angular/core"', "Angular"), ('"astro"', "Astro"),
                ('"tailwindcss"', "Tailwind CSS"), ('"react-native"', "React Native"),
                ('"electron"', "Electron"),
            ]:
                if token in package and label not in frameworks:
                    frameworks.append(label)
        swift_ui_evidence = any(
            marker in content.lower()
            for content in contents.values()
            for marker in ("import swiftui", "import uikit", "import appkit")
        )
        if swift_ui_evidence and any(p.endswith(".swift") for p in paths):
            frameworks.append("Swift / Apple platform")
        python_dependency_text = "\\n".join(
            contents.get(name, "") for name in ("pyproject.toml", "requirements.txt", "requirements-editor.txt")
        ).lower()
        for token, label in [
            ("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask"),
            ("pyside", "Qt desktop"), ("pyqt", "Qt desktop"),
        ]:
            if token in python_dependency_text and label not in frameworks:
                frameworks.append(label)
        python_ui_imports = "\\n".join(contents.values()).lower()
        if any(token in python_ui_imports for token in ("from tkinter", "import tkinter", "customtkinter")):
            if "Tkinter desktop" not in frameworks:
                frameworks.append("Tkinter desktop")
        return stacks, list(dict.fromkeys(managers)), list(dict.fromkeys(frameworks))

    @staticmethod
    def _entry_points(paths: list[str]) -> list[str]:
        names = {"main.tsx", "main.jsx", "main.ts", "main.js", "index.tsx", "index.jsx",
                 "index.ts", "index.js", "app.tsx", "app.jsx", "app.vue", "app.svelte",
                 "main.py", "manage.py", "application.java", "main.go", "main.dart"}
        return [p for p in paths if p.rsplit("/", 1)[-1].lower() in names][:40]

    @staticmethod
    def _is_route(path: str) -> bool:
        p = path.lower()
        name = p.rsplit("/", 1)[-1]
        return any(token in p for token in ("/routes/", "/pages/", "/app/")) or name in {
            "router.ts", "router.js", "routes.ts", "routes.js", "urls.py"
        }

    @staticmethod
    def _is_component_or_style(path: str) -> bool:
        p = path.lower()
        suffix = "." + p.rsplit(".", 1)[-1] if "." in p else ""
        python_ui_file = suffix == ".py" and any(token in p for token in PYTHON_UI_TOKENS)
        return suffix in WEB_UI_SUFFIXES or python_ui_file or "components/" in p or "design-system" in p

    @staticmethod
    def _commands(contents: dict[str, str]) -> list[str]:
        commands = []
        import json
        package = contents.get("package.json")
        if package:
            try:
                scripts = json.loads(package).get("scripts", {})
                for key in ("test", "lint", "typecheck", "build"):
                    if scripts.get(key):
                        commands.append(f"npm run {key} (declared; not executed)")
            except (ValueError, AttributeError):
                commands.append("package.json scripts could not be parsed")
        if "pyproject.toml" in contents:
            text = contents["pyproject.toml"].lower()
            if "pytest" in text:
                commands.append("pytest (declared/configured; not executed)")
            if "ruff" in text:
                commands.append("ruff check . (declared/configured; not executed)")
        return commands

    def _summary(self, repo: str, ref: str, stacks: list[str], frameworks: list[str],
                 entry_points: list[str], route_files: list[str], design_evidence: list[str],
                 contents: dict[str, str]) -> str:
        facts = [
            f"Repository {repo} at ref {ref}.",
            "Detected stacks: " + (", ".join(stacks) if stacks else "not confidently detected") + ".",
            "Framework signals: " + (", ".join(frameworks) if frameworks else "none confidently detected") + ".",
            "Entry points: " + (", ".join(entry_points[:8]) if entry_points else "not identified") + ".",
            "Route/page files: " + (", ".join(route_files[:10]) if route_files else "not identified") + ".",
            "Design-system evidence: " + (", ".join(design_evidence[:10]) if design_evidence else "not identified") + ".",
        ]
        deterministic = " ".join(facts)
        if self.llm and self.llm.enabled:
            try:
                output = self.llm.complete_json(
                    "You are a repository analyst. Summarize only evidence supplied. Distinguish facts "
                    "from inferences. Never claim to have executed code, tests, or visual checks. "
                    "Return JSON with one string field named summary.",
                    f"Inventory facts:\n{deterministic}\nSample file paths and bounded contents:\n"
                    + "\n".join(f"--- {path} ---\n{text[:2500]}" for path, text in list(contents.items())[:12]),
                )
                result = output.get("summary")
                if isinstance(result, str) and result.strip():
                    return result.strip()[:6000]
            except ProviderError:
                pass
        return deterministic
