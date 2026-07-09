# Snyk MCP デモ — `snyk_breakability_check`

> **新機能:** `snyk_breakability_check` は、依存関係のアップグレードに対して
> **破壊的変更（breaking-change）の評価** を実行する Snyk MCP ツールです。Snyk が推奨する修正
> （`Upgrade to <pkg>@<version>`）を受け入れる前に、このツールはそのジャンプがどれだけ
> リスキーであるか — どの API が削除されたか、ランタイム/OS の下限がどう変わったか、そして
> 一気にアップグレードするのではなく段階的にアップグレードすべきかどうか — を教えてくれます。
> **`low`**、**`medium`**、または **`high`** の `risk_level` を返します。
>
> その価値: Snyk SCA は **脆弱性を解消するために何にアップグレードすべきか** を教えてくれます。
> `snyk_breakability_check` は **そのアップグレードがアプリを壊すかどうか** を教えてくれます。
> 両者を組み合わせることで、「47 件の脆弱性があります」という状態を、優先順位付けされ、リスクを
> 認識した修復プランへと変えられます — そして何より重要なのは、常に最新のメジャーバージョンに
> 飛びつくのではなく、**最小で安全な修正** を見つける手助けをしてくれることです。

- **対象読者:** オープンソースの脆弱性を修復する開発者および DevOps エンジニア。
- **この実行で使用した環境:** Snyk MCP `v1.1305.2`、プロジェクト `uv-goof/simple`（Python / `uv`）。
- **前提条件:** エージェント/IDE に Snyk MCP サーバーが接続され、認証済みであること
  （`snyk_auth`）、およびプロジェクトのパッケージマネージャがインストールされていること（ここでは: Python + `uv`）。

---

## ワークフローの概要

```
 ┌──────────────────┐      ┌──────────────────────────┐      ┌────────────────────┐
 │ 1. snyk_sca_scan │  ──▶ │ pick a handful of the     │  ──▶ │ 2. snyk_breakability│
 │  (find issues +   │      │ candidate upgrades        │      │    _check per upgrade │
 │   fix versions)   │      │ (from → to versions)      │      │  (assess the risk)  │
 └──────────────────┘      └──────────────────────────┘      └────────────────────┘
                                                                       │
                        low  ─▶ safe to apply / auto-merge  ◀──────────┤
                        med  ─▶ apply + test the noted behavior change ◀┤
                        high ─▶ plan a staged upgrade / smaller target ◀┘
```

---

## ステップ 1 — `snyk_sca_scan` を実行する

プロジェクトをスキャンして、オープンソース（SCA）の脆弱性を検出します。各問題には、
**現在のバージョン**、**`fixedIn`** バージョンのリスト、および **`remediation`** の
アップグレード対象が含まれます — これらがステップ 2 に渡す入力となります。

**ツール呼び出し**

```jsonc
// tool: snyk_sca_scan
{
  "path": "/absolute/path/to/uv-goof/simple",  // MUST be an absolute path
  "command": "python3",                          // REQUIRED for Python projects
  "severity_threshold": "high"                   // focus on high + critical
}
```

> 注記:
> - `path` は **絶対パス** でなければなりません（`pwd` を実行して取得してください）。
> - Python の場合は `command`（Python 実行可能ファイル）を渡す **必要があります**。
> - `severity_threshold` はオプションです。ここではデモを絞り込むために使用しています。

**結果（抜粋）:** `47` 件の high/critical の問題。代表的な一部を示します — ほとんどの
パッケージが最新のものだけでなく、**複数の** `fixedIn` バージョンをリストしていることに注目してください。

| パッケージ | 現在 | `fixedIn` オプション（一部） | `remediation`（デフォルトの対象） | 問題の例 | 重大度 |
|---|---|---|---|---|
| django  | 2.2    | `2.2.22`, `2.2.28`, `3.2.14`, `4.2.15`, `4.2.17` | `django@4.2.17` | Command Injection (CVE-2024-53907) / SQLi | high / critical |
| urllib3 | 1.24.3 | `1.25.9`, `2.6.0`, `2.6.3` | `urllib3@2.6.3` | Data Amplification (CVE-2026-21441) | high |
| pyyaml  | 5.3.1  | `5.4` | `pyyaml@5.4` | Arbitrary Code Execution (CVE-2020-14343) | critical |
| flask   | 1.1.2  | `2.2.5`, `2.3.2` | `flask@2.2.5` | Information Exposure (CVE-2023-30861) | high |
| pyjwt   | 1.5.3  | `2.4.0`, `2.12.0`, `2.13.0` | `pyjwt@2.13.0` | Improper Authentication (CVE-2026-48526) | high |
| pillow  | 10.4.0 | `12.1.1`, `12.2.0`, `12.3.0` | `pillow@12.3.0` | Memory Allocation w/ Excessive Size | high |

