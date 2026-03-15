#!/usr/bin/env bash
# claude-wrapper.sh — emulates `claude --print <prompt>` using the Copilot CLI
# This allows the terminal-tools "claude" adapter to work without a direct Anthropic login.
#
# Supported flags (others are silently ignored):
#   --print <prompt>      prompt to send (required)
#   --model <model>       model alias; mapped to a copilot-compatible alias
#   --output-format text  (accepted, ignored — output is always text)
#   --add-dir <dir>       passed through to copilot as --add-dir
#   --dangerously-skip-permissions  (accepted, ignored)
#   --version             print wrapper version and exit

set -euo pipefail

COPILOT_BIN="${COPILOT_BIN:-/opt/fnm-host/node-versions/v22.22.0/installation/bin/copilot}"

if [[ ! -x "$COPILOT_BIN" ]]; then
  echo "claude-wrapper: copilot binary not found at $COPILOT_BIN" >&2
  exit 1
fi

PROMPT=""
MODEL="claude-haiku-4.5"
ADD_DIRS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print)
      PROMPT="$2"
      shift 2
      ;;
    --model)
      # Map common claude model aliases to copilot-supported ones
      case "$2" in
        claude-haiku*|haiku)   MODEL="claude-haiku-4.5" ;;
        claude-sonnet*|sonnet) MODEL="claude-sonnet-4.5" ;;
        claude-opus*|opus)     MODEL="claude-opus-4.5" ;;
        *)                     MODEL="claude-haiku-4.5" ;;
      esac
      shift 2
      ;;
    --add-dir)
      ADD_DIRS+=("--add-dir" "$2")
      shift 2
      ;;
    --version)
      echo "claude-wrapper 1.0.0 (via copilot)"
      exit 0
      ;;
    --output-format)
      # accepted, skip the value
      shift 2
      ;;
    --dangerously-skip-permissions|--allow-dangerously-skip-permissions|--no-color|--no-session-persistence)
      # accepted flags without values, ignored
      shift
      ;;
    --)
      shift
      break
      ;;
    *)
      shift
      ;;
  esac
done

if [[ -z "$PROMPT" ]]; then
  echo "claude-wrapper: --print <prompt> is required" >&2
  exit 1
fi

exec "$COPILOT_BIN" -p "$PROMPT" \
  --model "$MODEL" \
  --output-format text \
  --no-color \
  "${ADD_DIRS[@]}"
