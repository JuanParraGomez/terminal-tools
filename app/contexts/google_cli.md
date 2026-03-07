# Google CLI Context

When to use:
- GCP projects/resources/auth/logs/deploy checks

Use safe flags:
- --quiet
- --format=json
- Filters for narrow scope

Separate read vs mutative:
- Informative commands default
- Mutative commands require explicit confirmation

Examples:
- gcloud projects list --format=json
- gcloud config get-value project --quiet
