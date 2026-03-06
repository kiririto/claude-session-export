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

        # Read ツール: _ctx ファイルを limit なしで読む場合はファイルサイズを確認
        if tool_name == "Read":
            file_path = tool_input.get("file_path", "")
            if re.search(r'_ctx(_part\d+)?\.md', file_path):
                if tool_input.get("limit") is None:
                    # ファイルの実際の文字数を確認して自動判断
                    CHAR_THRESHOLD = 50000
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        char_count = len(content)

                        if char_count >= CHAR_THRESHOLD:
                            # 50K超: 適切なチャンクサイズを計算してブロック
                            line_count = content.count('\n') + 1
                            # 1チャンクが45K文字以下になる行数を計算（安全マージン10%）
                            chunk_size = max(50, int(45000 * line_count / char_count))
                            warning = (
                                f"CTX FILE READ BLOCKED\n\n"
                                f"File: {char_count:,} characters ({line_count} lines) — "
                                f"exceeds {CHAR_THRESHOLD:,} char limit.\n"
                                f"Reading without limit means only a 2KB preview enters context.\n\n"
                                f"CORRECT METHOD (auto-calculated chunk size):\n"
                                f"  Read with limit={chunk_size}\n"
                                f"  then offset={chunk_size} limit={chunk_size}\n"
                                f"  repeat until all {line_count} lines are read\n\n"
                                f"See CLAUDE.md 'Session Export Files (ctx files)' for details.\n"
                            )
                            sys.stderr.write("\n" + "=" * 60 + "\n")
                            sys.stderr.write(warning)
                            sys.stderr.write("=" * 60 + "\n\n")
                            print(json.dumps({
                                "action": "block",
                                "reason": warning
                            }))
                            sys.exit(2)
                        # 50K未満: limit なしでも安全、許可
                    except (OSError, IOError):
                        # ファイル読み取り失敗: Readツール自体にエラー処理を任せる
                        pass
            print(json.dumps({"status": "ok"}))
            sys.exit(0)

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
