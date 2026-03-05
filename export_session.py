#!/usr/bin/env python3
"""
Export Claude Code sessions to clean, AI-readable Markdown files.

Author: kiririto

USAGE
  python export_session.py                     Interactive session picker
  python export_session.py --list              List all sessions (no export)
  python export_session.py "keyword"           Export by title keyword
  python export_session.py 7e4893f8            Export by UUID prefix
  python export_session.py --all               Export all sessions
  python export_session.py --all -o D:\\out    Export all to custom directory
  python export_session.py "keyword" --no-subagents  Skip subagent content

OUTPUT
  Files are saved to your system Downloads folder by default.
  Filename format: YYYY-MM-DD_first-message-title.md

EXAMPLES
  python export_session.py --list
  python export_session.py gemini
  python export_session.py --all -o C:\\Users\\me\\Desktop
"""

import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime


# Claude Code projects directory
PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Claude Code plans directory
PLANS_DIR = Path.home() / ".claude" / "plans"

# Default output directory: system Downloads folder (falls back to ~/Downloads)
def _get_downloads_folder() -> Path:
    if sys.platform == 'win32':
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
            )
            path, _ = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')
            winreg.CloseKey(key)
            return Path(path)
        except Exception:
            pass
    return Path.home() / 'Downloads'

DEFAULT_OUTPUT_DIR = _get_downloads_folder()

# Max chars for tool result output (keeps Markdown readable)
TOOL_RESULT_MAX_CHARS = 500

# Max lines per output file (Claude Code Read tool hard limit is 2000 lines)
MAX_LINES_PER_FILE = 1200


# ─── Session discovery ────────────────────────────────────────────────────────

def find_sessions(projects_dir: Path) -> list:
    """Find all main session JSONL files, excluding subagents directories."""
    sessions = []
    for jsonl_file in projects_dir.rglob("*.jsonl"):
        if "subagents" in jsonl_file.parts:
            continue
        sessions.append(jsonl_file)
    return sessions


def get_session_info(jsonl_file: Path) -> dict:
    """Extract title (first user message), timestamp, message count, slug, and last_timestamp."""
    first_user_msg = None
    first_timestamp = None
    last_timestamp = None
    msg_count = 0
    slug = None

    try:
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("isSidechain"):
                    continue

                # slug はトップレベルフィールドとして存在する（最後の値で上書き → rename 後の名前を反映）
                s = entry.get("slug")
                if s:
                    slug = s

                # タイムスタンプを追跡
                ts = entry.get("timestamp")
                if ts:
                    if first_timestamp is None:
                        first_timestamp = ts
                    if last_timestamp is None or ts > last_timestamp:
                        last_timestamp = ts

                if entry.get("type") not in ("user", "assistant"):
                    continue

                msg_count += 1

                if entry.get("type") == "user" and first_user_msg is None:
                    content = entry.get("message", {}).get("content", "")
                    text = _extract_plain_text(content)
                    if text:
                        first_user_msg = text

    except Exception:
        pass

    return {
        "file": jsonl_file,
        "session_id": jsonl_file.stem,
        "project": jsonl_file.parent.name,
        "first_message": first_user_msg or "(empty)",
        "timestamp": first_timestamp or "",
        "last_timestamp": last_timestamp or first_timestamp or "",
        "msg_count": msg_count,
        "slug": slug,
    }


def find_session_by_query(projects_dir: Path, query: str) -> list:
    """Find sessions matching a UUID prefix or title keyword (case-insensitive)."""
    query_lower = query.lower()
    matches = []
    for f in find_sessions(projects_dir):
        if f.stem.lower().startswith(query_lower):
            matches.append(f)
            continue
        info = get_session_info(f)
        if query_lower in info["first_message"].lower():
            matches.append(f)
    return matches


# ─── JSONL parsing ────────────────────────────────────────────────────────────