`remediation` フィールドは通常、**メジャーバージョンのジャンプ** を指し示します。それは
最もリスキーな選択肢です — だからこそ、それを受け入れる前にブレーカビリティチェックを実行すべきであり、
多くの場合 **より小さい `fixedIn` の対象** も併せて確認すべきなのです。

---

## ステップ 2 — いくつかの問題に対して `snyk_breakability_check` を実行する

ステップ 1 のパッケージ名と **from → to** のバージョンを指定してツールを呼び出します。
ここでは、混合したケースをチェックします: **デフォルト（メジャー）の `remediation` 対象** と、
いくつかのパッケージについては、CVE を解消しつつも **同一メジャー内のより小さい `fixedIn` 対象** です。

**ツール呼び出し（すべて並列で実行可能）:**

```jsonc
// tool: snyk_breakability_check

// --- default remediation targets (the newest major) ---
{ "package_name": "django",  "package_version_from": "2.2",    "package_version_to": "4.2.17" }
{ "package_name": "urllib3", "package_version_from": "1.24.3", "package_version_to": "2.6.3"  }
{ "package_name": "flask",   "package_version_from": "1.1.2",  "package_version_to": "2.2.5"  }
{ "package_name": "pyjwt",   "package_version_from": "1.5.3",  "package_version_to": "2.13.0" }
{ "package_name": "pillow",  "package_version_from": "10.4.0", "package_version_to": "12.3.0" }

// --- smaller same-major targets that STILL fix a vulnerability ---
{ "package_name": "django",  "package_version_from": "2.2",    "package_version_to": "2.2.28" }
{ "package_name": "django",  "package_version_from": "2.2",    "package_version_to": "2.2.22" }
{ "package_name": "urllib3", "package_version_from": "1.24.3", "package_version_to": "1.25.9" }
{ "package_name": "pyyaml",  "package_version_from": "5.3.1",  "package_version_to": "5.4"    }
```

> 引数リファレンス:
> - `package_name` — 評価するパッケージ。スコープ付き npm の場合は `@scope/name` を、
>   Maven の場合は `groupId:artifactId` を使用します。
> - `package_version_from` — アップグレード **前** のバージョン（現在のバージョン）。
> - `package_version_to` — アップグレード **後** のバージョン（`fixedIn` の対象）。

---

### 2a. JSON 形式の結果

各呼び出しは、`risk_level`（`low` / `medium` / `high`）、Markdown の `assessment`、および
`instructions` フィールド（エージェントがどう進めるかについてのガイダンス）を返します。
`instructions` がリスクレベルによってどう異なるかに注目してください。

