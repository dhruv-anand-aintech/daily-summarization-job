#!/usr/bin/env python3
"""Collect local evidence for a daily work report.

This is a public, configurable version of the collector. It avoids hard-coded
private domains and keeps sensitive raw artifacts in the generated context file,
which should remain private.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


HOME = Path.home()
REPO_DIR = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".wrangler"}


def expand_path(value: str | None, default: Path | None = None) -> Path | None:
    if not value:
        return default
    return Path(value).expanduser()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"ERROR: {exc}"


def day_bounds(day: str, tz_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(tz_name)
    d = datetime.strptime(day, "%Y-%m-%d").date()
    return datetime.combine(d, time.min, zone), datetime.combine(d, time.max, zone)


def project_names(config: dict) -> dict[str, str]:
    path = expand_path(config.get("project_names_path"), REPO_DIR / "config" / "project_names.json")
    data = load_json(path) if path else {}
    return {str(k): str(v) for k, v in data.items() if str(k).strip() and str(v).strip()}


def display_project_name(name_or_path: str | None, names: dict[str, str]) -> str:
    if not name_or_path:
        return "unknown"
    text = str(name_or_path).strip()
    base = Path(text).name if "/" in text else text
    return names.get(text) or names.get(base) or base or text


def git_repos(root: Path) -> list[Path]:
    repos = []
    for git_dir in root.glob("*/.git"):
        if git_dir.is_dir():
            repos.append(git_dir.parent)
    return sorted(repos)


def collect_git(root: Path, start: datetime, end: datetime, names: dict[str, str]) -> dict:
    repos = []
    since = start.isoformat()
    until = end.isoformat()
    for repo in git_repos(root):
        commits = run(
            ["git", "log", "--all", f"--since={since}", f"--until={until}", "--date=iso", "--pretty=format:%h%x09%ad%x09%s"],
            repo,
        )
        status = run(["git", "status", "--porcelain"], repo)
        if commits or status:
            repos.append(
                {
                    "path": str(repo),
                    "name": display_project_name(repo.name, names),
                    "branch": run(["git", "branch", "--show-current"], repo),
                    "commits": commits.splitlines() if commits else [],
                    "status": status.splitlines()[:80] if status else [],
                }
            )
    return {"repos": repos}


def parse_kanban_cards(markdown: str, names: dict[str, str]) -> list[dict]:
    cards: list[dict] = []
    state = ""
    for line in markdown.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            state = heading.group(1).strip()
            continue
        item = re.match(r"^\s*(?:-\s+)?(?:child:\s+)?-\s+\[[ xX]\]\s+\[\[([^\]]+)\]\](.*)$", line)
        if not item:
            item = re.match(r"^\s*-\s+child:\s+\[\[([^\]]+)\]\](.*)$", line)
        if not item or not state:
            continue
        raw_name = item.group(1).strip()
        rest = item.group(2) or ""
        attrs = dict(re.findall(r"\[([A-Za-z]+):([^\]]+)\]", rest))
        cards.append(
            {
                "name": raw_name,
                "display_name": display_project_name(raw_name, names),
                "state": state,
                "importance": attrs.get("I"),
                "complexity": attrs.get("C"),
                "tags": re.findall(r"#([A-Za-z0-9_-]+)", rest),
            }
        )
    return cards


def collect_project_kanban(config: dict, names: dict[str, str]) -> dict:
    path = expand_path(config.get("project_kanban_path"))
    if not path or not path.exists():
        return {"path": str(path) if path else None, "cards": []}
    text = path.read_text(errors="ignore")
    cards = parse_kanban_cards(text, names)
    return {"path": str(path), "cards": cards, "active": [c for c in cards if c["state"] in {"In progress", "MVP"}]}


def collect_recent_files(root: Path, start: datetime, end: datetime, limit: int) -> list[dict]:
    start_ts = start.timestamp()
    end_ts = end.timestamp()
    files = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_PARTS]
        for name in names:
            path = Path(current) / name
            try:
                st = path.stat()
            except OSError:
                continue
            if start_ts <= st.st_mtime <= end_ts:
                files.append({"mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"), "path": str(path), "size": st.st_size})
    return sorted(files, key=lambda x: x["mtime"])[-limit:]


def text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item.get("text") or item.get("content") or "") for item in content if isinstance(item, dict))
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    return ""


def collect_codex_sessions(config: dict, day: str, limit: int = 25) -> list[dict]:
    base = expand_path(((config.get("transcripts") or {}).get("codex_sessions")), HOME / ".codex" / "sessions")
    day_dir = base / day[:4] / day[5:7] / day[8:10] if base else None
    if not day_dir or not day_dir.exists():
        return []
    sessions = []
    for path in sorted(day_dir.glob("*.jsonl")):
        cwd = None
        messages = []
        for line in path.read_text(errors="ignore").splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "session_meta":
                cwd = (obj.get("payload") or {}).get("cwd") or cwd
            if obj.get("type") != "response_item":
                continue
            item = obj.get("payload") or {}
            if item.get("type") == "message" and item.get("role") == "user":
                text = text_from_content(item.get("content")).strip()
                if text and not text.startswith(("<", "# AGENTS.md")):
                    messages.append(text[:600])
        if messages:
            sessions.append({"path": str(path), "cwd": cwd, "user_messages": messages[:12]})
    return sessions[-limit:]


def collect_opencode(config: dict, start: datetime, end: datetime, limit: int = 80) -> list[dict]:
    db = expand_path(((config.get("transcripts") or {}).get("opencode_db")), HOME / ".local/share/opencode/opencode.db")
    if not db or not db.exists():
        return []
    out = []
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
        rows = conn.execute(
            "select m.session_id, m.data, p.data from message m left join part p on p.message_id=m.id "
            "where m.time_created between ? and ? order by m.time_created limit ?",
            (int(start.timestamp() * 1000), int(end.timestamp() * 1000), limit * 4),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return []
    for session_id, msg_data, part_data in rows:
        try:
            msg = json.loads(msg_data)
            part = json.loads(part_data) if part_data else {}
        except Exception:
            continue
        if msg.get("role") == "user":
            text = text_from_content(part.get("text") or msg.get("content")).strip()
            if text:
                out.append({"session_id": session_id, "text": text[:1000]})
    return out[:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--config", default=str(REPO_DIR / "config.json"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--file-limit", type=int, default=120)
    parser.add_argument("--no-git", action="store_true")
    parser.add_argument("--no-recent-files", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config)) or load_json(REPO_DIR / "config.example.json")
    tz_name = config.get("timezone", "UTC")
    root = expand_path(config.get("code_root"), HOME / "Code") or (HOME / "Code")
    start, end = day_bounds(args.date, tz_name)
    names = project_names(config)

    report = {
        "date": args.date,
        "timezone": tz_name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_names": names,
        "project_kanban": collect_project_kanban(config, names),
        "git": {"repos": []} if args.no_git else collect_git(root, start, end, names),
        "recent_files": [] if args.no_recent_files else collect_recent_files(root, start, end, args.file_limit),
        "codex_sessions": collect_codex_sessions(config, args.date),
        "opencode_user_messages": collect_opencode(config, start, end),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "out": str(out),
                "repos": len(report["git"]["repos"]),
                "kanban_cards": len(report["project_kanban"].get("cards") or []),
                "codex_sessions": len(report["codex_sessions"]),
                "opencode_messages": len(report["opencode_user_messages"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
