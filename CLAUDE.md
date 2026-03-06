# claude-session-export

## Project Purpose

Export Claude Code sessions to clean, AI-readable Markdown files.

**Problem**: Claude Code stores conversations as JSONL files with UUID filenames. When a session hits the context limit and a new session is needed, there's no easy way to:
1. Identify which session is which without opening a browser
2. Feed the previous session's context to a new Claude Code session efficiently
3. Share conversation content with other AI tools like Gemini

**Solution**: A Python CLI script that converts JSONL session files (+ subagent files) to clean Markdown with human-readable filenames.

## Key Design Decisions

### Include Subagents?
Yes. The main session JSONL only contains brief `agent_progress` summaries of subagent calls. The actual research findings, tool outputs, and conclusions are stored exclusively in `subagents/agent-{id}.jsonl` files. Omitting them loses significant context.

### Content Extraction Rules
- **Keep**: User messages, assistant text responses, tool call names + key params, tool results (truncated), subagent conversations
- **Skip**: `thinking` blocks, `signature` fields, token stats, cache info, `file-history-snapshot` entries

## JSONL File Locations

```
~/.claude/projects/{project-dir}/
├── {session-uuid}.jsonl              # Main session
└── {session-uuid}/
    └── subagents/
        └── agent-{id}.jsonl          # Subagent conversations
```

On this machine:
```
C:\Users\liuzu\.claude\projects\C--Download\
```

## Usage

```bash
# List all sessions with titles
python export_session.py --list

# Interactive session picker
python export_session.py

# Export by title keyword or UUID prefix
python export_session.py "gemini"
python export_session.py 7e4893f8

# Export all sessions
python export_session.py --all

# Specify output directory
python export_session.py --all -o C:/Download/exports
```

## Output Format

Filename: `{YYYY-MM-DD}_{HH-MM}_{first-user-message-50chars}_ctx.md`

Content structure:
- Session header (date, message count, session ID)
- Conversation with `**User:**` / `**Claude:**` labels
- Tool calls shown as `[Tool: Name] params`
- Tool results truncated at 500 chars
- Plan files embedded at the top (`## Plan: {filename}`) before the conversation
- Subagents appended in a separate section `## Subagent: {id}`
- Large sessions auto-split into `_ctx_part1.md`, `_ctx_part2.md`... at `## Subagent:` boundaries (max 1200 lines/file)

## Session List Display

- Sessions with 0 messages are filtered out (empty sessions hidden)
- Two-line format per session:
  ```
    1. [2026-03-01 14:23] ( 42 msgs) my-session-name
          First user message preview...
  ```
- Session name uses `slug` field (set by `/rename`); falls back to `(no name)`
- Timestamps displayed in **local time** (UTC converted via `datetime.astimezone()`)

## Tech Stack

- Python 3.x (no external dependencies)
- Standard library only: `json`, `re`, `sys`, `pathlib`, `argparse`, `datetime`, `winreg` (Windows only)

## Development Notes

- Session JSONL lines use `uuid`/`parentUuid` for threading - messages must be walked in order, not just line by line
- `isSidechain: true` entries should be skipped (duplicate progress messages)
- Tool result content appears in `user` type messages (not `assistant`) via `content[].type: "tool_result"`
- Subagent identity is tracked via `agent_progress` entries in the main session, linking to subagent files by `agentId`
- `slug` field exists as a top-level entry field (not inside `message`); **last occurrence wins** so `/rename` is reflected
- Plan files detected via `Write` tool calls targeting `.claude/plans/*.md` paths; content read and prepended to output
- Default output directory resolved at runtime via `_get_downloads_folder()`: reads `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders\{374DE290-123F-4565-9164-39C4925E467B}` on Windows; falls back to `~/Downloads`

## ctx File Marker

All exported files have a `_ctx` suffix in the filename:
- Single file: `2026-03-05_14-23_my-session_ctx.md`
- Multi-part: `2026-03-05_14-23_my-session_ctx_part1.md`

This marker signals to Claude Code that the file is a session export and should be read directly
(not summarized via Task agent). See `hooks/check_ctx_file_agent.py` for enforcement.

### Hook Bypass for Middle Parts

For sessions with 3+ parts, the middle parts may be read via a Task agent (Explore) for summarization.
To bypass the hook in this case, include `AUTHORIZED_CTX_MIDDLE_PART` in the agent prompt:

```
AUTHORIZED_CTX_MIDDLE_PART
Summarize key decisions and code changes in [filename]...
```

The hook allows this through while still blocking unauthorized agent reads.
