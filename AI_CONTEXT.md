# AI Context & Handoff Document

## Project Identity & Purpose
- **Project Name:** MyApp
- **Purpose:** A persistent, AI-provider-independent coding workspace designed to maintain continuous context across different AI sessions, models, and coding agents via version-controlled project documentation and Git history.

## Current Project Status
- **Phase:** Project Infrastructure Initialization
- **Status:** Active
- **Active Focus:** Establishing robust project context infrastructure and documentation standards prior to application design or implementation.

## Current Active Task
- Initialize core project documentation (`AI_CONTEXT.md`, `ARCHITECTURE.md`, `TODO.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`) and `.gitignore`.

## Technology Stack
- **Languages:** Not yet defined
- **Frameworks:** Not yet defined
- **Databases/Storage:** Not yet defined
- **Testing Tools:** Not yet defined

## Project Structure
```text
MyApp/
├── .git/
├── .gitignore
├── AI_CONTEXT.md
├── ARCHITECTURE.md
├── CHANGELOG.md
├── DECISIONS.md
├── README.md
└── TODO.md
```

## Important Files
- `AI_CONTEXT.md`: Primary persistent handoff document and AI agent guidelines.
- `ARCHITECTURE.md`: High-level system design and architectural decisions.
- `TODO.md`: Task tracking, backlog, and milestones.
- `DECISIONS.md`: Architecture Decision Records (ADRs).
- `CHANGELOG.md`: Chronological record of changes and releases.
- `README.md`: High-level project overview and instructions.

## Coding Conventions
- **General:** Not yet defined.
- **Documentation:** Keep documentation synchronized with code changes and Git history.

## Current Known Issues / Blockers
- None.

## Important Instructions for AI Agents
1. **Source of Truth:** Project documentation and Git history are the absolute source of truth. Do not rely on conversational memory.
2. **Session Initialization:** At the start of every session or when switching AI providers, read `AI_CONTEXT.md`, `ARCHITECTURE.md`, and `TODO.md` first.
3. **Task Completion:** Update relevant documentation (`AI_CONTEXT.md`, `TODO.md`, `CHANGELOG.md`) whenever a feature, refactoring task, or milestone is completed.
4. **No Assumptions:** If requirements or technology choices are unspecified, mark them as "Not yet defined" or clarify with the user.

## Last Updated
- **Date:** August 19, 2026
- **Updated By:** AI Agent (Initialization)
