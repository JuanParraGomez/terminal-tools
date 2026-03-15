from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="terminal-tools")
    app_env: str = Field(default="dev")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8090)

    data_dir: Path = Field(default=Path("./data"))
    logs_dir: Path = Field(default=Path("./data/logs"))
    db_path: Path = Field(default=Path("./data/terminal_tools.db"))
    context_dir: Path = Field(default=Path("./data/context"))
    context_ttl_seconds: int = Field(default=900)
    trash_dir: Path = Field(default=Path("/home/juan/Documents/terminal-tools/data/trash"))
    trash_ttl_days: int = Field(default=7)
    langgraph_agent_repo_root: Path = Field(default=Path("/home/juan/Documents/langgraph-agent-server"))
    langgraph_agent_repo_tests_dir: Path = Field(default=Path("/home/juan/Documents/langgraph-agent-server/tests"))
    langgraph_agent_repo_trash_dir: Path = Field(default=Path("/home/juan/Documents/langgraph-agent-server/data/trash"))

    default_timeout_seconds: int = Field(default=120)
    max_output_chars: int = Field(default=50000)

    allowed_workdirs: str = Field(default="/home/juan/Documents,/tmp")
    allowed_script_dirs: str = Field(default="/home/juan/Documents/scripts/backup,/home/juan/Documents/scripts/deploy,/home/juan/Documents/scripts/maintenance")

    copilot_bin: str = Field(default="copilot")
    codex_bin: str = Field(default="codex")
    claude_bin: str = Field(default="claude")
    gcloud_bin: str = Field(default="gcloud")
    gemini_cli_bin: str = Field(default="gemini")

    # Claude model profiles (primary tool for all AI tasks)
    claude_model_small: str = Field(default="claude-haiku-4-5")    # fast/cheap: quick fixes, small tasks
    claude_model_plan: str = Field(default="claude-sonnet-4-6")    # planning, architecture, complex tasks
    claude_model_code: str = Field(default="claude-sonnet-4-6")    # code execution, apply changes
    claude_model_review: str = Field(default="claude-haiku-4-5")   # review/validation (kept for compat)

    # Legacy copilot settings (kept for backward compat, unused)
    copilot_model_cheap_a: str = Field(default="claude-haiku-4-5")
    copilot_model_cheap_b: str = Field(default="claude-sonnet-4-6")
    copilot_model_plan: str = Field(default="claude-sonnet-4-6")
    copilot_cli_model_cheap_a: str | None = Field(default=None)
    copilot_cli_model_cheap_b: str | None = Field(default=None)
    copilot_cli_model_plan: str = Field(default="claude-sonnet-4-6")

    enable_gemini_cli: bool = Field(default=True)
    enable_gcloud: bool = Field(default=True)
    enable_codex: bool = Field(default=False)   # disabled: all code tasks route to claude
    enable_copilot: bool = Field(default=False)  # disabled: all tasks route to claude
    enable_claude: bool = Field(default=True)
    enable_langgraph_agent_server: bool = Field(default=True)

    langgraph_agent_server_base_url: str = Field(default="http://127.0.0.1:8070")
    langgraph_agent_server_mcp_url: str = Field(default="http://127.0.0.1:8070/mcp/tools")

    auto_refresh_context_on_stale: bool = Field(default=True)

    mcp_transport: str = Field(default="streamable-http")
    mcp_host: str = Field(default="127.0.0.1")
    mcp_port: int = Field(default=8091)

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def allowed_workdirs_list(self) -> list[Path]:
        return [Path(p.strip()).expanduser() for p in self.allowed_workdirs.split(",") if p.strip()]

    @property
    def allowed_script_dirs_list(self) -> list[Path]:
        return [Path(p.strip()).expanduser() for p in self.allowed_script_dirs.split(",") if p.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir = settings.data_dir.expanduser().resolve()
    settings.logs_dir = settings.logs_dir.expanduser().resolve()
    settings.db_path = settings.db_path.expanduser().resolve()
    settings.context_dir = settings.context_dir.expanduser().resolve()
    settings.trash_dir = settings.trash_dir.expanduser().resolve()
    settings.langgraph_agent_repo_root = settings.langgraph_agent_repo_root.expanduser().resolve()
    settings.langgraph_agent_repo_tests_dir = settings.langgraph_agent_repo_tests_dir.expanduser().resolve()
    settings.langgraph_agent_repo_trash_dir = settings.langgraph_agent_repo_trash_dir.expanduser().resolve()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.context_dir.mkdir(parents=True, exist_ok=True)
    settings.trash_dir.mkdir(parents=True, exist_ok=True)
    settings.langgraph_agent_repo_trash_dir.mkdir(parents=True, exist_ok=True)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