```json
[
  {
    "package": "django", "from": "2.2", "to": "2.2.28",
    "risk_level": "low",
    "assessment": "Patch version upgrade within the 2.2 LTS series — bug fixes and security patches only. 2.2.28 addresses two high-severity SQL injection vulnerabilities (CVE-2022-28346 and CVE-2022-28347). As a patch release it is designed to be fully backward-compatible with no breaking API changes.",
    "instructions": "Non-breaking change, proceed with the upgrade."
  },
  {
    "package": "django", "from": "2.2", "to": "2.2.22",
    "risk_level": "low",
    "assessment": "Patch version upgrade within the same LTS series. Django's versioning policy states patch releases are for security and bug fixes only and contain no backward-incompatible changes. 2.2.22 fixed a potential HTTP header injection vulnerability. No breaking API changes documented for this path.",
    "instructions": "Non-breaking change, proceed with the upgrade."
  },
  {
    "package": "urllib3", "from": "1.24.3", "to": "1.25.9",
    "risk_level": "medium",
    "assessment": "Behavioral change requiring verification. From 1.25.0, urllib3 enables TLS certificate verification by default for all HTTPS requests. Connections to servers with invalid or self-signed certificates that previously succeeded will now fail with SSLError unless explicitly configured. Verify all HTTPS endpoints present valid, trusted certificates before upgrading.",
    "instructions": "Check the assessment and determine if the change is breaking or not. If it is breaking, inform the user of the breaking change first. Otherwise, proceed with the upgrade."
  },
  {
    "package": "pyyaml", "from": "5.3.1", "to": "5.4",
    "risk_level": "medium",
    "assessment": "Minor version upgrade. No documented runtime API breaking changes, but 5.4 has known installation issues from a deprecated license_file packaging parameter that can cause build failures with newer setuptools. Verify the package installs correctly in your build/deploy environments.",
    "instructions": "Check the assessment and determine if the change is breaking or not. If it is breaking, inform the user of the breaking change first. Otherwise, proceed with the upgrade."
  },
  {
    "package": "django", "from": "2.2", "to": "4.2.17",
    "risk_level": "high",
    "assessment": "Major upgrade across two LTS versions (2.2 → 4.2) with numerous breaking changes. Drops Python 3.6/3.7 (needs 3.8+). Drops older DBs (Django 4.2 needs PostgreSQL 12+, drops MySQL 5.7 / MariaDB 10.3). Removed APIs: ugettext* → gettext*, force_text/smart_text → force_str/smart_str, postgresql_psycopg2 backend path → postgresql. Removed {% load staticfiles %}. Timezone default pytz → zoneinfo. DEFAULT_AUTO_FIELD, CSRF_TRUSTED_ORIGINS (now needs scheme), DEFAULT_FILE_STORAGE → STORAGES. Recommend incremental upgrade 2.2 → 3.2 → 4.2.",
    "instructions": "IMPORTANT: Breaking change detected. If Snyk reported another upgrade path that is non-breaking use it. Otherwise, inform the user of the breaking change first."
  },
  {
    "package": "urllib3", "from": "1.24.3", "to": "2.6.3",
    "risk_level": "high",
    "assessment": "Major 1.x → 2.x upgrade. Drops Python < 3.10 and OpenSSL < 1.1.1 (impacts RHEL 7/8, older OSes). Removed APIs: HTTPResponse.getheaders()/getheader() → response.headers; HTTPConnection.request_chunked() → request(chunked=True). Stricter defaults: min TLS now 1.2, hostname verification uses subjectAltName only. Removed modules: urllib3.contrib.ntlmpool, urllib3.contrib.securetransport.",
    "instructions": "IMPORTANT: Breaking change detected. If Snyk reported another upgrade path that is non-breaking use it. Otherwise, inform the user of the breaking change first."
  },
  {
    "package": "flask", "from": "1.1.2", "to": "2.2.5",
    "risk_level": "high",
    "assessment": "Major version jump. Drops Python 2 and 3.5 (needs 3.6+). app.config.from_json() removed → from_file(). send_file/send_from_directory params renamed: attachment_filename → download_name, cache_timeout → max_age, filename → path. Core deps bumped (Werkzeug 2.x, Jinja 3.x). Switched to contextvars, deprecating _app_ctx_stack/_request_ctx_stack (affects older extensions).",
    "instructions": "IMPORTANT: Breaking change detected. If Snyk reported another upgrade path that is non-breaking use it. Otherwise, inform the user of the breaking change first."
  },
  {
    "package": "pyjwt", "from": "1.5.3", "to": "2.13.0",
    "risk_level": "high",
    "assessment": "Major 1.x → 2.x upgrade with mandatory code changes. jwt.decode() now requires the algorithms parameter (calls without it fail). Drops Python 2.7 and < 3.6 (2.13.0 needs 3.9+). Removed deprecated verify_expiration/verify params. require_* options consolidated into options={'require': [...]}. Dropped PyCrypto and ecdsa backends in favor of cryptography>=3.",
    "instructions": "IMPORTANT: Breaking change detected. If Snyk reported another upgrade path that is non-breaking use it. Otherwise, inform the user of the breaking change first."
  },
  {
    "package": "pillow", "from": "10.4.0", "to": "12.3.0",
    "risk_level": "high",
    "assessment": "Major upgrade 10 → 12. Pillow 11 dropped Python 3.8; Pillow 12 dropped Python 3.9 (needs 3.10+). ImageCms constants (e.g. ImageCms.FLAGS['MATRIXINPUT']) removed in 12.0.0, replaced by ImageCms.Flags class. Removed internal helpers: PSFile, PyAccess, Image.USE_CFFI_ACCESS, IptcImageFile helpers. Dropped FreeType <= 2.9.0.",
    "instructions": "IMPORTANT: Breaking change detected. If Snyk reported another upgrade path that is non-breaking use it. Otherwise, inform the user of the breaking change first."
  }
]
```

---

### 2b. 人間が読みやすい形式の結果

**サマリー — リスク順にソート（低い順）**

