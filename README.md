# cc-trace

Claude Code のセッションログから**思考プロセス**だけを抽出し、Obsidian の Inbox に Markdown として書き出すツール。

## これは何？

Claude Code を使って開発していると、`~/.claude/projects/` に JSONL 形式のセッションログが蓄積されていきます。しかしこのログには、ストリーミングチャンク・ツール実行結果・内部メッセージなど大量のノイズが含まれており、後から「あのとき何を考えていたか」を振り返るには不向きです。

cc-trace は、このログから**対話の文脈**だけを抽出します。

- ユーザーの質問・指示
- Claude の思考過程（thinking）
- Claude のテキスト回答
- ツール使用の 1 行サマリー（コード本体は除去）

コードブロックは `[Code Block: python, 45 lines]` のようなプレースホルダーに置換され、「何を書いたか」ではなく「なぜ書いたか」が残ります。

## 前提: Claude Code のログ自動削除を無効化する

Claude Code は**デフォルトで 30 日経過したセッションログを起動時に自動削除**します。cc-trace で過去のログを処理するには、この削除を無効化する必要があります。

`~/.claude/settings.json` に `cleanupPeriodDays` を追加してください。

```json
{
  "cleanupPeriodDays": 99999
}
```

| 値 | 意味 |
|---|---|
| 未設定 | 30 日で削除（デフォルト） |
| `99999` | 実質無期限保持（推奨） |
| `0` | **全ログ即時削除（危険）** |

cc-trace の cron を設定していれば、仮に Claude Code がログを削除しても Obsidian 側に Markdown が残ります。ただし取りこぼしを防ぐため、`cleanupPeriodDays` の設定を推奨します。

## セットアップ

```bash
# リポジトリをクローン
git clone <repo-url> && cd cc-trace

# uv で依存解決（外部依存なし）
uv sync
```

Python 3.11 以上が必要です。外部ライブラリへの依存はありません。

## 使い方

### 手動同期

```bash
uv run cc-trace sync
```

`~/.claude/projects/` 配下の全セッションログを走査し、未処理のものを Obsidian Inbox に書き出します。

```bash
# 詳細ログを表示
uv run cc-trace sync --verbose

# 出力先を変更
uv run cc-trace sync --inbox ~/my-obsidian-vault/Inbox
```

### 自動実行（cron）

```bash
# 毎時 0 分に自動同期する cron ジョブを登録
uv run cc-trace cron --install

# cron ジョブを解除
uv run cc-trace cron --uninstall
```

cron のログは `~/.claude/cc-trace.log` に出力されます。

### 設定ファイル（任意）

`~/.config/cc-trace/config.toml` を作成すると、デフォルト値を変更できます。

```toml
obsidian_inbox = "~/my-vault/Inbox"
staleness_threshold = 600  # 秒（デフォルト: 300）
```

| 設定キー | デフォルト | 説明 |
|---|---|---|
| `claude_dir` | `~/.claude` | Claude Code のデータディレクトリ |
| `obsidian_inbox` | Google Drive 上の ikmx-memo | Markdown の出力先 |
| `state_file` | `~/.claude/cc-trace-state.json` | 処理済みファイルの追跡用 |
| `staleness_threshold` | `300` | 最終更新からこの秒数が経過したファイルのみ処理 |

## 出力例

生成される Markdown は以下のような形式です。

```markdown
---
created: 2026-02-02T06:08:52Z
tags:
  - log/claude
  - type/thought_trace
status: auto_generated
tokens: 25000
model: claude-opus-4-5-20251101
project: cc-trace
related_files:
  - src/main.py
  - tests/test_app.py
---

# Session: cc-trace (2026-02-02)

## 🧑 User
アプリケーションを開発してください...

## 🤖 Assistant

> [!thinking]- Thinking
> Let me analyze this task...
> The user wants a Python application that...

まず、プロジェクト構造を確認します。

> 🔧 Used **Read**: `src/main.py`
> 🔧 Used **Bash**: List files in current directory

処理結果は以下の通りです。

[Code Block: python, 45 lines]

このコードは...
```

ファイル名は `CC-{日付}-{プロジェクト名}-{セッションID先頭8文字}.md` の形式です。

## テスト

```bash
uv run pytest
```
