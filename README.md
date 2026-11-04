# Design Intelligence System

A standalone, provider-backed design intelligence foundation for improving web, desktop, and mobile products. DIS coordinates specialist design capabilities, maintains project-scoped memory, applies permission gates, and evaluates evidence against a quality rubric. It has no dependency on KubeDock or any specific product.

## Current capabilities

- Design Director and six specialist roles: creative, UX, visual design, design systems, frontend planning, and visual QA.
- Optional LLM-backed specialist analysis and dynamic specialist selection.
- OpenAI-compatible provider support (OpenAI, Groq, Gemini, Mistral, OpenRouter, and compatible endpoints) plus Anthropic Messages API.
- Deterministic fallback when no provider is configured or a provider request fails.
- Structured JSON response parsing and Pydantic validation.
- Project-scoped SQLite memory, permission policy, quality rubric, and FastAPI API.
- Provider status endpoint exposes configuration metadata only; API keys are never returned.

> **Capability boundary:** DIS can inspect GitHub repositories read-only, inspect deployed public web URLs in Chromium, use configured multimodal models to interpret screenshots, optionally crawl a bounded set of same-origin routes, prepare constrained frontend patches, and create a GitHub pull request only after explicit approval. It does not yet execute a repository checkout or build an arbitrary repository in a managed preview sandbox; provide an existing deployed/preview URL. Native desktop/mobile screenshot and interaction automation and authenticated route journeys are not currently supported, although the platform adapter registry identifies the required runner type.

## Architecture

```mermaid
flowchart TD
  API[FastAPI] --> ORCH[Dynamic Orchestrator]
  ORCH --> PLAN[LLM Planner]
  PLAN --> SPECIALISTS[Selected Specialists]
  SPECIALISTS --> PROVIDER[Provider Adapter]
  PROVIDER --> MODELS[OpenAI-compatible / Anthropic]
  ORCH --> FALLBACK[Deterministic Fallback]
  ORCH --> DIR[Design Director]
  ORCH --> MEM[(Project Memory / SQLite)]
  ORCH --> Q[Evidence-aware Quality Evaluator]
  API --> PERM[Permission Policy]
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

DIS works without an API key in deterministic mode. To enable model-backed reasoning, edit `.env`:

```dotenv
DIS_LLM_PROVIDER=openai
DIS_LLM_API_KEY=your_api_key
DIS_LLM_MODEL=gpt-4o-mini
```

Supported provider values:
- `openai` — OpenAI API (default base URL: `https://api.openai.com/v1`)
- `anthropic` — Anthropic Messages API
- `mistral` — Mistral chat completions API (default base URL: `https://api.mistral.ai/v1`)
- `gemini` — Google Gemini through its OpenAI-compatible endpoint (default base URL: `https://generativelanguage.googleapis.com/v1beta/openai`)
- `groq`, `openrouter`, `openai-compatible` — other OpenAI-compatible chat completions APIs

Mistral and Gemini have built-in endpoint defaults. In browser Settings, each provider has its own session-scoped model ID, API key and optional endpoint profile; switching providers preserves the other profiles. The selected provider powers the existing DIS Design Director and specialist-agent team. For other compatible providers, set `DIS_LLM_BASE_URL` to the provider's OpenAI-compatible API base URL. Example for Groq:

```dotenv
DIS_LLM_PROVIDER=groq
DIS_LLM_BASE_URL=https://api.groq.com/openai/v1
DIS_LLM_API_KEY=your_api_key
DIS_LLM_MODEL=your-model-id
```

Keep `.env` out of version control. Never place API keys in source code, requests, or logs.

## Read-only GitHub repository inspection

DIS can now inspect a GitHub repository without cloning it or executing its code. The first adapter is intentionally read-only and framework-agnostic.

