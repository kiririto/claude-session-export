#!/usr/bin/env python3
"""
Claude Code Hook: Prevent Task agent from reading _ctx session export files.
_ctx.md files must be read directly (Read tool), not via agent summarization.
"""

import sys
import json
import re


def main():
    try:
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Task ツール呼び出しのみ対象
        if tool_name != "Task":
            print(json.dumps({"status": "ok"}))
            sys.exit(0)

        prompt = tool_input.get("prompt", "")

        # _ctx.md ファイルへの言及を検出
        if re.search(r'_ctx(_part\d+)?\.md', prompt):
            # 中間パート要約の明示的な承認マーカーがあれば許可
            if 'AUTHORIZED_CTX_MIDDLE_PART' in prompt:
                print(json.dumps({"status": "ok"}))
                sys.exit(0)

            warning = (
                "CTX FILE AGENT READ BLOCKED\n\n"
                "_ctx.md files are Claude Code session exports. "
                "They must be read DIRECTLY using the Read tool, not via Task agent.\n\n"
                "CORRECT METHOD:\n"
                "  - 1-2 parts per session: Read all parts directly\n"
                "  - 3+ parts per session: Read part1 + last part directly; "
                "middle parts via agent with 'AUTHORIZED_CTX_MIDDLE_PART' marker in prompt\n\n"
                "See CLAUDE.md 'Session Export Files (ctx files)' for details.\n"
            )
            sys.stderr.write("\n" + "=" * 60 + "\n")
            sys.stderr.write(warning)
            sys.stderr.write("=" * 60 + "\n\n")

            print(json.dumps({
                "action": "block",
                "reason": warning
            }))
            sys.exit(2)  # exit 2 = block the tool call

        print(json.dumps({"status": "ok"}))
        sys.exit(0)

    except Exception as e:
        sys.stderr.write(f"Hook error: {e}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