def _extract_plain_text(content) -> str:
    """Extract readable text from a content field (string or array)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            item.get("text", "").strip()
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return ""


def _format_tool_param(name: str, input_data: dict) -> str:
    """Return a concise one-line description of a tool call's parameters."""
    if name == "WebFetch":
        return input_data.get("url", "")
    if name == "WebSearch":
        return input_data.get("query", "")
    if name == "Bash":
        cmd = input_data.get("command", "")
        return (cmd[:100] + "...") if len(cmd) > 100 else cmd
    if name in ("Read", "Write", "Edit", "Glob"):
        return input_data.get("file_path") or input_data.get("pattern", "")
    if name == "Grep":
        pattern = input_data.get("pattern", "")
        path = input_data.get("path", "")
        return f'"{pattern}" in {path}' if path else f'"{pattern}"'
    if name == "Task":
        return input_data.get("description", "")
    # Fallback: first string value
    for v in input_data.values():
        if isinstance(v, str) and v.strip():
            return v[:100]
    return ""


def parse_session(jsonl_file: Path, include_subagents: bool = True) -> list:
    """
    Parse a session JSONL into a flat list of structured message dicts.

    Message types returned:
      {"role": "user",          "text": str}
      {"role": "assistant",     "text": str, "tool_calls": [...]}
      {"role": "tool_result",   "tool_results": [...]}
      {"role": "subagent_header", "agent_id": str}
    """
    try:
        with open(jsonl_file, encoding="utf-8") as f:
            raw_lines = f.readlines()
    except Exception:
        return []

    entries = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    messages = []
    subagent_ids = []
    plan_files = []  # plan file paths found via Write tool calls
    pending_tool_uses = {}  # tool_use_id -> {name, param}

    for entry in entries:
        if entry.get("isSidechain"):
            continue

        etype = entry.get("type")

        # Collect subagent IDs from progress entries
        if etype == "progress":
            data = entry.get("data", {})
            if data.get("type") == "agent_progress":
                aid = data.get("agentId", "")
                if aid and aid not in subagent_ids:
                    subagent_ids.append(aid)
            continue

        if etype == "agent_progress":
            aid = entry.get("agentId", "")
            if aid and aid not in subagent_ids:
                subagent_ids.append(aid)
            continue

        if etype not in ("user", "assistant"):
            continue

        msg = entry.get("message", {})
        role = msg.get("role", etype)
        content = msg.get("content", "")

        if role == "assistant":
            if isinstance(content, list):
                text_parts = []
                tool_calls = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("type")
                    if itype == "text":
                        t = item.get("text", "").strip()
                        if t:
                            text_parts.append(t)
                    elif itype == "tool_use":
                        tid = item.get("id", "")
                        tname = item.get("name", "")
                        tparam = _format_tool_param(tname, item.get("input", {}))
                        tool_calls.append({"id": tid, "name": tname, "param": tparam})
                        pending_tool_uses[tid] = {"name": tname, "param": tparam}
                        # Detect Write calls targeting plan files
                        if tname == "Write":
                            fp_str = item.get("input", {}).get("file_path", "")
                            fp = Path(fp_str.replace("\\", "/"))
                            fp_parts = fp_str.replace("\\", "/")
                            if ".claude" in fp_parts and "plans" in fp_parts and fp.suffix == ".md":
                                if fp not in plan_files:
                                    plan_files.append(fp)
                    # "thinking" blocks are intentionally skipped
                if text_parts or tool_calls:
                    messages.append({
                        "role": "assistant",
                        "text": "\n".join(text_parts),
                        "tool_calls": tool_calls,
                    })
            else:
                text = _extract_plain_text(content)
                if text:
                    messages.append({"role": "assistant", "text": text, "tool_calls": []})

        elif role == "user":
            if isinstance(content, list):
                tool_results = []
                text_parts = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("type")
                    if itype == "tool_result":
                        rc = item.get("content", "")
                        if isinstance(rc, list):
                            rc = "\n".join(
                                x.get("text", "") for x in rc
                                if isinstance(x, dict) and x.get("type") == "text"
                            )
                        rc = str(rc).strip()
                        if len(rc) > TOOL_RESULT_MAX_CHARS:
                            rc = rc[:TOOL_RESULT_MAX_CHARS] + f"\n...(truncated, {len(rc)} chars total)"
                        tuid = item.get("tool_use_id", "")
                        tinfo = pending_tool_uses.get(tuid, {})
                        tool_results.append({
                            "name": tinfo.get("name", ""),
                            "result": rc,
                        })
                    elif itype == "text":
                        t = item.get("text", "").strip()
                        if t:
                            text_parts.append(t)
                if tool_results:
                    messages.append({"role": "tool_result", "tool_results": tool_results})
                elif text_parts:
                    messages.append({"role": "user", "text": "\n".join(text_parts), "tool_calls": []})
            else:
                text = _extract_plain_text(content)
                if text:
                    messages.append({"role": "user", "text": text, "tool_calls": []})

    # Append subagent conversations
    if include_subagents and subagent_ids:
        subagents_dir = jsonl_file.parent / jsonl_file.stem / "subagents"
        for aid in subagent_ids:
            agent_file = subagents_dir / f"agent-{aid}.jsonl"
            if agent_file.exists():
                agent_msgs = parse_session(agent_file, include_subagents=False)
                if agent_msgs:
                    messages.append({"role": "subagent_header", "agent_id": aid})
                    messages.extend(agent_msgs)

    # Prepend plan file contents (inserted at index 0 so they appear before conversation)
    for pf in reversed(plan_files):
        try:
            content = pf.read_text(encoding="utf-8")
            messages.insert(0, {"role": "plan_file", "path": pf.name, "content": content})
        except Exception:
            pass

    return messages


