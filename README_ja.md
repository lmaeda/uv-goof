# uv-goof — Snyk トレーニングガイド

このリポジトリには、意図的に脆弱性を含んだ [`uv`](https://docs.astral.sh/uv/)
Python プロジェクトが多数含まれています。これは、**顧客チーム向けのハンズオン・トレーニングトラック**として、最新の
Snyk 開発者ワークフローを学ぶために使用されます。具体的には、CLI からのスキャン、IDE 拡張機能での新規（net-new）問題の確認、
エディタ内での SAST 検出結果の修正、そして AI コーディングアシスタントから `/snyk-fix` を使って
**Snyk Remediation Agent**（Snyk Studio Recipes）を動かすワークフローです。

> ⚠️ **ここにあるコードは意図的に安全ではありません。** これはトレーニング用の検出結果を生成するためだけに存在します。
> 決してデプロイせず、そのパターンを実際のプロジェクトにコピーしないでください。

このガイドの大部分では [`simple/`](./simple) プロジェクトを使用します。このプロジェクトは、既知の脆弱性を含む依存関係
（SCA）を `pyproject.toml` に固定（ピン留め）し、意図的に脆弱な Python ソースコード（SAST）を
`vulnerable.py` と `app.py` に同梱しています。

---

## 前提条件

セッションの前に、以下を一度だけインストールしてください。

| ツール | 目的 | インストール方法 |
|---|---|---|
| **git** | リポジトリのクローン | ほとんどのシステムにプリインストール済み |
| **uv** | Python プロジェクトのビルド/実行 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Snyk CLI** | コマンドラインでのスキャン | `npm i -g snyk` または `brew install snyk` |
| **Snyk IDE 拡張機能** | エディタ内スキャン + 新規（net-new）ビュー | VS Code Marketplace → "Snyk Security" |
| **GitHub CLI (`gh`)** | PR チェックのステップ（[11](#11-snyk-pr-チェックをテストするために-pr-を開く)–[12](#12-pr-をマージしてチェックを評価する)）での PR の作成/マージ。また `/snyk-fix` が PR を開く方法でもある | `brew install gh` または [cli.github.com](https://cli.github.com) を参照。その後 `gh auth login` |
| **AI アシスタント** | `/snyk-fix` レシピの実行 | GitHub Copilot CLI **または** Claude Code / Cursor |
| **Snyk Studio Recipes** | `/snyk-fix` スキル + MCP 連携 | [ステップ 6](#6-実験的snyk-remediation-agentmcp--copilot-cli-経由) を参照 |

> **GitHub アクセス。** `gh` は、PR チェックのステップと `/snyk-fix` の PR 作成に必要な基本要件です。
> アシスタント内から自然言語で PR を操作したい場合は、オプションで **GitHub MCP サーバー** を
> 設定することもできます — [ステップ 11](#11-snyk-pr-チェックをテストするために-pr-を開く) の注記を参照してください。

また、Snyk アカウント（無料プランで問題ありません）が必要です。`simple/` プロジェクトは、
`.vscode/settings.json` を介してトレーニング用の組織（org）に事前設定されています。

```json
{
  "snyk.advanced.organization": "cdc6bc3b-f914-4a3d-b52c-a45147a46643",
  "snyk.advanced.autoSelectOrganization": true
}
```

---

## 1. プロジェクトをクローンし、トレーニング用ベースブランチを作成する

### 1a. クローンする（ブランチ `ai-agent-snyk-fix`）

```bash
git clone git@github.com:lmaeda/uv-goof.git
cd uv-goof
git checkout ai-agent-snyk-fix

# トレーニング用ブランチにいることを確認する
git branch --show-current      # -> ai-agent-snyk-fix
```

> HTTPS を使う場合: `git clone --branch ai-agent-snyk-fix https://github.com/lmaeda/uv-goof.git`

### 1b. 日付付きのトレーニング用ベースブランチを作成する

各実施回ごとに、専用の**トレーニング用ベースブランチ**を用意します。これは `ai-agent-snyk-fix` から
切り出し、サフィックス `YYYYMMDD_base` を付けます。こうすることで、各セッション（および各トレーナー）が
互いに独立します。修正ブランチはこのブランチから切り出し、修正 PR もこのブランチにマージし直すため、
`ai-agent-snyk-fix` は正規の出発点としてクリーンなまま保たれます。

```bash
# 例: ai-agent-snyk-fix_20260709_base
export TRAIN_BASE="ai-agent-snyk-fix_$(date +%Y%m%d)_base"

git checkout -b "$TRAIN_BASE"
git push -u origin "$TRAIN_BASE"

git branch --show-current      # -> ai-agent-snyk-fix_<今日の日付>_base
```

> ステップ 11〜12 で `$TRAIN_BASE` が設定されたままになるよう、このターミナルを開いたままにしてください。
> 新しいシェルでは、上記の `export` 行を再実行してください（またはブランチ名のリテラルに置き換えます）。

---

## 2. プロジェクトをビルドする

このガイドのすべての作業は `simple/` プロジェクト内で行われます。

```bash
cd simple

# （意図的に脆弱な）依存関係を解決し、ローカルの venv にインストールする。
# uv は pyproject.toml を読み込み、すべてを uv.lock に固定する。
uv sync

# プロジェクトが動作するか確認する。
uv run python main.py          # -> Hello from simple-project!
```

これで `simple/.venv/` に脆弱な依存関係ツリーが構築されました — これはまさに Snyk が
解析する対象です。

> オプション: 意図的に脆弱な Flask アプリを実行して、SAST のシンクを
> `http://127.0.0.1:5000`（`/user`、`/ping`、`/greet` などのルート）で実際に確認できます:
> `uv run python app.py`

---

## 3. Snyk スキャンを実行する（CLI）

一度認証を行い、`simple/` 内から両方のスキャンタイプを実行します。

```bash
# CLI を認証する（ブラウザが開きます）。
snyk auth

# --- SCA: オープンソース依存関係の脆弱性（pyproject.toml / uv.lock を読み込む） ---
snyk test

# --- SAST: ファーストパーティコードの脆弱性（Snyk Code） ---
snyk code test
```

期待される結果:

- `snyk test` は、固定された依存関係全体の脆弱性を報告します — `urllib3 1.24.3`、
  `jinja2 2.11.2`、`flask 1.1.2`、`requests 2.20.0`、`pyyaml 5.3.1`、`pyjwt 1.5.3`、
  `cryptography 2.3`、`pillow 10.4.0`、`django 2.2.0`、`lxml 5.3.0`、`ldap3 2.5`、
  `pycryptodome 3.20.0` — 重大度、CVE/Snyk ID、および **アップグレードパス** を含みます。
- `snyk code test` は、`vulnerable.py` と `app.py` のテイントフローを報告します — SQL インジェクション（CWE-89）、
  コマンドインジェクション（CWE-78）、パストラバーサル（CWE-22）、XSS（CWE-79）、安全でないデシリアライゼーション
  （CWE-502）、XXE（CWE-611）、LDAP インジェクション（CWE-90）、検証されない JWT 署名（CWE-347）、安全でない
  乱数生成（CWE-330/338）、無効化された TLS 検証（CWE-295）、オープンリダイレクト（CWE-601）、シークレットの
  平文ロギング/送信（CWE-312/319）、脆弱なハッシュ化（CWE-327）など。

ベースラインのカウントを記録してください（Snyk はそれぞれについてサマリー行を出力します） — 次のステップで
新規（net-new）問題を追加した後に、これらと比較します。

---

## 4. SCA を1件 + SAST を1件追加する（IDE で「新規」を明確にする）

このステップの目的は、**Snyk IDE 拡張機能が、今まさに導入した問題だけをハイライトする** ことを示すことです —
つまり、バックログ全体に埋もれさせるのではなく、新規（net-new）の差分だけを表示します。

Snyk 拡張機能を有効にした状態で VS Code でフォルダを開き、拡張機能がベースラインを持てるように
最初のスキャンを実行し、その後、以下の2つの問題を導入します。

### 4a. 新規（net-new）**SCA** 問題 — 脆弱な依存関係を追加する

`simple/pyproject.toml` を編集し、既知の脆弱性を含む、メンテナンス放棄されたパッケージを `dependencies`
リストに追加します。

```toml
dependencies = [
  "urllib3==1.24.3",
  # ... 既存のエントリ ...
  "ldap3==2.5",
  "pycrypto==2.6.1",   # <-- 新規（NET-NEW）SCA: メンテ放棄された暗号ライブラリ、CVE-2013-7459（ヒープオーバーフロー）
]
```

Snyk が認識できるように再ロックします。

```bash
uv lock
uv sync
```

### 4b. 新規（net-new）**SAST** 問題 — 脆弱な関数を追加する

`simple/vulnerable.py` に新しいコマンドインジェクションのシンクを追加します。ファイル内にまだ存在しない
関数を使用してください（ベースラインには既に `run_backup` のようなシンクが同梱されています）。そうすれば、
新規（net-new）としてきれいに表示されます。

```python
# CWE-78: OS コマンドインジェクション — トレーニングの差分用の新規（NET-NEW）SAST 問題。
def compress_logs(logdir: str):
    os.system("gzip -r " + logdir)
```

### 4c. IDE で差分を確認する

- 両方のファイルを保存します。Snyk 拡張機能は保存時に再スキャンします。
- **Snyk パネル** では、新しく追加された `pycrypto`（Open Source）と `compress_logs`（Code）の検出結果が
  最上部に表示され、前回のスキャン以降の新規として印が付きます。
- `os.system(...)` の行の波線にカーソルを合わせると、インラインの検出結果、データフロー、および
  修正ガイダンスが表示されます — 開発者が作業しているまさにその場所で。

> トークポイント: これが実践における「シフトレフト」です — 開発者は、エディタを離れることなく、また
> CI/PR ゲートを待つことなく、*自身の* 新しいリスクを即座に確認できます。

---

## 5. IDE 拡張機能を通じて SAST 問題を1件修正する

Snyk パネルでコードの検出結果を1つ選びます — ステップ 4b で追加した新規（net-new）の `compress_logs`
コマンドインジェクションは、デモの対象としてわかりやすいものです。

1. **Snyk パネル → Code Security** で、`compress_logs`（CWE-78）の検出結果をクリックします。
2. 詳細ビューを読みます: データフロー（信頼できない `logdir` → シェル）、CWE、および修正
   ガイダンス。
3. **⚡ Fix this issue**（Snyk の AI 支援による IDE 内修正）をクリックして安全な書き換えを生成します。例えば、
   シェル文字列を引数リストに置き換え、シェルを使わないようにします。

   ```python
   import subprocess

   def compress_logs(logdir: str):
       subprocess.run(["gzip", "-r", logdir], check=True)
   ```

4. 提案された修正を適用し、保存して、拡張機能に再スキャンさせます。検出結果はパネルから消えます。

> トークポイント: 修正は **最小限でレビュー可能な差分** のままです — シェルを使わず、引数はリストとして
> 渡されます — そして検証は、今まさに緑色に変わるのを見た再スキャンそのものです。

---

## 6. 実験的：Snyk Remediation Agent（MCP + Copilot CLI 経由）

このステップでは、**Snyk MCP サーバー** を AI コーディングアシスタントに接続し、**Snyk Studio
Recipes** をインストールします。これにより、自然言語（`/snyk-fix`）から修復を実行できるようになります。
レシピの完全な内訳については [`STUDIO_RECIPES_EXPLAINED.md`](./STUDIO_RECIPES_EXPLAINED.md) を参照してください。

### 6a. Snyk Studio Recipes をインストールする

レシピは、アシスタントを自動検出し、スキル、ガードレール、MCP 設定をマージする単一の自己展開型
インストーラーとして提供されます。

```bash
# studio-recipes ディストリビューションから:
./installer/dist/snyk-studio-install.sh            # macOS/Linux
# または:  installer\dist\snyk-studio-install.ps1      # Windows PowerShell

# 必要に応じて単一のアシスタントを対象にする:
./installer/dist/snyk-studio-install.sh --ade copilot
```

これにより、検出されたアシスタントに対して `/snyk-fix` および `/snyk-batch-fix` コマンド/スキルと
Snyk MCP 連携がインストールされます。

### 6b. GitHub Copilot CLI に Snyk MCP サーバーを登録する

Snyk MCP サーバーは、スキャナー（`snyk_code_scan`、`snyk_sca_scan`、
`snyk_breakability_check`、`snyk_auth`、…）を stdio 経由で公開します。これを Copilot CLI の MCP 設定
（`~/.config/github-copilot/mcp.json`、または `copilot mcp add` 経由）に追加します。

```jsonc
{
  "servers": {
    "Snyk": {
      "command": "snyk",
      "args": ["mcp", "-t", "stdio"],
      "env": {
        "SNYK_CFG_ORG": "cdc6bc3b-f914-4a3d-b52c-a45147a46643"
      }
    }
  }
}
```

その後、リポジトリ内で Copilot CLI を起動し、ツールが読み込まれたことを確認します。

```bash
cd simple
copilot            # インタラクティブな Copilot CLI セッションを開始する
# セッション内で:
/mcp               # Snyk サーバー + そのツールが一覧表示されるはず
```

> 同じ MCP ブロックは Claude Code（`.mcp.json`）と Cursor でも機能します — Studio Recipes インストーラーが
> アシスタントごとに正しいファイルを自動的に書き込みます。

---

## 7. SCA スキャンを検査する — MCP ツール **と** CLI — ブレーカビリティ分析付き

ここでは、依存関係リスクを表示する2つの方法を比較し、**ブレーカビリティ分析** を強調します —
これは、アップグレードがコードを壊す可能性がどれくらいあるかについての Snyk の評価です。

### 7a. Snyk MCP ツール経由（アシスタント内）

Copilot CLI / Claude Code セッションで:

```
このプロジェクトで Snyk SCA スキャンを実行し、脆弱な依存関係、
それらの修正バージョン、および各アップグレードのブレーカビリティリスクを表示してください。
```

アシスタントは `snyk_sca_scan`（探索）と、候補となる各アップグレードに対して `snyk_breakability_check` を
呼び出し、以下の表を返します: パッケージ、現在 → 修正後のバージョン、重大度、および **ブレーカビリティ = LOW /
MEDIUM / HIGH**。ブレーカビリティは、`snyk-fix` ワークフローにおいて修正をゲートするものです。

- **LOW / MEDIUM** → 自動適用が安全（MEDIUM はその根拠を文書化します）。
- **HIGH** → アップグレードが適用される前に明示的な確認が必要。

### 7b. Snyk CLI 経由

```bash
cd simple
snyk test                      # 人間が読める依存関係レポート + アップグレードパス
snyk test --json > sca.json    # 完全な機械可読の詳細（バージョン、CVSS、エクスプロイトの成熟度）
```

> トークポイント: 同じ基盤データに対する2つの表面。CLI は決定論的な CI/ターミナルビューであり、
> MCP ツールは **Remediation Agent** がブレーカビリティを推論して *最も低リスク* の
> アップグレードを選択できるようにします — 単に最新のバージョン番号を選ぶのではありません。

---

## 8. `/snyk-fix` で修正する — 単一項目とバッチ

Studio Recipes + MCP が整ったら、アシスタントから修復を実行します。

### 8a. ID を指定して単一の脆弱性を修正する

**自分自身のスキャン出力**（ステップ 3 / ステップ 7）から ID を使用します。

```
/snyk-fix CVE-2019-11324
```

`/snyk-fix <ID>` はディスパッチャーとして機能します: その特定の問題を見つけるために探索を実行し、
コードまたは依存関係ハンドラにルーティングし、最小限の修正を適用し（SCA の場合はまずブレーカビリティ
チェックを実行）、検証のために再スキャンし、サマリーを出力します。**PR を開く前に、あなたの確認を待ちます。**

> 実際の ID に置き換えてください: 例えば Jinja2 の `CVE-2020-28493`、`urllib3` の CVE、または
> `snyk test` の出力に表示される `SNYK-PYTHON-*` ID など。タイプを指定してコードの問題を対象にすることも
> できます。例: `/snyk-fix the SQL injection in vulnerable.py`。

### 8b. バッチ修正

```
/snyk-fix                      # すべてを探索 + 修正、優先度順
/snyk-fix all high             # または重大度で絞り込む
/snyk-fix top 5                # または件数で
```

バッチモードは、両方のスキャンを実行し、問題タイプごとにグループ化し、**Critical → Low** の順に
ソートし（利用可能な修正がある問題を優先）、**番号付きの修正プラン** を表示し、適用する前に
**あなたの確認を待ちます**。暴走ループを防ぐために **20 個の脆弱性 / 15 ファイル / 項目ごとに3回の試行** に
制限されており、修正を検証できない場合はクリーンにロールバックします。

---

## 9. `/snyk-fix` の効果を強調する

実行後、チームに対して、何が変更され、なぜ信頼できるのかを正確に説明します。

- **本物の、検証済みの修正 — 推測ではない。** すべての変更は、同じ対象の **再スキャン** によって
  確認されます。ワークフローは最大3回まで反復し、クリーンな修正を生成できない場合や、同等以上の重大度の
  問題を導入した場合には **ロールバック** します。
- **でっち上げの依存関係修正はない。** Snyk が修正バージョン/アップグレードパスを報告しない場合、
  `/snyk-fix` はそれを捏造することを拒否します — **「No Fix Available（利用可能な修正なし）」** の
  アドバイザリを出力して停止します。
- **ブレーカビリティでゲートされたアップグレード。** SCA 修正は、何かに手を付ける *前に*
  `snyk_breakability_check` を実行します。HIGH リスクのアップグレードにはあなたの承認が必要であり、
  バージョン選択は最も低いバージョン番号ではなく **最も低いブレーカビリティリスク** を最適化します。
- **最小限で、レビュー可能な差分。** コード修正は標準的なセキュアパターンを使用します（SQLi にはパラメータ化
  クエリ、XSS には出力エンコーディング、パストラバーサルには正規化+検証、コマンドインジェクションには
  引数リスト）。無関係なリファクタリングは行いません。
- **あなたが主導権を保つ。** **PR を開く前には必ず確認します**。確認後は、`fix/security-<identifier>` に
  ブランチを切り、セキュリティ関連のファイルのみをステージし、コミットし、プッシュし、`gh` を介して
  PR を開きます。

### 効果を自分で確認する

```bash
cd simple

# エージェントが行った正確な変更を確認する:
git diff

# 検出結果が実際に消えたことを確認する:
snyk test          # SCA — 依存関係の脆弱性が減少/ゼロに
snyk code test     # SAST — 修正されたコードの問題はもう報告されない
```

これらのカウントを、ステップ 3 で記録したベースラインと比較してください — この差分こそが価値のストーリーです:
開発者のワークフローを離れることなく、問題が発見され、修正され、検証されたのです。

---

## 10. PR チェック用に Snyk ↔ GitHub 連携を設定する（SCA + SAST）

プルリクエストをゲートできるようにする前に、Snyk が GitHub からリポジトリをインポートし、両方のスキャン
タイプで **PR チェック** を有効にする必要があります。これはリポジトリ/組織ごとに一度だけ行います。

### 10a. GitHub を接続してリポジトリをインポートする

1. [Snyk Web UI](https://app.snyk.io) で、**Settings → Integrations → GitHub**（または
   **GitHub Enterprise**）に移動し、`lmaeda` アカウント/組織に対して Snyk アプリを認可します。
2. **Add project → GitHub** に移動し、`lmaeda/uv-goof` を見つけてインポートします。Snyk は対象
   ブランチをインポートし、`pyproject.toml` / `uv.lock`（SCA）とファーストパーティコード（SAST）の
   監視を開始します。

> PR チェックと CLI/IDE の結果が一致するように、プロジェクトが接続されているのと **同じ組織**
> （`cdc6bc3b-f914-4a3d-b52c-a45147a46643`）にインポートするようにしてください。

### 10b. SCA と SAST の **両方** で PR チェックを有効にする

Snyk Web UI で、**Settings → Integrations → GitHub → Automatic pull request checks**（および
組織で Snyk Code が有効になっていることを確認するために **Settings → Snyk Code**）を開き、
以下を有効にします。

| 設定 | 場所 | 機能 |
|---|---|---|
| **Open Source (SCA) PR checks** | Settings → Integrations → GitHub | PR の依存関係の変更に対して `snyk test` を実行 |
| **Snyk Code (SAST) PR checks** | Settings → Integrations → GitHub | PR のコードの変更に対して `snyk code test` を実行 |
| **Fail conditions** | 同じパネル | どの重大度でチェックを失敗させるかを選択（例: 利用可能な修正がある Medium 以上で失敗） |
| **Only new issues** *(オプション)* | 同じパネル | **新規（net-new）** の問題のみで PR をゲートする — ステップ 4 の IDE 差分を反映 |

> トークポイント: これは、シフトレフトの IDE ビューを補完する CI/PR ゲートです。エディタと CLI で
> 実行されるのと同じ Snyk エンジンが、すべてのプルリクエストで自動的に実行されるようになります —
> チェックはネイティブの GitHub 連携に乗っているため、パイプラインの YAML は必要ありません。

---

## 11. Snyk PR チェックをテストするために PR を開く

次に、ステップ 10 で設定したチェックが実際に発火するように、プルリクエストを作成します。

`/snyk-fix`（ステップ 8、`fix/security-<identifier>`）から既に修正ブランチがある場合もあれば、
ステップ 5〜8 で適用した修正から手動で作成することもできます。修正ブランチはステップ 1b の
**トレーニング用ベースブランチから**切り出し、時間ごとの実施を区別できるようサフィックス
`YYYYMMDD_HH` を付けます。

```bash
cd simple

# 例: ai-agent-snyk-fix_20260709_14（日付 + 時。トレーニング用ベースブランチから切り出す）
export FIX_BRANCH="ai-agent-snyk-fix_$(date +%Y%m%d_%H)"

# /snyk-fix が既にブランチ作成 + プッシュを行っていない場合:
git checkout -b "$FIX_BRANCH" "$TRAIN_BASE"
git add pyproject.toml uv.lock vulnerable.py app.py
git commit -m "fix: remediate Snyk SCA + SAST findings"
git push -u origin "$FIX_BRANCH"

# トレーニング用ベースブランチにマージするための PR を開く（gh 経由、または GitHub Web UI で):
gh pr create \
  --base "$TRAIN_BASE" \
  --head "$FIX_BRANCH" \
  --title "Fix Snyk SCA + SAST findings" \
  --body "Remediates dependency and code vulnerabilities surfaced by Snyk."
```

> ヒント: チェックが問題を *検出* する様子と通過する様子の両方をデモするには、新しい脆弱な依存関係
> （ステップ 4a の `pycrypto` の変更）を **導入する** PR を1つと、問題を **修正する** PR を
> もう1つ開きます。1つ目はチェックによってフラグが立てられ、2つ目はクリーンな結果が返ってくるはずです。

> **オプション — GitHub MCP 経由でアシスタントから PR を開く。** `gh` の代わりに、GitHub MCP サーバーを
> アシスタントに登録し（`docker run ... ghcr.io/github/github-mcp-server`、またはホスト型サーバーを
> GitHub トークンで認可）、次のように尋ねるだけです: *「私の修正ブランチからトレーニング用ベースブランチへ、
> これらの変更で PR を開いてください。」* 上記の `gh` コマンドと同じ結果になります — これにより、ループ全体
> （スキャン → 修正 → PR）がステップ 6〜8 の自然言語ワークフロー内に収まります。`gh` は引き続き
> 決定論的なデフォルトです。

### PR で期待されること

GitHub のプルリクエストページで、**Checks** の下に2つの Snyk チェックが表示されます。

- **Snyk Open Source** — SCA スキャンからの新規/ブロックされた依存関係の脆弱性を報告します。
- **Snyk Code** — SAST スキャンからの新規/ブロックされたコードの脆弱性を報告します。

各チェックは、ステップ 10b の失敗条件に対して ✅ 合格 または ❌ 失敗 を表示し、詳細のために Snyk
UI へのリンクを提供し、（SCA の場合）アップグレードパスを表示します。クリーンな修正 PR は、両方の
チェックを緑色にします。

---

## 12. PR をマージしてチェックを評価する

1. **Snyk Open Source** と **Snyk Code** の両方のチェックが緑色であることを確認します（または、
   「脆弱性を導入する」デモ PR の場合は赤色であることを確認し、ゲートがマージをブロックする様子を
   チームに見せます）。
2. GitHub で PR をマージします（または `gh pr merge --merge`）。
3. マージ後、Snyk は **ベースブランチを再監視** します: Snyk UI でプロジェクトを開き、問題のカウントが
   修正内容に一致して減少したことを確認します — ステップ 9 でローカルで検証したのと同じ差分です。

```bash
# オプション: マージされたトレーニング用ベースブランチが CLI からもクリーンであることを確認する。
git checkout "$TRAIN_BASE"
git pull
cd simple && uv sync
snyk test && snyk code test
```

> トークポイント: これでループが完結します — 開発者は IDE で問題を確認し（ステップ 4）、`/snyk-fix` で
> それを修正・検証し（ステップ 5〜9）、コードがデフォルトブランチに到達する前に **PR チェックがゲートで
> それを強制しました**（ステップ 4）。シフトレフト *と* バックストップの両方を、1つの Snyk
> プラットフォームから実現しています。

---

## 環境をリセットする（次回の実施のために）

```bash
git checkout -- simple/pyproject.toml simple/uv.lock simple/vulnerable.py simple/app.py
git checkout ai-agent-snyk-fix       # 正規のトレーニング用ブランチに戻る
uv sync
```

> 次回の実施は `ai-agent-snyk-fix` から新たに始めます: [ステップ 1b](#1b-日付付きのトレーニング用ベースブランチを作成する)
> と同様に、新しい日付付きのトレーニング用ベースブランチを作成してください。

---

## リポジトリ構成

| パス | 内容 |
|---|---|
| `simple/` | メインのトレーニングプロジェクト — 脆弱な依存関係（`pyproject.toml`）+ 脆弱なコード（`vulnerable.py`、`app.py`） |
| `simple-no-deps/` | 依存関係のない `uv` プロジェクト |
| `workspace/`、`workspace-mixed-sources/`、`virtual-workspace/` | 高度なシナリオ用の追加の `uv` ワークスペースレイアウト |
| `STUDIO_RECIPES_EXPLAINED.md` | Snyk Studio Recipes（`/snyk-fix`、ガードレール、MCP）の詳細解説 |

> このリポジトリは公開コントリビューションを受け付けていませんのでご注意ください。
