# Claude Session Export

[English](#english) | [中文](#中文) | [日本語](#日本語)

---

## English

### Overview
A CLI tool that exports Claude Code sessions to clean, AI-readable Markdown files.

Claude Code stores conversations as JSONL files with UUID filenames. When a session hits the context limit, there's no easy way to identify which session is which or share the context with another AI tool. This tool converts them into readable Markdown with human-friendly filenames.

### Features
- **Interactive session picker** - Browse sessions with timestamps, message counts, and names
- **Session name support** - Shows names set by `/rename` instead of random UUIDs
- **Subagent support** - Includes subagent conversations stored in separate files
- **Plan file integration** - Embeds plan files written during the session
- **Smart file splitting** - Auto-splits large sessions to stay within Claude's read token limit (~1200 lines/file)
- **Local time display** - Converts UTC timestamps to your system's local time
- **No dependencies** - Standard library only

### System Requirements
- **OS**: Windows / macOS / Linux
- **Python**: 3.6 or higher
- **Dependencies**: None (standard library only)

### Installation

Clone the repository and run directly — no setup required.

```bash
git clone https://github.com/kiririto/claude-session-export.git
cd claude-session-export
python export_session.py
```

### Usage

On Windows, you can use `export_session.bat` instead of `python export_session.py`:

```bat
export_session.bat
export_session.bat --list
export_session.bat "keyword"
export_session.bat --all -o D:\exports
```

Or with Python directly:

```bash
# Interactive session picker
python export_session.py

# List all sessions
python export_session.py --list

# Export by title keyword or UUID prefix
python export_session.py "keyword"
python export_session.py 7e4893f8

# Export all sessions
python export_session.py --all

# Specify output directory
python export_session.py --all -o D:\exports
```

### Output
Files are saved to your system Downloads folder by default.
Filename format: `YYYY-MM-DD_HH-MM_first-message-title_ctx.md`

### License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 中文

### 概述
将 Claude Code 会话导出为简洁、AI 可读的 Markdown 文件的 CLI 工具。

Claude Code 以 UUID 文件名的 JSONL 格式存储对话，当会话达到上下文限制时，很难识别是哪个会话，也无法方便地将内容传递给其他 AI 工具。本工具将其转换为带有易读文件名的 Markdown 文件。

### 功能特性
- **交互式会话选择器** - 浏览带有时间戳、消息数和名称的会话列表
- **会话名称支持** - 显示通过 `/rename` 设置的名称，而非随机 UUID
- **子代理支持** - 包含存储在独立文件中的子代理对话内容
- **计划文件整合** - 嵌入会话过程中写入的计划文件
- **智能文件分割** - 自动分割大型会话以适配 Claude 的读取限制（约 1200 行/文件）
- **本地时间显示** - 将 UTC 时间戳转换为系统本地时间
- **无需依赖** - 仅使用 Python 标准库

### 系统要求
- **操作系统**: Windows / macOS / Linux
- **Python**: 3.6 或更高版本
- **依赖**: 无（仅使用标准库）

### 安装

克隆仓库后直接运行，无需任何配置。

```bash
git clone https://github.com/kiririto/claude-session-export.git
cd claude-session-export
python export_session.py
```

### 使用方法

Windows 用户可以直接使用 `export_session.bat`，无需输入 `python`：

```bat
export_session.bat
export_session.bat --list
export_session.bat "关键词"
export_session.bat --all -o D:\exports
```

或直接用 Python 运行：

```bash
# 交互式会话选择
python export_session.py

# 列出所有会话
python export_session.py --list

# 按标题关键词或 UUID 前缀导出
python export_session.py "关键词"
python export_session.py 7e4893f8

# 导出所有会话
python export_session.py --all

# 指定输出目录
python export_session.py --all -o D:\exports
```

### 输出
默认保存到系统的下载文件夹。
文件名格式：`YYYY-MM-DD_HH-MM_首条消息标题_ctx.md`

### 许可证
本项目使用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 日本語

### 概要
Claude Code のセッションをクリーンで AI が読みやすい Markdown ファイルにエクスポートする CLI ツールです。

Claude Code は会話を UUID ファイル名の JSONL 形式で保存します。セッションがコンテキスト上限に達したとき、どのセッションがどれかを判別したり、内容を別の AI ツールに渡したりする手段がありません。このツールはそれを読みやすいファイル名の Markdown に変換します。

### 機能
- **インタラクティブなセッション選択** - タイムスタンプ・メッセージ数・名前付きでセッションを一覧表示
- **セッション名のサポート** - ランダムな UUID ではなく `/rename` で設定した名前を表示
- **サブエージェント対応** - 別ファイルに保存されているサブエージェントの会話も含める
- **プランファイルの統合** - セッション中に書き込まれたプランファイルを埋め込み
- **自動ファイル分割** - Claude の読み取りトークン制限に収まるよう大きなセッションを自動分割（約 1200 行/ファイル）
- **ローカル時刻表示** - UTC タイムスタンプをシステムのローカル時刻に変換
- **依存関係なし** - Python 標準ライブラリのみ使用

### システム要件
- **OS**: Windows / macOS / Linux
- **Python**: 3.6 以上
- **依存関係**: なし（標準ライブラリのみ）

### インストール

リポジトリをクローンしてそのまま実行できます。セットアップ不要です。

```bash
git clone https://github.com/kiririto/claude-session-export.git
cd claude-session-export
python export_session.py
```

### 使い方

Windows では `export_session.bat` を使えば `python` を省略できます：

```bat
export_session.bat
export_session.bat --list
export_session.bat "キーワード"
export_session.bat --all -o D:\exports
```

または Python で直接実行：

```bash
# インタラクティブなセッション選択
python export_session.py

# 全セッションを一覧表示
python export_session.py --list

# タイトルキーワードまたは UUID プレフィックスでエクスポート
python export_session.py "キーワード"
python export_session.py 7e4893f8

# 全セッションをエクスポート
python export_session.py --all

# 出力ディレクトリを指定
python export_session.py --all -o D:\exports
```

### 出力
デフォルトの保存先はシステムのダウンロードフォルダです。
ファイル名形式：`YYYY-MM-DD_HH-MM_最初のメッセージタイトル_ctx.md`

### ライセンス
このプロジェクトは MIT ライセンスの下で公開されています - 詳細は [LICENSE](LICENSE) ファイルを参照してください。

---

## Contributing / 贡献 / コントリビュート

Issues and pull requests are welcome! / 欢迎提交 Issue 和 Pull Request！ / Issue と Pull Request を歓迎します！

## Author / 作者 / 作者

kiririto - [GitHub](https://github.com/kiririto)
