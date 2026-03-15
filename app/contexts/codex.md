# Codex Context

When to use:
- Complex tasks requiring multi-step iteration
- Multi-file changes with validations

When NOT to use:
- Tiny one-line edits or read-only checks

How to formulate:
- End goal, boundaries, commands allowed for validation

Output style:
- Step-by-step execution report and resulting state

Risks:
- Large change sets; keep scope bounded

LangGraph baseline requirement:
- If creating or modifying LangGraph/LangChain agent services, include LangSmith tracing by default.
- Minimum expected env/config:
  - `LANGSMITH_ENABLED=true`
  - `LANGSMITH_API_KEY` (from environment, never hardcoded in source)
  - `LANGSMITH_PROJECT` (service-level project name)
  - `LANGSMITH_ENDPOINT=https://api.smith.langchain.com`
- Ensure startup/bootstrap wires tracing env so runtime executions are observable.