# ─── Markdown rendering ───────────────────────────────────────────────────────

def messages_to_markdown(messages: list, session_info: dict) -> str:
    """Render parsed messages as clean Markdown."""
    lines = []

    # Header
    first_msg = session_info.get("first_message", "")
    session_id = session_info.get("session_id", "")
    msg_count = session_info.get("msg_count", 0)
    ts = session_info.get("timestamp", "")
    date_str = _format_date(ts)

    lines.append(f"# {first_msg[:80]}")
    lines.append("")
    lines.append(f"**Date:** {date_str}  |  **Messages:** {msg_count}  |  **Session ID:** `{session_id[:8]}...`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Render plan files first (before conversation) to avoid 2000-line truncation
    plan_msgs = [m for m in messages if m.get("role") == "plan_file"]
    other_msgs = [m for m in messages if m.get("role") != "plan_file"]
    for pm in plan_msgs:
        lines += [f"## Plan: {pm['path']}", "", pm["content"].strip(), "", "---", ""]

    for msg in other_msgs:
        role = msg.get("role")

        if role == "subagent_header":
            lines += ["", "---", f"## Subagent: {msg.get('agent_id', '')}", ""]

        elif role == "user":
            text = msg.get("text", "").strip()
            if text:
                lines.append(f"**User:** {text}")
                lines.append("")

        elif role == "assistant":
            text = msg.get("text", "").strip()
            tool_calls = msg.get("tool_calls", [])
            if text:
                lines.append(f"**Claude:** {text}")
                lines.append("")
            for tc in tool_calls:
                name = tc.get("name", "")
                param = tc.get("param", "")
                lines.append(f"> [Tool: {name}]" + (f" `{param}`" if param else ""))
                lines.append("")

        elif role == "tool_result":
            for tr in msg.get("tool_results", []):
                result = tr.get("result", "").strip()
                name = tr.get("name", "")
                label = f"[Result: {name}]" if name else "[Result]"
                if result:
                    lines.append(f"> {label} {result}")
                    lines.append("")

    return "\n".join(lines)


def _split_markdown(md: str, max_lines: int) -> list:
    """
    Split a Markdown string into parts of at most max_lines lines.
    Splits at '## Subagent:' boundaries where possible.
    Returns a list of strings (parts).
    """
    all_lines = md.splitlines()
    if len(all_lines) <= max_lines:
        return [md]

    # Find split points: lines starting with '## Subagent:' or '---' section boundaries
    split_indices = [0]
    for i, line in enumerate(all_lines):
        if i > 0 and line.startswith("## Subagent:"):
            split_indices.append(i)

    parts = []
    split_indices.append(len(all_lines))  # sentinel

    current_start = 0
    current_split_pos = 0

    while current_start < len(all_lines):
        # Find the furthest split point that keeps us within max_lines
        end = current_start + max_lines
        if end >= len(all_lines):
            parts.append("\n".join(all_lines[current_start:]))
            break

        # Find the best split boundary before `end`
        best_boundary = end
        for idx in split_indices:
            if current_start < idx <= end:
                best_boundary = idx

        # If no boundary found within range, hard-cut at max_lines
        if best_boundary == end:
            best_boundary = end

        parts.append("\n".join(all_lines[current_start:best_boundary]))
        current_start = best_boundary

    return parts


# ─── File output ──────────────────────────────────────────────────────────────

def _sanitize_filename(text: str) -> str:
    """Convert arbitrary text to a safe, readable filename segment."""
    text = text.strip()
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    text = text[:50].strip()
    text = re.sub(r"\s+", "-", text)
    return text or "session"


def _format_date(timestamp: str) -> str:
    """Return YYYY-MM-DD from an ISO timestamp string."""
    if not timestamp:
        return "unknown"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return timestamp[:10]


def _format_time_for_file(timestamp: str) -> str:
    """Return HH-MM in local time from an ISO timestamp string."""
    if not timestamp:
        return "0000"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%H-%M")
    except Exception:
        return "0000"


def _format_datetime(timestamp: str) -> str:
    """Return YYYY-MM-DD HH:MM in local time from an ISO timestamp string."""
    if not timestamp:
        return "unknown"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        # UTC → システムのローカルタイムに変換
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return timestamp[:16]


def export_session(jsonl_file: Path, output_dir: Path, include_subagents: bool = True):
    """Export one session to a Markdown file (or multiple parts). Returns the output Path or None."""
    info = get_session_info(jsonl_file)
    messages = parse_session(jsonl_file, include_subagents)

    if not messages:
        print("  (no messages found, skipping)")
        return None

    md = messages_to_markdown(messages, info)

    date_str = _format_date(info["timestamp"])
    time_str = _format_time_for_file(info["timestamp"])
    title = _sanitize_filename(info["first_message"])
    output_dir.mkdir(parents=True, exist_ok=True)

    parts = _split_markdown(md, MAX_LINES_PER_FILE)

    if len(parts) == 1:
        out_file = output_dir / f"{date_str}_{time_str}_{title}.md"
        counter = 1
        while out_file.exists():
            out_file = output_dir / f"{date_str}_{time_str}_{title}_{counter}.md"
            counter += 1
        out_file.write_text(parts[0], encoding="utf-8")
        return out_file
    else:
        # Multi-part: add Part N/M header to each part
        total = len(parts)
        first_out = None
        base_name = f"{date_str}_{time_str}_{title}"
        for i, part_content in enumerate(parts, 1):
            part_header = f"> Part {i}/{total}\n\n"
            out_file = output_dir / f"{base_name}_part{i}.md"
            counter = 1
            while out_file.exists():
                out_file = output_dir / f"{base_name}_part{i}_{counter}.md"
                counter += 1
            out_file.write_text(part_header + part_content, encoding="utf-8")
            if i == 1:
                first_out = out_file
            print(f"     Part {i}/{total} -> {out_file.name}")
        return first_out


# ─── CLI commands ─────────────────────────────────────────────────────────────

def cmd_list(projects_dir: Path):
    """Print all sessions sorted by date descending."""
    all_infos = sorted(
        [get_session_info(f) for f in find_sessions(projects_dir)],
        key=lambda x: x["last_timestamp"] or x["timestamp"],
        reverse=False,
    )
    if not all_infos:
        print("No sessions found.")
        return

    # 空の session を除外
    infos = [i for i in all_infos if i["msg_count"] > 0]
    empty_count = len(all_infos) - len(infos)

    print(f"\nFound {len(infos)} sessions:\n")
    for i, info in enumerate(infos, 1):
        dt = _format_datetime(info["last_timestamp"] or info["timestamp"])
        n = info["msg_count"]
        name = info.get("slug") or "(no name)"
        preview = info["first_message"][:70]
        if preview.startswith("<"):
            preview = "(command/system message)"
        print(f"  {i:3}. [{dt}] ({n:3} msgs) {name}")
        print(f"        {preview}")
        print()

    if empty_count:
        print(f"  ({empty_count} empty sessions hidden)")


def cmd_interactive(projects_dir: Path, output_dir: Path, include_subagents: bool):
    """Interactive picker: show list and let user choose."""
    all_infos = sorted(
        [get_session_info(f) for f in find_sessions(projects_dir)],
        key=lambda x: x["last_timestamp"] or x["timestamp"],
        reverse=False,
    )
    if not all_infos:
        print("No sessions found.")
        return

    # 空の session を除外
    infos = [i for i in all_infos if i["msg_count"] > 0]
    empty_count = len(all_infos) - len(infos)

    print(f"\nFound {len(infos)} sessions:\n")
    for i, info in enumerate(infos, 1):
        dt = _format_datetime(info["last_timestamp"] or info["timestamp"])
        n = info["msg_count"]
        name = info.get("slug") or "(no name)"
        preview = info["first_message"][:70]
        if preview.startswith("<"):
            preview = "(command/system message)"
        print(f"  {i:3}. [{dt}] ({n:3} msgs) {name}")
        print(f"        {preview}")
        print()

    if empty_count:
        print(f"  ({empty_count} empty sessions hidden)")

    print()
    try:
        choice = input("Enter number (0 to cancel): ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(infos):
            target = infos[idx]["file"]
            info = infos[idx]
            name = info.get("slug") or info["first_message"][:60]
            print(f"\nExporting: {name}...")
            out = export_session(target, output_dir, include_subagents)
            if out:
                print(f"Done -> {out}")
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.")


def cmd_export_query(projects_dir: Path, query: str, output_dir: Path, include_subagents: bool):
    """Export session(s) matching a UUID prefix or title keyword."""
    matches = find_session_by_query(projects_dir, query)
    if not matches:
        print(f"No sessions matching '{query}'")
        sys.exit(1)

    if len(matches) == 1:
        target = matches[0]
    else:
        print(f"Found {len(matches)} matching sessions:\n")
        infos = sorted(
            [get_session_info(f) for f in matches],
            key=lambda x: x["last_timestamp"] or x["timestamp"]
        )
        for i, info in enumerate(infos, 1):
            dt = _format_datetime(info["last_timestamp"] or info["timestamp"])
            n = info["msg_count"]
            name = info.get("slug") or "(no name)"
            preview = info["first_message"][:70]
            if preview.startswith("<"):
                preview = "(command/system message)"
            print(f"  {i:3}. [{dt}] ({n:3} msgs) {name}")
            print(f"        {preview}")
            print()
        print()
        try:
            choice = input("Enter number (0 to cancel): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                target = matches[idx]
            else:
                print("Cancelled.")
                return
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            return

    info = get_session_info(target)
    print(f"Exporting: {info['first_message'][:60]}...")
    out = export_session(target, output_dir, include_subagents)
    if out:
        print(f"Done -> {out}")


def cmd_export_all(projects_dir: Path, output_dir: Path, include_subagents: bool):
    """Export every session."""
    files = find_sessions(projects_dir)
    if not files:
        print("No sessions found.")
        return
    print(f"Exporting {len(files)} sessions to {output_dir} ...\n")
    for f in files:
        info = get_session_info(f)
        title = info["first_message"][:55]
        print(f"  -> {title}...")
        out = export_session(f, output_dir, include_subagents)
        if out:
            print(f"     {out.name}")
    print("\nDone.")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="export_session",
        description="Export Claude Code sessions to clean Markdown files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "query", nargs="?",
        help="Session title keyword or UUID prefix to export",
    )
    parser.add_argument("--list", action="store_true", help="List all sessions")
    parser.add_argument("--all",  action="store_true", help="Export all sessions")
    parser.add_argument(
        "-o", "--output", default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-subagents", action="store_true",
        help="Skip subagent conversation content",
    )
    parser.add_argument(
        "--projects-dir",
        help=f"Claude projects directory (default: {PROJECTS_DIR})",
    )

    args = parser.parse_args()

    projects_dir = Path(args.projects_dir) if args.projects_dir else PROJECTS_DIR
    output_dir   = Path(args.output)
    include_subs = not args.no_subagents

    if not projects_dir.exists():
        print(f"Error: Projects directory not found: {projects_dir}")
        sys.exit(1)

    if args.list:
        cmd_list(projects_dir)
    elif args.all:
        cmd_export_all(projects_dir, output_dir, include_subs)
    elif args.query:
        cmd_export_query(projects_dir, args.query, output_dir, include_subs)
    else:
        cmd_interactive(projects_dir, output_dir, include_subs)


if __name__ == "__main__":
    main()
