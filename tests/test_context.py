from app.services.container import get_context_service


def test_refresh_context_has_required_fields() -> None:
    snap = get_context_service().refresh_context()
    required = [
        "context_id",
        "created_at",
        "os_info",
        "shell_info",
        "detected_binaries",
        "detected_versions",
        "detected_scripts",
        "detected_repos",
        "google_context",
        "available_tools",
        "unavailable_tools",
    ]
    for key in required:
        assert key in snap
