# Repository and AI Implementation Audit

**Baseline:** `main` at `f61b366d3938e2af72140fdf31970b8a856c37d7`  
**Audit branch:** `audit/ai-and-repository-hardening`  
**Scope:** Static review of the repository tree, AI/provider adapters, orchestration and specialist agents, multimodal visual analysis, repository inspection and patch generation, API routes, browser inspection, browser UI wiring, project memory, configuration, tests and CI.

## Confirmed findings and remediation

| ID | Severity | Area | Finding | Disposition |
|---|---|---|---|---|
| AI-01 | High | Provider security | Anthropic text and image calls did not invoke the provider-host guard. An Anthropic profile configured with an OpenAI official endpoint could send its credential to the wrong provider host. | Fixed: validate provider host before either Anthropic request. Added regression tests for both paths. |
| AI-02 | Medium | Vision cost control | OpenAI-compatible image requests did not set an explicit output-token limit. | Fixed: cap image-response output at 2,400 tokens. Added a payload regression test. |
| AI-03 | Medium | Response parsing | Non-string chat message content could raise an unhandled `AttributeError` when the JSON parser called `.strip()`. | Fixed: reject non-text content as a controlled `ProviderError`. Added regression coverage. |
| AI-04 | Medium | Vision diagnostics | Vision HTTP status failures were collapsed into a generic provider error, hiding safe status/detail information. | Fixed: preserve HTTP status and a bounded, credential-redacted provider diagnostic; distinguish timeout and connectivity errors. |
| UI-01 | Medium | AI implementation workflow | Qt stylesheet files were not eligible for proposal discovery, despite repository inspection identifying them as UI assets. | Fixed: include `.qss` in allowed UI source files and stylesheet relevance scoring. Added regression test. |
| UI-02 | Medium | Studio integration | Automatic file suggestions in the visual and AI Studio workflows excluded Python and Qt stylesheet files. | Fixed: include `.py` and `.qss` in both UI-source filters. |
| SEC-01 | High / residual | Browser SSRF boundary | URL validation resolves a public hostname before Chromium connects, but the browser performs its own later DNS resolution. This leaves a DNS-rebinding/TOCTOU gap. | Partially mitigated: block WebSocket handshakes during inspection, since they are not covered by ordinary request routing. **Not fully fixed:** robust DNS pinning/network egress enforcement requires a network-level proxy or isolated browser runtime. |
 
## Design and implementation observations

- The specialist pipeline has six roles plus a director, validates planner-selected roles against an allowlist, passes prior specialist outputs downstream, and falls back to deterministic analysis on provider failures.
- Deterministic fallback is an intentional availability behavior; specialist outputs expose `model_generated` so fallback results can be distinguished.
- Quality evaluation correctly leaves categories unverified when no evidence-backed scores were supplied. It does not represent a release approval.
- Repository inspection is read-only and bounded; it does not execute untrusted repository code.
- Generated source proposals are bounded to selected files, signed server-side, and require explicit approval before GitHub writes. The proposal/apply path still depends on external GitHub permissions and should be tested against failure during a multi-file apply.
- Visual inspection is limited to public URLs and bounded viewports/routes. It is not a WCAG certification, authenticated journey test, or native desktop runner.
- Browser UI credentials are held in per-tab `sessionStorage`; project inspection history is held in browser `localStorage`.

## Verification boundary

The baseline GitHub Actions run on `main` was green at audit start. Changes on this branch require the pull-request workflow to complete before they can be called passing. No live model credentials, provider billing, deployed Render environment, private repository, or production browser-egress configuration was exercised as part of this static audit.
