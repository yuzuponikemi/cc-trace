# Gemini MyActivity データ形式

Google Takeout の「マイ アクティビティ」→「Gemini アプリ」からエクスポートされる JSON ファイルの構造解析。

## 取得方法

1. [Google Takeout](https://takeout.google.com/) にアクセス
2. 「すべて選択を解除」→「**マイ アクティビティ**」だけをチェック
3. 「すべての履歴データが含まれます」→ フィルタで「**Gemini アプリ**」だけを選択
4. 形式を **JSON** に設定してエクスポート

**注意**: Takeout のリストにある「Gemini」を選んでも Gems 設定と Scheduled Actions しか出力されない。会話履歴は「マイ アクティビティ」の方に格納されている。

## ファイル概要

| 項目 | 値 |
|---|---|
| ファイル名 | `My Activity.json` |
| 形式 | JSON 配列（1 ファイルに全エントリ） |
| サイズ | 約 20MB（2,061 エントリの場合） |
| 期間 | 2024-10 〜 現在 |
| 並び順 | 新しい順（降順） |

## トップレベル構造

```json
[
  { ... entry ... },
  { ... entry ... },
  ...
]
```

配列の各要素が 1 つのアクティビティ（プロンプト、Canvas 作成、フィードバック等）。

## エントリのスキーマ

### 共通フィールド（全エントリに存在）

| フィールド | 型 | 説明 |
|---|---|---|
| `header` | `string` | 常に `"Gemini Apps"` |
| `title` | `string` | アクティビティの種類 + 内容（下記参照） |
| `time` | `string` | ISO 8601 タイムスタンプ（UTC） |
| `products` | `string[]` | 常に `["Gemini Apps"]` |
| `activityControls` | `string[]` | 常に `["Gemini Apps Activity"]` |

### オプショナルフィールド

| フィールド | 型 | 出現率 | 説明 |
|---|---|---|---|
| `safeHtmlItem` | `object[]` | 96% | Gemini の回答（HTML 形式） |
| `subtitles` | `object[]` | 9% | 使用された Gem、添付ファイル等の補足情報 |
| `attachedFiles` | (不明) | 3% | 添付ファイルがある場合 |
| `imageFile` | `string` | 3% | 添付画像のファイル名 |

## title フィールドのパターン

`title` の先頭キーワードでアクティビティの種類が判別できる。

| プレフィックス | 件数 | 説明 |
|---|---|---|
| `Prompted ...` | 1,972 | ユーザーのプロンプト入力。`Prompted ` の後にプロンプト全文が続く |
| `Created ...` | 68 | Canvas やドキュメントの作成 |
| `Used ...` | 6 | Assistant 機能の使用 |
| `Selected preferred draft` | 8 | 複数の回答候補から選択した操作 |
| `Gave feedback: Good response` | 7 | 回答への「良い回答」フィードバック |

### Prompted エントリの例

```json
{
  "header": "Gemini Apps",
  "title": "Prompted claude codeなどのエージェントを使うとき、日本語で会話するのか...",
  "time": "2026-02-02T07:24:02.806Z",
  "products": ["Gemini Apps"],
  "activityControls": ["Gemini Apps Activity"],
  "safeHtmlItem": [
    {
      "html": "<p>結論から申し上げますと、<strong>英語で会話する方が...</strong></p>..."
    }
  ]
}
```

- `title` から `Prompted ` プレフィックスを除去するとユーザーのプロンプトになる
- `safeHtmlItem[0].html` が Gemini の回答（HTML）
- 1,972 件中 1,971 件に回答が付いている（1 件のみ回答なし）

### safeHtmlItem が複数ある場合

```json
"safeHtmlItem": [
  { "html": "<p>最初の回答...</p>" },
  { "html": "<p>再生成された回答...</p>" }
]
```

回答の再生成（Regenerate）が行われた場合、複数の回答が記録される。29 件が該当（24 件が 2 つ、3 件が 3 つ、1 件が 4 つ、1 件が 5 つ）。

## subtitles のパターン

`subtitles` は補足的なメタデータを格納する配列。

### Gem（カスタム AI）使用時

```json
"subtitles": [
  {
    "name": "RonbunOchiAI3 was used in this chat. Manage your Gems.",
    "url": "https://gemini.google.com/gems/..."
  }
]
```

よく使われている Gem:
- `RonbunOchiAI3` (16 回)
- `RonbunOchiai` (13 回)
- `統計学勉強クイズ作成` (9 回)
- `編集工学の達人` (6 回)

### ファイル添付時

```json
"subtitles": [
  { "name": "Attached 1 file." },
  { "name": "-  image_89b1bd.png", "url": "image_89b1bd-1e9873211d1a6157.png" }
],
"imageFile": "image_89b1bd-1e9873211d1a6157.png"
```

### YouTube URL が含まれる場合

```json
"subtitles": [
  { "name": "http://googleusercontent.com/youtube_content/10" }
]
```

## 月別エントリ数

```
2024-10:   2
2024-12:   2
2025-05: 103
2025-06: 122
2025-07:  92
2025-08: 280
2025-09: 330
2025-10: 233
2025-11: 237
2025-12: 217
2026-01: 401
2026-02:  42
```

## cc-trace との統合に向けた考慮点

- **Claude Code ログとの違い**: Gemini のデータは「1 プロンプト = 1 エントリ」の独立した構造。Claude Code のような複数ターンのセッション概念はなく、会話の連続性（どのプロンプトが同一会話に属するか）の情報が**含まれていない**。
- **回答は HTML**: `safeHtmlItem.html` は構造化 HTML（見出し、リスト、テーブル、コードブロック含む）。Markdown への変換が必要。
- **プロンプトは title 内**: `title` フィールドから `Prompted ` プレフィックスを除去して取得する。
- **時系列の並び**: 降順（新しい順）なので、処理時に逆順にする必要がある。
- **画像ファイル**: `imageFile` で参照されるファイルは Takeout の ZIP 内に同梱される。Markdown 変換時はファイル名の参照のみ残す形が現実的。