| パッケージ | アップグレード | リスク | 意味 | 推奨アクション |
|---|---|---|---|---|
| 🟢 django  | 2.2 → 2.2.28    | **Low**    | 2.2 LTS 内のパッチ。重大な SQLi を修正、API 変更なし | 適用 — 自動マージして安全 |
| 🟢 django  | 2.2 → 2.2.22    | **Low**    | 2.2 LTS 内のパッチ。ヘッダインジェクションを修正、API 変更なし | 適用 — 自動マージして安全 |
| 🟡 urllib3 | 1.24.3 → 1.25.9 | **Medium** | TLS 証明書検証がデフォルトで有効に | 適用後、HTTPS エンドポイントの証明書が有効かテスト |
| 🟡 pyyaml  | 5.3.1 → 5.4     | **Medium** | API の破壊なし。ただしパッケージングのバグでビルドが失敗する可能性 | 適用後、CI でインストールできるか検証 |
| 🔴 django  | 2.2 → 4.2.17    | **High**   | LTS を2つ飛ぶ。API 削除、DB と Python の下限 | 上記の 2.2.x パッチを優先。それ以外は 2.2→3.2→4.2 と段階的に |
| 🔴 urllib3 | 1.24.3 → 2.6.3  | **High**   | 1.x→2.x。Python 3.10+/OpenSSL 1.1.1+、TLS 1.2 が最小 | 1.25.9 を優先。それ以外はランタイム + 削除された API を監査 |
| 🔴 flask   | 1.1.2 → 2.2.5   | **High**   | `send_file` パラメータのリネーム、Werkzeug/Jinja のバンプ | 呼び出しを更新し、拡張機能をテスト |
| 🔴 pyjwt   | 1.5.3 → 2.13.0  | **High**   | `jwt.decode()` に `algorithms` が必須に | すべての decode に `algorithms=[...]` を追加 |
| 🔴 pillow  | 10.4.0 → 12.3.0 | **High**   | `ImageCms` 定数が削除、Python 3.10+ | `ImageCms.Flags` に移行、Python を検証 |

> **要点の教訓。** *同じ* 脆弱な `django 2.2` が、**非常に異なるリスク** で **3回** 登場します:
> デフォルトの `remediation` 対象（`4.2.17`）は 🔴 **high** ですが、より小さい `2.2.28` / `2.2.22`
> のパッチ対象は 🟢 **low** です — しかもこれらは実際の CVE をしっかり解消します。ブレーカビリティに
> よって、盲目的に最新のメジャーを選ぶのではなく、**最小で安全な修正** を選べるようになります。

**詳細 — 低リスク（適用して安全）**

- **django 2.2 → 2.2.28 — 🟢 Low。** 2.2 LTS シリーズ内のパッチリリース。
  セキュリティ/バグ修正のみ。2件の high 重大度の SQL インジェクション問題
  （CVE-2022-28346、CVE-2022-28347）を解消します。完全に後方互換で、API 変更なし。
  → `instructions`: *"Non-breaking change, proceed with the upgrade."*
- **django 2.2 → 2.2.22 — 🟢 Low。** 同一 LTS シリーズ内のパッチリリース。
  Django のバージョニングポリシーに従い、後方互換性のない変更はありません。HTTP
  ヘッダインジェクションの脆弱性を修正します。
  → `instructions`: *"Non-breaking change, proceed with the upgrade."*

**詳細 — 中リスク（適用するが、指摘された変更を検証すること）**

- **urllib3 1.24.3 → 1.25.9 — 🟡 Medium。** API の削除はありませんが、1.25.0 から TLS
  証明書検証が **デフォルトで有効** になります。以前は通っていた、無効/自己署名証明書を持つ
  エンドポイントへのリクエストは、`SSLError` を発生させるようになります。展開前に、
  すべての HTTPS 対象が有効な証明書を持つことを確認してください。
- **pyyaml 5.3.1 → 5.4 — 🟡 Medium。** 文書化されたランタイム API の破壊はありませんが、5.4 には
  既知のパッケージング問題（非推奨の `license_file`）があり、新しい `setuptools` でビルドが
  壊れる可能性があります。CI でクリーンにインストールできることを検証してください。

**詳細 — 高リスク（計画する / より小さい対象を優先する）**

