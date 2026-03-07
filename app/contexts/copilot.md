# Copilot Context

When to use:
- Small, focused code edits
- Quick explanation of a specific block
- Low-cost short generation
- Code planning when you want to stay on Copilot instead of escalating to a pricier planner

When NOT to use:
- Multi-repo architecture redesign
- Long iterative workflows

How to formulate:
- Include file path, exact scope, and acceptance check
- For planning, ask for impacted files, validation steps, rollback notes, and risks

Profiles:
- `copilot_cheap_a`: default low-cost code task
- `copilot_cheap_b`: slightly richer focused code task
- `copilot_plan`: code planning profile; plan only, no file edits

Output style:
- Minimal patch plan + concise rationale

Risks:
- Over-broad edits outside requested scope
