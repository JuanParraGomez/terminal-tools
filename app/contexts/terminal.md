# Terminal Context

Security baseline:
- Enforce command allowlist and denylist
- Restrict cwd and script paths
- Timeout + output limits + secret masking

Execution rules:
- Prefer argv lists, no shell freeform
- Avoid destructive mutations unless explicitly allowed

Operational guidance:
- Verify cwd
- Keep logs per task
- Return structured status and stderr/stdout summaries
