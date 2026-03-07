# terminal-tools

`terminal-tools` es un servicio desacoplado para orquestar herramientas de terminal y agentes CLI con patrón:

`IA -> MCP -> API -> backend real`

Diseñado para integrarse con OpenClaw sin meter lógica pesada en OpenClaw core.

## Arquitectura V1
- FastAPI: API principal y contratos HTTP estables.
- FastMCP: tools MCP para agentes.
- Routing explícito: `app/routing/policy.yaml` + `app/routing/task_patterns.yaml`.
- Contexto determinista: discovery, snapshot en SQLite + JSON, render por herramienta.
- Seguridad: allowlist/denylist, validación de paths, timeouts, límites de salida, masking de secretos.
- Persistencia local: SQLite + logs por tarea (`data/logs`).
- Runner local: `subprocess` controlado (sin dependencia obligatoria de Celery/Redis).

## Herramientas soportadas
- `terminal` (comandos controlados)
- `copilot` (alias de modelos baratos configurables)
- `claude` (review/plan)
- `codex` (iteración larga)
- `gcloud`
- `gemini_cli` (opcional)

Si una herramienta no existe en host, aparece como `unavailable` y devuelve error claro.

## Routing Policy
Reglas principales implementadas:
- `target_environment=google` -> prioriza `gcloud` o `gemini_cli`.
- `needs_plan=true` o `needs_second_opinion=true` -> prioriza `claude`.
- `requires_iteration=true` o cambios complejos -> prioriza `codex`.
- cambios de código puntuales -> prioriza `copilot`.
- operaciones locales simples -> `terminal` controlado.

## Terminal Context (determinista)
Discovery controlado detecta:
- OS, shell
- workdirs/script dirs permitidos
- binarios y versiones
- scripts `.sh` permitidos
- repos git (branch + dirty)
- estado Google básico (gcloud instalado/auth/proyecto/cuenta)

Snapshot se guarda en:
- SQLite (`context_snapshots`)
- `data/context/current_context.json`

Endpoints:
- `GET /context`
- `POST /context/refresh`
- `GET /context/capabilities`
- `GET /context/scripts`
- `GET /context/repos`

Tools MCP equivalentes:
- `terminal_get_context`
- `terminal_refresh_context`
- `terminal_get_capabilities`
- `terminal_get_scripts`
- `terminal_get_repos`

## Seguridad
- Allowlist de comandos: `app/security/command_allowlist.yaml`
- Denylist y patrones peligrosos: `app/security/command_denylist.yaml`
- Política de rutas: `app/security/path_policy.yaml`
- CWD restringido a `ALLOWED_WORKDIRS`
- Scripts restringidos a `ALLOWED_SCRIPT_DIRS`
- Sin `shell=True` por defecto
- Timeout configurable
- Max output chars configurable
- Masking básico de secretos en logs/salida

### Política de rutas y permisos
Permisos soportados:
- `read_only`
- `read_write`
- `create_only`
- `scratch`
- `blocked`

Acciones controladas:
- `read`
- `write`
- `create_file`
- `create_dir`
- `delete`
- `execute`

Resolución de reglas:
1. coincidencia exacta más específica
2. patrón (`glob`) más específico
3. regla de workspace raíz
4. default global (`unknown_paths`)

Si hay duda, se prioriza la más restrictiva.