- Public repositories work without a GitHub token, subject to GitHub's anonymous API rate limit.
- For private repositories or higher API limits, set `DIS_GITHUB_TOKEN` in the server environment using a least-privilege token with repository Contents: read access.
- If a GitHub token or LLM API key is configured, also set `DIS_REPOSITORY_INSPECTION_API_KEY`. Requests must then include `X-DIS-API-Key`; the endpoint fails closed rather than exposing a configured GitHub token or allowing unauthenticated LLM usage.
- DIS inventories the repository tree, detects common stacks and framework signals, identifies likely entry points/routes/components/styles/design-system files, and reports declared test/lint/build commands.
- It samples a bounded number of files and limits bytes read. Likely embedded credentials are redacted before sampled text is sent to the configured LLM.
- Repository reports include platform adapter profiles. Web apps use the browser visual workflow; Electron can use a supplied renderer preview URL; React Native, Flutter, Swift and Qt are identified with explicit native-runner limitations.
- It never executes project code, installs dependencies, runs tests, or claims visual verification. The report includes limitations and explicit “not executed” labels.
- The endpoint accepts `owner/name` or a `https://github.com/owner/name` URL. An optional `ref` selects a branch, tag, or commit.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/repositories/inspect \
  -H 'Content-Type: application/json' \
  -H 'X-DIS-API-Key: your_shared_key' \
  -d '{"repository":"HareeshGT/KubeDock","include_file_samples":true}'
```

The response contains detected stacks/frameworks, entry points, route/page paths, component/style paths, design-system evidence, declared test commands, sampled-file evidence, an architecture summary, and limitations. It does not return source file contents.

## Browser-based visual inspection

The visual inspector accepts a public application URL (optionally linked to a GitHub repository/ref in the dashboard) and opens it in a headless Chromium browser at desktop (1440×1000), tablet (768×1024), and mobile (390×844) viewports. It returns viewport screenshots, page metadata, responsive overflow checks, and basic accessibility signals for image alternatives, accessible button/link names, form labels, and heading hierarchy.

- API: `POST /api/v1/visual/inspect` with JSON `{"url":"https://example.com","capture_screenshots":true,"analyze_with_vision":true}` to opt in to sending screenshots to the configured provider.
- Include `X-DIS-API-Key` when `DIS_REPOSITORY_INSPECTION_API_KEY` is configured.
- The target must be publicly reachable over HTTP(S). Localhost, private, loopback, link-local, and reserved IP targets are blocked, including redirects and browser subrequests.
- Browser inspection is read-only: it does not log in, submit forms, click controls, or modify the target.
- Screenshots are returned as base64 JPEGs in the response and are not persisted by the server.
- When the user explicitly enables AI screenshot analysis, screenshots are sent to the configured vision-capable provider. You can configure a separate vision model with `DIS_VISION_LLM_PROVIDER`, `DIS_VISION_LLM_API_KEY`, `DIS_VISION_LLM_MODEL` and `DIS_VISION_LLM_BASE_URL`. When any dedicated vision setting is supplied, DIS does not mix in text-provider credentials or endpoints; otherwise it reuses the complete `DIS_LLM_*` configuration for observations about visual hierarchy, spacing, typography, color and component consistency. Optional route exploration follows same-origin anchor links only, with a configurable hard limit. The score is heuristic, not a WCAG certification or objective design-quality guarantee.

## Visual comparison and approved code improvements

- `POST /api/v1/visual/compare` inspects baseline and candidate URLs at desktop, tablet and mobile sizes, calculates pixel similarity and changed-pixel ratios, and compares deterministic finding titles. Pixel similarity measures change, not quality.
- `POST /api/v1/improvements/propose` reads up to four existing UI source files from a GitHub branch (public repos can be read anonymously; private repos need `DIS_GITHUB_TOKEN`) and asks the configured model for replacement contents tied to supplied visual findings. It enforces source path and file-size limits, redacts likely credentials, signs the proposal and returns a reviewable unified diff. Proposing never writes to GitHub.
- `POST /api/v1/improvements/apply` requires a signed, unexpired proposal and explicit `approval: true`. It uses `DIS_GITHUB_WRITE_TOKEN` to create a separate branch, commit approved files and open a pull request. It never merges the pull request. Proposal signatures use a separate server-only `DIS_PROPOSAL_SIGNING_KEY`; do not reuse the dashboard API key.
- Configure `DIS_GITHUB_WRITE_TOKEN` with fine-grained repository permissions for **Contents: read/write** and **Pull requests: read/write**. Keep `DIS_GITHUB_TOKEN` read-only for inspection. Set a random, independent `DIS_PROPOSAL_SIGNING_KEY` on the server. Never expose any of these secrets to the browser.
- The dashboard requires explicit consent before selected source files and findings are sent to the configured LLM provider, then lets the user review the diff and check a separate approval box before the PR is created. The code proposal is limited to selected existing UI source files; it does not install dependencies, run the target repository, or deploy it.

## Browser dashboard

DIS includes a browser-based workspace served by the FastAPI application:

- Open `http://127.0.0.1:8000/` for the dashboard.
- **Overview** shows API health, provider mode, and recent inspections.
- **Repository inspector** accepts a GitHub URL or `owner/name`, with an optional branch/tag/commit ref.
- **Visual inspection** opens a public web URL in Chromium, captures desktop/tablet/mobile screenshots, optionally explores same-origin routes, and displays deterministic and multimodal design findings.
- **Visual comparison** compares two deployed versions and shows screenshot change metrics plus resolved/new findings.
- **UI improvement proposal** generates a bounded frontend patch for selected GitHub files, displays the diff, and opens a PR only after explicit approval.
- **Architecture report** displays detected stacks/frameworks, entry points, routes, components/styles, design-system signals, declared commands, sampled file evidence, and limitations.
- **Inspection history** is stored in the current browser's local storage. It can be cleared from the History page.
- Dashboard Settings accepts a request-scoped AI provider/model/API key, optional compatible API base URL, GitHub read token, GitHub write token, and optional shared DIS API key. Values are kept in this browser tab's `sessionStorage`, sent as request headers, and used for that request only; they are not stored in the DIS database or returned by any API.
- GitHub read tokens are used for private repository inspection and source retrieval. GitHub write tokens are used only by the explicitly approved branch/commit/PR operation. Prefer fine-grained tokens scoped to the target repository.
- Configure `DIS_REPOSITORY_INSPECTION_API_KEY` on the server and enter its value in Settings when using protected AI/repository/improvement endpoints. `DIS_PROPOSAL_SIGNING_KEY` remains server-only and is never supplied from the browser.
- Browser-stored credentials are accessible to scripts running in the same origin. Use HTTPS, trusted dependencies, avoid shared devices, and clear settings when finished. Multi-user public hosting requires authenticated user accounts and an encrypted per-user credential vault; these settings are per-browser-session, not account identity.

