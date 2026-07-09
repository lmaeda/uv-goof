# uv-goof — Snyk Training Guide

This repository contains a number of intentionally vulnerable [`uv`](https://docs.astral.sh/uv/)
Python projects. It is used as a **hands-on training track for customer teams** to learn the modern
Snyk developer workflow: scanning from the CLI, seeing net-new issues in the IDE extension, fixing
SAST findings in-editor, and driving the **Snyk Remediation Agent** (Snyk Studio Recipes) from an
AI coding assistant with `/snyk-fix`.

> ⚠️ **The code here is deliberately insecure.** It exists only to generate findings for training.
> Never deploy it, and never copy its patterns into a real project.

Most of the guide uses the [`simple/`](./simple) project, which pins known-vulnerable dependencies
(SCA) in `pyproject.toml` and ships intentionally vulnerable Python source (SAST) in
`vulnerable.py` and `app.py`.

---

## Prerequisites

Install these once before the session:

| Tool | Purpose | Install |
|---|---|---|
| **git** | Clone the repo | preinstalled on most systems |
| **uv** | Build/run the Python project | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Snyk CLI** | Command-line scanning | `npm i -g snyk` or `brew install snyk` |
| **Snyk IDE extension** | In-editor scanning + net-new view | VS Code Marketplace → "Snyk Security" |
| **GitHub CLI (`gh`)** | Open/merge PRs for the PR-check steps ([11](#11-open-a-pr-to-test-the-snyk-pr-check)–[12](#12-merge-the-pr-and-evaluate-the-check)); also how `/snyk-fix` opens PRs | `brew install gh` or see [cli.github.com](https://cli.github.com); then `gh auth login` |
| **AI assistant** | Run `/snyk-fix` recipes | GitHub Copilot CLI **or** Claude Code / Cursor |
| **Snyk Studio Recipes** | The `/snyk-fix` skills + MCP wiring | see [Step 6](#6-experimental-snyk-remediation-agent-via-mcp--copilot-cli) |

> **GitHub access.** `gh` is the required baseline for the PR-check steps and for `/snyk-fix`'s PR
> creation. If you'd rather drive PRs from natural language inside the assistant, you can optionally
> configure the **GitHub MCP server** as well — see the note in [Step 11](#11-open-a-pr-to-test-the-snyk-pr-check).

You also need a Snyk account (free tier is fine). The `simple/` project is preconfigured to the
training org via `.vscode/settings.json`:

```json
{
  "snyk.advanced.organization": "cdc6bc3b-f914-4a3d-b52c-a45147a46643",
  "snyk.advanced.autoSelectOrganization": true
}
```

---

## 1. Fork, clone the project, and create a training base branch

### 1a. Fork the repository on GitHub

Fork [`lmaeda/uv-goof`](https://github.com/lmaeda/uv-goof) into your own GitHub account so you have a
writable copy to push branches and open PRs against. Use the **Fork** button on
[github.com/lmaeda/uv-goof](https://github.com/lmaeda/uv-goof), or the GitHub CLI:

```bash
# Forks lmaeda/uv-goof to <your-username>/uv-goof
gh repo fork lmaeda/uv-goof --clone=false
```

> Keep the fork's default settings (including all branches) so `ai-agent-snyk-fix` comes across as the
> canonical training branch.

### 1b. Clone your fork (branch `ai-agent-snyk-fix`)

```bash
# Clone YOUR fork, not lmaeda/uv-goof
git clone git@github.com:<your-username>/uv-goof.git
cd uv-goof
git checkout ai-agent-snyk-fix

# confirm you are on the training branch
git branch --show-current      # -> ai-agent-snyk-fix
```

> HTTPS alternative: `git clone --branch ai-agent-snyk-fix https://github.com/<your-username>/uv-goof.git`

### 1c. Create a dated training base branch

Each run-through gets its own **training base branch**, cut from `ai-agent-snyk-fix` and suffixed
`YYYYMMDD_base`. This keeps every session (and every trainer) isolated: the fix branch is cut from
it and the fix PR merges back into it, so `ai-agent-snyk-fix` stays pristine as the canonical
starting point.

```bash
# e.g. ai-agent-snyk-fix_20260709_base
export TRAIN_BASE="ai-agent-snyk-fix_$(date +%Y%m%d)_base"

git checkout -b "$TRAIN_BASE"
git push -u origin "$TRAIN_BASE"

git branch --show-current      # -> ai-agent-snyk-fix_<today>_base
```

> Keep this terminal open so `$TRAIN_BASE` stays set for Steps 11–12. In a fresh shell, re-run the
> `export` line above (or substitute the literal branch name).

---

## 2. Build the project

All work in this guide happens inside the `simple/` project.

```bash
cd simple

# Resolve + install the (intentionally vulnerable) dependencies into a local venv.
# uv reads pyproject.toml and pins everything in uv.lock.
uv sync

# Sanity-check that the project runs.
uv run python main.py          # -> Hello from simple-project!
```

You now have `simple/.venv/` populated with the vulnerable dependency tree — exactly what Snyk will
analyze.

> Optional: run the deliberately vulnerable Flask app to see the SAST sinks live at
> `http://127.0.0.1:5000` (routes like `/user`, `/ping`, `/greet`):
> `uv run python app.py`

---

## 3. Run a Snyk scan (CLI)

Authenticate once, then run both scan types from inside `simple/`.

```bash
# Authenticate the CLI (opens a browser).
snyk auth

# --- SCA: open-source dependency vulnerabilities (reads pyproject.toml / uv.lock) ---
snyk test

# --- SAST: first-party code vulnerabilities (Snyk Code) ---
snyk code test
```

What to expect:

- `snyk test` reports vulnerabilities across the pinned dependencies — `urllib3 1.24.3`,
  `jinja2 2.11.2`, `flask 1.1.2`, `requests 2.20.0`, `pyyaml 5.3.1`, `pyjwt 1.5.3`,
  `cryptography 2.3`, `pillow 10.4.0`, `django 2.2.0`, `lxml 5.3.0`, `ldap3 2.5`,
  `pycryptodome 3.20.0` — with severity, CVE/Snyk IDs, and **upgrade paths**.
- `snyk code test` reports the taint flows in `vulnerable.py` and `app.py` — SQL injection (CWE-89),
  command injection (CWE-78), path traversal (CWE-22), XSS (CWE-79), insecure deserialization
  (CWE-502), XXE (CWE-611), LDAP injection (CWE-90), unverified JWT signature (CWE-347), insecure
  randomness (CWE-330/338), disabled TLS verification (CWE-295), open redirect (CWE-601), cleartext
  logging/transmission of secrets (CWE-312/319), weak hashing (CWE-327), and more.

Capture the baseline counts (Snyk prints a summary line for each) — you will compare against them
after adding net-new issues in the next step.

---

## 4. Add one SCA + one SAST issue (make "net new" obvious in the IDE)

The point of this step is to show that the **Snyk IDE extension highlights only the issues you just
introduced** — the net-new delta — rather than drowning you in the full backlog.

Open the folder in VS Code with the Snyk extension enabled, run an initial scan so the extension has
a baseline, then introduce the two issues below.

### 4a. Net-new **SCA** issue — add a vulnerable dependency

Edit `simple/pyproject.toml` and add a known-vulnerable, abandoned package to the `dependencies`
list:

```toml
dependencies = [
  "urllib3==1.24.3",
  # ... existing entries ...
  "ldap3==2.5",
  "pycrypto==2.6.1",   # <-- NET-NEW SCA: abandoned crypto lib, CVE-2013-7459 (heap overflow)
]
```

Re-lock so Snyk sees it:

```bash
uv lock
uv sync
```

### 4b. Net-new **SAST** issue — add a vulnerable function

Append a new command-injection sink to `simple/vulnerable.py`. Use a function that isn't already
in the file (the baseline already ships sinks like `run_backup`), so it shows up cleanly as net-new:

```python
# CWE-78: OS Command Injection — NET-NEW SAST issue for the training delta.
def compress_logs(logdir: str):
    os.system("gzip -r " + logdir)
```

### 4c. See the delta in the IDE

- Save both files. The Snyk extension re-scans on save.
- In the **Snyk panel**, the newly added `pycrypto` (Open Source) and `compress_logs` (Code) findings
  appear at the top, flagged as new since the last scan.
- Hover the squiggle on the `os.system(...)` line to see the inline finding, the data-flow, and the
  fix guidance — right where the developer is working.

> Talking point: this is "shift-left" in practice — the developer sees *their own* new risk
> immediately, without leaving the editor or waiting for a CI/PR gate.

---

## 5. Fix one SAST issue through the IDE extension

Pick a code finding in the Snyk panel — the net-new `compress_logs` command injection from Step 4b is
a clean demo target.

1. In the **Snyk panel → Code Security**, click the `compress_logs` (CWE-78) finding.
2. Read the detail view: the data flow (untrusted `logdir` → shell), the CWE, and the remediation
   guidance.
3. Click **⚡ Fix this issue** (Snyk's AI-assisted in-IDE fix) to generate a safe rewrite, e.g.
   replacing the shell string with an argument list and no shell:

   ```python
   import subprocess

   def compress_logs(logdir: str):
       subprocess.run(["gzip", "-r", logdir], check=True)
   ```

4. Apply the suggested fix, save, and let the extension re-scan. The finding clears from the panel.

> Talking point: the fix stays a **minimal, reviewable diff** — no shell, arguments passed as a
> list — and validation is the re-scan you just watched turn green.

---

## 6. Experimental: Snyk Remediation Agent via MCP + Copilot CLI

This step wires the **Snyk MCP server** into an AI coding assistant and installs the **Snyk Studio
Recipes**, so you can drive remediation from natural language (`/snyk-fix`). See
[`STUDIO_RECIPES_EXPLAINED.md`](./STUDIO_RECIPES_EXPLAINED.md) for a full breakdown of the recipes.

### 6a. Install the Snyk Studio Recipes

The recipes ship as a single self-extracting installer that auto-detects your assistants and merges
in the skills, guardrails, and MCP config:

```bash
# From the studio-recipes distribution:
./installer/dist/snyk-studio-install.sh            # macOS/Linux
# or:  installer\dist\snyk-studio-install.ps1      # Windows PowerShell

# Target a single assistant if you like:
./installer/dist/snyk-studio-install.sh --ade copilot
```

This installs the `/snyk-fix` and `/snyk-batch-fix` commands/skills and the Snyk MCP wiring for the
detected assistant(s).

### 6b. Register the Snyk MCP server with GitHub Copilot CLI

The Snyk MCP server exposes the scanners (`snyk_code_scan`, `snyk_sca_scan`,
`snyk_breakability_check`, `snyk_auth`, …) over stdio. Add it to the Copilot CLI MCP config
(`~/.config/github-copilot/mcp.json`, or via `copilot mcp add`):

```jsonc
{
  "servers": {
    "Snyk": {
      "command": "snyk",
      "args": ["mcp", "-t", "stdio"],
      "env": {
        "SNYK_CFG_ORG": "cdc6bc3b-f914-4a3d-b52c-a45147a46643",
        "SNYK_MCP_PROFILE": "experimental"
      }
    }
  }
}
```

Then launch Copilot CLI in the repo and confirm the tools loaded:

```bash
cd simple
copilot            # start the interactive Copilot CLI session
# inside the session:
/mcp               # should list the Snyk server + its tools
```

> The same MCP block works for Claude Code (`.mcp.json`) and Cursor — the Studio Recipes installer
> writes the correct file per assistant automatically.

---

## 7. Inspect the SCA scan — MCP tool **and** CLI — with breakability analysis

Now compare the two ways of viewing dependency risk, and highlight **breakability analysis** — Snyk's
assessment of how likely an upgrade is to break your code.

### 7a. Via the Snyk MCP tool (inside the assistant)

In your Copilot CLI / Claude Code session:

```
Run a Snyk SCA scan on this project and show me the vulnerable dependencies,
their fix versions, and the breakability risk of each upgrade.
```

The assistant calls `snyk_sca_scan` (discovery) and `snyk_breakability_check` per candidate upgrade,
returning a table of: package, current → fixed version, severity, and **breakability = LOW / MEDIUM /
HIGH**. Breakability is what gates the fix in the `snyk-fix` workflow:

- **LOW / MEDIUM** → safe to auto-apply (MEDIUM documents its reasoning).
- **HIGH** → requires explicit confirmation before the upgrade is applied.

### 7b. Via the Snyk CLI

```bash
cd simple
snyk test                      # human-readable dependency report + upgrade paths
snyk test --json > sca.json    # full machine-readable detail (versions, CVSS, exploit maturity)
```

> Talking point: same underlying data, two surfaces. The CLI is your deterministic
> CI/terminal view; the MCP tool lets the **Remediation Agent** reason over breakability to choose
> the *lowest-risk* upgrade — not just the newest version number.

---

## 8. Fix with `/snyk-fix` — single item and batch

With the Studio Recipes + MCP in place, drive remediation from the assistant.

### 8a. Fix a single vulnerability by ID

Use an ID **from your own scan output** (Step 3 / Step 7):

```
/snyk-fix CVE-2019-11324
```

`/snyk-fix <ID>` acts as a dispatcher: it runs discovery to locate that specific issue, routes to the
code or dependency handler, applies the minimal fix (running a breakability check first for SCA),
re-scans to validate, and prints a summary. It **waits for your confirmation before opening a PR**.

> Substitute a real ID: e.g. a Jinja2 `CVE-2020-28493`, an `urllib3` CVE, or a `SNYK-PYTHON-*` ID
> shown in your `snyk test` output. You can also target a code issue by type, e.g.
> `/snyk-fix the SQL injection in vulnerable.py`.

### 8b. Batch fix

```
/snyk-fix                      # discover + fix everything, priority-ordered
/snyk-fix all high             # or scope to a severity
/snyk-fix top 5                # or a count
```

Batch mode runs both scans, groups by issue type, sorts **Critical → Low** (preferring issues with
an available fix), shows a **numbered fix plan**, and **waits for your confirmation** before
applying. It is bounded to **20 vulns / 15 files / 3 attempts per item** to prevent runaway loops,
and rolls back cleanly if a fix can't be validated.

---

## 9. Highlight the effects of `/snyk-fix`

After the run, walk the team through exactly what changed and why it's trustworthy:

- **Real, validated fixes — not guesses.** Every change is confirmed by a **re-scan** of the same
  target; the workflow iterates up to 3 attempts and **rolls back** if it can't produce a clean fix
  or introduces an equal/higher-severity issue.
- **No invented dependency fixes.** If Snyk reports no fix version/upgrade path, `/snyk-fix` refuses
  to fabricate one — it emits a **"No Fix Available"** advisory and stops.
- **Breakability-gated upgrades.** SCA fixes run `snyk_breakability_check` *before* touching
  anything; HIGH-risk upgrades require your sign-off, and version selection optimizes for
  **lowest breakability risk**, not lowest version number.
- **Minimal, reviewable diffs.** Code fixes use standard secure patterns (parameterized queries for
  SQLi, output encoding for XSS, canonicalize+validate for path traversal, arg-lists for command
  injection) with no unrelated refactoring.
- **You stay in control.** It **always asks before opening a PR**; on confirmation it branches
  `fix/security-<identifier>`, stages only the security-related files, commits, pushes, and opens the
  PR via `gh`.

### Verify the effect yourself

```bash
cd simple

# See the exact changes the agent made:
git diff

# Confirm the findings are actually gone:
snyk test          # SCA — fewer/zero dependency vulns
snyk code test     # SAST — the fixed code issues no longer report
```

Compare these counts against the baseline you captured in Step 3 — the delta *is* the value story:
issues found, fixed, and validated without leaving the developer's workflow.

---

## 10. Configure the Snyk ↔ GitHub integration for PR checks (SCA + SAST)

Before a pull request can be gated, Snyk needs to be imported the repo from GitHub and have **PR
checks** turned on for both scan types. Do this once per repo/org.

### 10a. Connect GitHub and import the repo

1. In the [Snyk Web UI](https://app.snyk.io), go to **Settings → Integrations → GitHub** (or
   **GitHub Enterprise**) and authorize the Snyk app for your own GitHub account/org (the one that
   owns your fork).
2. Go to **Add project → GitHub**, find `<your-username>/uv-goof`, and import it. Snyk imports the
   target branch and begins monitoring `pyproject.toml` / `uv.lock` (SCA) and the first-party code
   (SAST).

> Make sure you import into the **same org** the project is wired to
> (`cdc6bc3b-f914-4a3d-b52c-a45147a46643`) so the PR check and the CLI/IDE results line up.

### 10b. Enable PR checks for **both** SCA and SAST

In the Snyk Web UI, open **Settings → Integrations → GitHub → Automatic pull request checks** (and
**Settings → Snyk Code** to confirm Snyk Code is enabled for the org), then turn on:

| Setting | Where | What it does |
|---|---|---|
| **Open Source (SCA) PR checks** | Settings → Integrations → GitHub | Runs `snyk test` against the PR's dependency changes |
| **Snyk Code (SAST) PR checks** | Settings → Integrations → GitHub | Runs `snyk code test` against the PR's code changes |
| **Fail conditions** | Same panel | Choose which severities fail the check (e.g. fail on Medium+ with an available fix) |
| **Only new issues** *(optional)* | Same panel | Gates the PR on **net-new** issues only — mirrors the IDE delta from Step 4 |

> Talking point: this is the CI/PR gate that complements the shift-left IDE view. The same Snyk
> engine that runs in the editor and CLI now runs automatically on every pull request — no pipeline
> YAML required, because the check rides the native GitHub integration.

---

## 11. Open a PR to test the Snyk PR check

Now produce a pull request so the checks configured in Step 10 actually fire.

You already have a fix branch from `/snyk-fix` (Step 8, `fix/security-<identifier>`), or you can
create one manually from the fixes you applied in Steps 5–8. Cut the fix branch **off the training
base branch** from Step 1c and suffix it `YYYYMMDD_HH` so each hourly run is distinct:

```bash
cd simple

# e.g. ai-agent-snyk-fix_20260709_14  (date + hour, cut from the training base branch)
export FIX_BRANCH="ai-agent-snyk-fix_$(date +%Y%m%d_%H)"

# If /snyk-fix didn't already branch + push for you:
git checkout -b "$FIX_BRANCH" "$TRAIN_BASE"
git add pyproject.toml uv.lock vulnerable.py app.py
git commit -m "fix: remediate Snyk SCA + SAST findings"
git push -u origin "$FIX_BRANCH"

# Open the PR to merge into the training base branch (via gh, or the GitHub web UI):
gh pr create \
  --base "$TRAIN_BASE" \
  --head "$FIX_BRANCH" \
  --title "Fix Snyk SCA + SAST findings" \
  --body "Remediates dependency and code vulnerabilities surfaced by Snyk."
```

> Tip: to demo the check *catching* a problem as well as passing, open one PR that **introduces** a
> new vulnerable dependency (the `pycrypto` change from Step 4a) and a second PR that **fixes**
> issues. The first should be flagged by the check; the second should come back clean.

> **Optional — open the PR from the assistant via GitHub MCP.** Instead of `gh`, you can register
> the GitHub MCP server with your assistant (`docker run ... ghcr.io/github/github-mcp-server`, or
> the hosted server, authorized with a GitHub token) and then just ask: *"Open a PR from my fix
> branch into the training base branch with these changes."* Same result as the `gh`
> commands above — this keeps the whole loop (scan → fix → PR) inside the natural-language workflow
> from Steps 6–8. `gh` remains the deterministic default.

### What to expect on the PR

On the pull request page in GitHub, two Snyk checks appear under **Checks**:

- **Snyk Open Source** — reports new/blocked dependency vulnerabilities from the SCA scan.
- **Snyk Code** — reports new/blocked code vulnerabilities from the SAST scan.

Each check shows ✅ pass or ❌ fail against the fail conditions from Step 10b, links back to the Snyk
UI for detail, and (for SCA) surfaces the upgrade path. A clean fix PR turns both checks green.

---

## 12. Merge the PR and evaluate the check

1. Confirm both **Snyk Open Source** and **Snyk Code** checks are green (or, for the "introduces a
   vuln" demo PR, red — and let the team see the gate block the merge).
2. Merge the PR in GitHub (or `gh pr merge --merge`).
3. After merge, Snyk **re-monitors the base branch**: open the project in the Snyk UI and confirm the
   issue counts dropped to match the fixes — the same delta you validated locally in Step 9.

```bash
# Optional: verify the merged training base branch is clean from the CLI too.
git checkout "$TRAIN_BASE"
git pull
cd simple && uv sync
snyk test && snyk code test
```

> Talking point: this closes the loop — the developer saw the issue in the IDE (Step 4), fixed and
> validated it with `/snyk-fix` (Steps 5–9), and the **PR check enforced it at the gate** before the
> code could reach the default branch. Shift-left *and* a backstop, from one Snyk platform.

---

## Reset the environment (for the next run-through)

```bash
git checkout -- simple/pyproject.toml simple/uv.lock simple/vulnerable.py simple/app.py
git checkout ai-agent-snyk-fix       # back to the canonical training branch
uv sync
```

> The next run-through starts fresh from `ai-agent-snyk-fix`: create a new dated training base
> branch as in [Step 1c](#1c-create-a-dated-training-base-branch).

---

## Repository layout

| Path | What it is |
|---|---|
| `simple/` | Main training project — vulnerable deps (`pyproject.toml`) + vulnerable code (`vulnerable.py`, `app.py`) |
| `simple-no-deps/` | A `uv` project with no dependencies |
| `workspace/`, `workspace-mixed-sources/`, `virtual-workspace/` | Additional `uv` workspace layouts for advanced scenarios |
| `STUDIO_RECIPES_EXPLAINED.md` | Deep-dive on the Snyk Studio Recipes (`/snyk-fix`, guardrails, MCP) |

> Please note that this repository is closed to public contributions.