- **django 2.2 → 4.2.17 — 🔴 High。** 2つの LTS リリースにまたがります。Python 3.8+ と
  新しい DB が必要です（PostgreSQL 12+。MySQL 5.7 / MariaDB 10.3 を廃止）。`ugettext*`、
  `force_text`/`smart_text`、`postgresql_psycopg2` のパス、および `{% load staticfiles %}` を
  削除。タイムゾーンを `pytz` → `zoneinfo` に切り替え。`DEFAULT_AUTO_FIELD`、
  `CSRF_TRUSTED_ORIGINS`、`DEFAULT_FILE_STORAGE` → `STORAGES` を変更。
  Django 4.x が特に必要でない限り、上記の 🟢 `2.2.28` パッチを **優先** してください。
  そうでない場合は、2.2 → 3.2 → 4.2 と段階的にアップグレードしてください。
- **urllib3 1.24.3 → 2.6.3 — 🔴 High。** メジャー 1.x → 2.x。Python 3.10+ と
  OpenSSL 1.1.1+ が必要です。`getheaders()`/`getheader()` は削除（`response.headers` を使用）。
  `request_chunked()` → `request(chunked=True)`。TLS 最小 1.2。`subjectAltName` のみの
  検証。`contrib.ntlmpool`/`contrib.securetransport` は削除。
  あなたの CVE を解消するなら 🟡 `1.25.9` 対象を **優先** してください。
- **flask 1.1.2 → 2.2.5 — 🔴 High。** Python 2 / 3.5 を廃止。`from_json()` は削除
  （`from_file()` を使用）。`send_file`/`send_from_directory` のパラメータをリネーム
  （`attachment_filename`→`download_name`、`cache_timeout`→`max_age`、
  `filename`→`path`）。Werkzeug 2.x / Jinja 3.x を取り込む。`contextvars` に切り替え
  （古い拡張機能を壊す可能性）。
- **pyjwt 1.5.3 → 2.13.0 — 🔴 High。** `jwt.decode()` に `algorithms` 引数が
  **必須** になりました — それがない既存の呼び出しは失敗します。`verify_expiration`/`verify` を
  削除。`require_*` は `options={"require": [...]}` に統合。Python 3.9+ と
  `cryptography>=3` が必要です。
- **pillow 10.4.0 → 12.3.0 — 🔴 High。** Python 3.10+ が必要です（11 が 3.8 を、12 が
  3.9 を廃止）。`ImageCms` 定数（例: `ImageCms.FLAGS['MATRIXINPUT']`）は
  `ImageCms.Flags` に置き換えられて削除。内部ヘルパー（`PSFile`、`PyAccess`、
  `Image.USE_CFFI_ACCESS`）は削除。

---

## 結果に基づいて行動する方法

1. **`risk_level` に決定を委ねる:**
   - 🟢 **low** → `instructions` は *"Non-breaking change, proceed."* と伝えます。
     修正を適用して自動マージして安全です。
   - 🟡 **medium** → 適用しますが、assessment が指摘する **特定の挙動をテスト** してください
     （例: urllib3 の証明書検証、pyyaml のビルド）。
   - 🔴 **high** → `instructions` は *まずユーザーに知らせる / 破壊的でないパスを優先する* と
     伝えます。人間によるレビュー、テスト、または段階的なアップグレードが必要です。
2. **CVE を解消できる最小の `fixedIn` 対象を優先する。** 示したとおり、`django@2.2.28`（🟢 low）は、
   `django@4.2.17`（🔴 high）でも修正できる重大な SQLi を修正します — しかも破壊は一切ありません。
   選択する前に、より小さい対象に対して `snyk_breakability_check` を再実行して確認してください。
3. 本当に必要な `high` リスクのメジャーについては、**複数ステップのアップグレードを計画する**
   （例: django 2.2 → 3.2 → 4.2）。
4. **CI でゲートする:** `low` は自動マージ、`medium` はテスト実行を必須にし、
   `high` は人間によるレビューを必須にします。

---

## このデモを再現する

1. Snyk MCP サーバーが接続され、認証されていることを確認します
   （ツールが未認証と報告する場合は `snyk_auth` を実行）。
2. **絶対** `path` と（Python の場合）`command: python3` を指定して `snyk_sca_scan` を実行します。
3. 結果から、いくつかのアップグレードを選びます。それぞれについて、現在のバージョン **と**
   完全な `fixedIn` リストを記録します — 最新のメジャーと、より小さい同一メジャーの対象の
   両方を含めます。
4. 候補ごとに `package_name`、`package_version_from`、`package_version_to` を指定して
   `snyk_breakability_check` を1回呼び出します。
5. 対象間で `risk_level` を比較し、**最小で安全な修正** を選びます。

---

*2026-07-08 に `uv-goof/simple` に対して Snyk MCP `v1.1305.2` で実行したライブ実行から生成。上記のすべての `risk_level` 値と assessment は、実際のツール出力です。*
