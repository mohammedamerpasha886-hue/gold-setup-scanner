# Architecture Decision Records (ADRs)

This file records architectural, technical, and process decisions made for the project.

## ADR Template
```markdown
## ADR-[Number]: [Short Title]
- **Status:** [Proposed | Accepted | Rejected | Deprecated]
- **Date:** [YYYY-MM-DD]
- **Context:** [Context and problem statement]
- **Decision:** [The decision made]
- **Consequences:** [Positive and negative consequences]
```

---

## ADR-001: Project Documentation and Git as Persistent Source of Truth
- **Status:** Accepted
- **Date:** 2026-08-19
- **Context:** AI coding sessions can span different AI providers (e.g., Gemini, OpenRouter models) and chat sessions. Relying on conversational history risks context loss and fragmentation.
- **Decision:** Use local version-controlled project documentation (`AI_CONTEXT.md`, `ARCHITECTURE.md`, `TODO.md`, `DECISIONS.md`, `CHANGELOG.md`) and Git history as the absolute source of truth independent of any AI provider.
- **Consequences:** 
  - **Positive:** Seamless handoffs between any AI provider or coding agent; permanent, auditable project history; zero vendor lock-in for project context.
  - **Negative:** Requires discipline to update documentation files continuously during development.
