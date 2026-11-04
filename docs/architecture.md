# Architecture decisions

## 1. Orchestration over independent chatbots

A single orchestrator owns task creation, dependencies, context propagation, run state, and final synthesis. Specialists have narrow responsibilities and return a shared `AgentResult` contract. This keeps handoffs inspectable and testable.

## 2. Sequential first-pass workflow

The initial workflow is deliberately sequential: creative direction → UX → visual language → design system → frontend plan → QA plan → director synthesis. Future versions can parallelize independent discovery tasks after dependency metadata and conflict resolution are in place.

## 3. Provider independence

Agent behavior is separated from transport and provider concerns. The next provider milestone should introduce an `LLMProvider` protocol and adapters, rather than binding the registry to a single vendor.

## 4. Evidence-based quality

Quality scores are only calculated for measured categories. Missing evidence remains unverified. Critical defects block the release gate independently of the weighted score.

## 5. Project-scoped memory

SQLite stores append-only project events. The first implementation keeps memory isolated by project ID and avoids storing credentials. A later migration can introduce retention policies, encryption, and a vector index for reference retrieval.

## 6. Execution safety

The current policy classifies action intent. Future execution tools must enforce authorization at the adapter boundary too, use least privilege, sandbox untrusted code, redact secrets, and require approval for consequential actions.