## API HTTP
- `GET /health`
- `GET /capabilities`
- `GET /profiles`
- `GET /context`
- `POST /context/refresh`
- `GET /context/capabilities`
- `GET /context/scripts`
- `GET /context/repos`
- `GET /path-policy`
- `GET /path-policy/effective?path=...`
- `POST /path-policy/check`
- `GET /trash`
- `POST /trash/create`
- `POST /trash/cleanup`
- `GET /trash/{task_id}`
- `POST /route`
- `POST /run`
- `POST /run/command`
- `POST /run/script`
- `POST /run/copilot`
- `POST /run/claude-review`
- `POST /run/codex`
- `POST /run/google-cli`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/logs`
- `GET /tasks`
- `POST /sessions`
- `GET /sessions/{session_id}`

## MCP Tools
- `terminal_health`
- `terminal_list_capabilities`
- `terminal_route_task`
- `terminal_get_context`
- `terminal_refresh_context`
- `terminal_get_capabilities`
- `terminal_get_scripts`
- `terminal_get_repos`
- `terminal_get_path_policy`
- `terminal_check_path_access`
- `terminal_get_trash_info`
- `terminal_create_trash_space`
- `terminal_cleanup_trash`
- `terminal_run_command`
- `terminal_run_script`
- `terminal_copilot_code_task`
- `terminal_claude_review_task`
- `terminal_codex_iterate_task`
- `terminal_google_cli_task`
- `terminal_get_task`
- `terminal_get_logs`

## Recetas
Estructuradas en:
- `app/recipes/google/`
- `app/recipes/terminal/`
- `app/recipes/git/`

## Instalación
```bash
cd /home/juan/Documents/terminal-tools
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp -n .env.example .env
```

## Correr API
```bash
cd /home/juan/Documents/terminal-tools
. .venv/bin/activate
./scripts/run_api.sh
```

## Correr MCP
```bash
cd /home/juan/Documents/terminal-tools
. .venv/bin/activate
./scripts/run_mcp.sh
```

## Tests
```bash
cd /home/juan/Documents/terminal-tools
. .venv/bin/activate
pytest -q
```

## Ejemplos curl
```bash
curl -sS http://127.0.0.1:8090/health

curl -sS -X POST http://127.0.0.1:8090/route \
  -H 'Content-Type: application/json' \
  -d '{"user_goal":"hazme un plan de implementación y riesgos","needs_plan":true,"complexity":3,"target_environment":"local","requires_iteration":false,"requires_code_changes":false,"needs_second_opinion":false,"allowed_mutation_level":"readonly"}'

curl -sS -X POST http://127.0.0.1:8090/run/command \
  -H 'Content-Type: application/json' \
  -d '{"user_goal":"listar archivos","command":["ls","-la"],"execution_mode":"sync","allow_mutative":false}'

curl -sS http://127.0.0.1:8090/path-policy

curl -sS -X POST http://127.0.0.1:8090/path-policy/check \
  -H 'Content-Type: application/json' \
  -d '{"path":"/home/juan/Documents/.env","action":"read"}'

curl -sS -X POST http://127.0.0.1:8090/trash/create \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"demo123","label":"scratch-temp"}'

curl -sS -X POST http://127.0.0.1:8090/trash/cleanup \
  -H 'Content-Type: application/json' \
  -d '{"dry_run":true}'
```

## Ejemplo MCP initialize
```bash
curl -i -sS -X POST http://127.0.0.1:8091/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"cli","version":"1.0"}}}'
```

## Limitaciones V1
- No scheduler distribuido ni cola externa.
- Adapters CLI dependen de binarios instalados en host.
- Wrappers de AI CLI son básicos, pensados para extender sin romper contratos.

## Trash temporal
- Raíz por defecto: `/home/juan/Documents/terminal-tools/data/trash`
- Espacios por tarea: `task_<task_id>`
- TTL por defecto: `7` días
- Cleanup automático en startup y manual por API/MCP
- No se borra fuera de `trash_root`

## Contexto de tarea y path policy
El contexto renderizado inyecta:
- `path_policy_summary.read_write_roots`
- `path_policy_summary.blocked_patterns`
- `scratch_root` por tarea
- `write_constraints.prefer_scratch_for_temporary_outputs=true`

## Extensión futura
- Añadir adapters sin tocar contratos API/MCP.
- Migrar runner local a Celery en caso de carga alta.
- Enriquecer recipes y perfiles con control más fino por entorno.