The dashboard and API are served from the same origin; no separate frontend build or Node.js installation is required.


## Deploy on Render with Docker

Create a **Web Service** from this repository and select **Docker** as the runtime (Render can build directly from the included `Dockerfile`). Use these settings:

- Dockerfile path: `./Dockerfile`
- Docker build context: `.`
- Health check path: `/health`
- Do not set a fixed port in the Render dashboard. The container reads Render's injected `PORT` value and binds Uvicorn to `0.0.0.0:$PORT` (falling back to `8000` for local Docker).
- Add a persistent disk mounted at `/data` if you need SQLite project memory to survive deploys/restarts. Set `DIS_DATABASE_PATH=/data/design_intelligence.db`. Render persistent disks require a paid service plan and are not shared between multiple instances.
- Set `DIS_REPOSITORY_INSPECTION_API_KEY` and `DIS_PROPOSAL_SIGNING_KEY` as Render environment variables. Use independent, high-entropy secrets; never commit them to the repository. The dashboard prompts for the matching API key in Settings.
- Add provider and GitHub credentials only where needed. Prefer entering user-owned model/GitHub credentials in the browser Settings rather than baking secrets into the image.

The Docker image installs Chromium and its OS dependencies at build time for the visual-inspection endpoint. The image is therefore larger and its first build takes longer than a basic FastAPI image. Render's health check calls `/health`; a healthy container does not imply that an external model API key has been configured.

For local Compose, `PORT=8000` is set explicitly and the host port remains configurable with `DIS_PORT`. The Dockerfile's runtime port handling is shared by local Docker and Render.

