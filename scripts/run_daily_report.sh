#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

CONFIG_FILE="${CONFIG_FILE:-$REPO_DIR/config.json}"
REPORT_DATE="${1:-$(date +%F)}"
OUT_DIR="$REPO_DIR/out/$REPORT_DATE"
CONTEXT_JSON="$OUT_DIR/context.json"
REPORT_MD="$OUT_DIR/report.md"
PROMPT_FILE="$OUT_DIR/prompt.txt"
EMAIL_PROMPT_FILE="$OUT_DIR/email_prompt.txt"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/daily-report-$REPORT_DATE.log"
DRY_RUN="${DRY_RUN:-0}"
INCLUDE_RECENT_FILES="${INCLUDE_RECENT_FILES:-0}"
if [[ -z "${INCLUDE_GIT+x}" ]]; then
  if [[ "$DRY_RUN" == "1" ]]; then
    INCLUDE_GIT="0"
  else
    INCLUDE_GIT="1"
  fi
fi

mkdir -p "$OUT_DIR" "$LOG_DIR"

find_executable() {
  local name="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  command -v "$name"
}

AGENT_BIN="${AGENT_BIN:-$(find_executable agl "$HOME/.local/bin/agl" /opt/homebrew/bin/agl /usr/local/bin/agl)}"
PYTHON_BIN="${PYTHON_BIN:-$(find_executable python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3)}"
NPM_BIN="${NPM_BIN:-$(find_executable npm /opt/homebrew/bin/npm /usr/local/bin/npm)}"

timestamp() {
  date "+%Y-%m-%dT%H:%M:%S%z"
}

config_value() {
  "$PYTHON_BIN" - "$CONFIG_FILE" "$1" "$2" <<'PY'
import json, sys
path, dotted, default = sys.argv[1:]
try:
    data = json.load(open(path))
except Exception:
    data = {}
cur = data
for part in dotted.split("."):
    if not isinstance(cur, dict) or part not in cur:
        print(default)
        raise SystemExit
    cur = cur[part]
print(cur if not isinstance(cur, (dict, list)) else json.dumps(cur))
PY
}

{
  echo "[$(timestamp)] Collecting context for $REPORT_DATE"
  collect_args=(
    "$REPO_DIR/scripts/collect_daily_context.py"
    --date "$REPORT_DATE" \
    --config "$CONFIG_FILE" \
    --out "$CONTEXT_JSON"
  )
  if [[ "$INCLUDE_RECENT_FILES" != "1" ]]; then
    collect_args+=(--no-recent-files)
  fi
  if [[ "$INCLUDE_GIT" != "1" ]]; then
    collect_args+=(--no-git)
  fi
  "$PYTHON_BIN" "${collect_args[@]}"

  sed \
    -e "s|{CONTEXT_JSON}|$CONTEXT_JSON|g" \
    -e "s|{REPORT_DATE}|$REPORT_DATE|g" \
    -e "s|{REPORT_MD}|$REPORT_MD|g" \
    "$REPO_DIR/prompts/daily_report_prompt.md" > "$PROMPT_FILE"

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[$(timestamp)] Dry run; context and prompt written"
    exit 0
  fi

  echo "[$(timestamp)] Generating report with Codex-capable agent"
  "$AGENT_BIN" --non-interactive --prefer codex --cwd "$REPO_DIR" --mode danger --model-class fast --prompt-file "$PROMPT_FILE"

  if [[ ! -s "$REPORT_MD" ]]; then
    echo "[$(timestamp)] Report was not written: $REPORT_MD"
    exit 1
  fi

  echo "[$(timestamp)] Building site"
  build_command="$(config_value deploy.build_command "npm run build")"
  (cd "$REPO_DIR" && eval "$build_command")

  echo "[$(timestamp)] Committing generated report artifacts"
  (
    cd "$REPO_DIR"
    git add "$REPORT_MD" "$REPO_DIR/src/generated/reports.json" 2>/dev/null || git add "$REPORT_MD"
    if ! git diff --cached --quiet; then
      git commit -m "Add daily report for $REPORT_DATE"
      git push
    fi
  )

  echo "[$(timestamp)] Deploying"
  deploy_command="$(config_value deploy.deploy_command "true")"
  (cd "$REPO_DIR" && eval "$deploy_command")

  email_to="$(config_value report_email_to "")"
  report_url_template="$(config_value updates_url_template "https://updates.example.com/?day={date}")"
  report_url="${report_url_template//\{date\}/$REPORT_DATE}"
  sed \
    -e "s|{REPORT_DATE}|$REPORT_DATE|g" \
    -e "s|{REPORT_MD}|$REPORT_MD|g" \
    -e "s|{REPORT_EMAIL_TO}|$email_to|g" \
    -e "s|{REPORT_URL}|$report_url|g" \
    "$REPO_DIR/prompts/post_deploy_email_prompt.md" > "$EMAIL_PROMPT_FILE"

  if [[ -n "$email_to" ]]; then
    echo "[$(timestamp)] Sending post-deploy email"
    "$AGENT_BIN" --non-interactive --prefer codex --cwd "$REPO_DIR" --mode danger --model-class fast --prompt-file "$EMAIL_PROMPT_FILE"
  else
    echo "[$(timestamp)] report_email_to empty; skipping email"
  fi
} >>"$LOG_FILE" 2>&1