## Docker

Copy the example environment file, configure optional provider/GitHub credentials, and start DIS:

```bash
cp .env.example .env
# Edit .env; set DIS_REPOSITORY_INSPECTION_API_KEY when using an LLM key or GitHub token.
docker compose up --build -d
```

Then open `http://localhost:8000/`. Compose persists SQLite project memory in the named Docker volume `dis-data`.

Useful commands:

```bash
docker compose logs -f dis
docker compose ps
docker compose down
```

To build and run without Compose:

```bash
docker build -t design-intelligence-system .
docker run --rm -p 8000:8000 --env-file .env -v dis-data:/data design-intelligence-system
```

The container runs as a non-root user, includes a health check, and stores SQLite under `/data`. Keep `.env` private and never bake secrets into the Docker image.

## Render deployment

This repository includes a Render Blueprint in `render.yaml` and deploys the same Docker image used by local Compose.

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint**, connect this repository, and deploy the detected `render.yaml`.
3. Render supplies the `PORT` environment variable. The Docker entrypoint and container health check both honor it; local Compose explicitly sets `PORT=8000`.
4. After deployment, open the service's **Environment** settings and copy the generated `DIS_REPOSITORY_INSPECTION_API_KEY` value into the dashboard's **Shared DIS API key** setting. Keep `DIS_PROPOSAL_SIGNING_KEY` server-side; never put it in browser settings.

The Blueprint uses Render's free web-service plan and does not attach a persistent disk. Its filesystem (including the SQLite database under `/data`) is ephemeral, so project memory and stored data can be lost when the service restarts or redeploys. For persistent SQLite data, move the service to a paid Render instance and attach a persistent disk mounted at `/data`; keep `DIS_DATABASE_PATH=/data/design_intelligence.db`.

The image installs Chromium for browser-based visual inspection. The service can start on the free plan, but Chromium inspections are memory-intensive; use an instance with sufficient memory for production visual-inspection workloads. Render deployment and browser inspection should be verified after the first deploy using `GET /health` and a real visual-inspection request.

## API

- `GET /` — browser dashboard
- `GET /health` — service health
- `GET /api/v1/agents` — registered roles
- `GET /api/v1/provider` — safe provider configuration status (never returns the key)
- `POST /api/v1/design/runs` — dynamically select specialists and orchestrate a design brief
- `POST /api/v1/visual/inspect` — capture and audit a public web page at three viewport sizes
- `POST /api/v1/visual/compare` — compare before/after screenshots and deterministic findings
- `POST /api/v1/improvements/propose` — generate a signed, reviewable frontend patch proposal
- `POST /api/v1/improvements/apply` — create a PR from an approved proposal
- `POST /api/v1/permissions/evaluate` — evaluate an action against autonomy policy

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/design/runs \
  -H 'Content-Type: application/json' \
  -d '{"brief":"Design a premium analytics dashboard","constraints":["WCAG AA","mobile first"]}'
```

## Development and tests

```bash
pip install -e '.[dev]'
pytest -q
ruff check . --select E4,E7,E9,F
```

## Autonomy and safety

Routine analysis and design planning are autonomous. Destructive, external, publishing, deployment, permission-changing, and merge actions require explicit approval. Secret exfiltration and disabling security controls are prohibited. Provider errors fall back to deterministic analysis rather than taking down the API. Provider output is treated as untrusted data and is constrained to structured result fields. The permission policy is not a substitute for authorization checks in future execution adapters.

## Roadmap

1. **Foundation:** registry, orchestration, project memory, permission policy, quality rubric, API.
2. **Provider-backed reasoning (current):** configurable provider adapter, dynamic specialist selection, structured outputs, deterministic fallback.
3. **Product adapters (in progress):** GitHub repository discovery is available in read-only mode; deepen framework-aware context and design-system ingestion.
4. **Controlled execution:** patch proposals, sandboxed commands, approval workflow, browser automation.
5. **Visual feedback loop:** viewport screenshots, visual issue detection, repair proposals, regression comparison.
6. **Learning and operations:** reference library, project design memory, run tracing, observability, evaluation datasets.
