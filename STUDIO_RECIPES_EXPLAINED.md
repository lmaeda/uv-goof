# Snyk Studio Recipes — Repository Explained

> A walkthrough of the `studio-recipes` repository: what it is, the skills Snyk ships
> (starting with `snyk-fix`), the aim of the `composit_commands`, and the options users
> have to optimize token consumption.

---

## 1. What is this repository?

**Snyk Studio Recipes** are drop-in security "recipes" that embed Snyk directly inside the AI
coding assistants developers already use — **Cursor, Claude Code, GitHub Copilot (CLI + VS Code),
Gemini, Windsurf, and Kiro**. The goal is **"Secure at Inception"**: run security checks *at the
moment code is generated*, inside the assistant's loop, so vulnerabilities are caught and fixed
before they ever land in a commit — rather than at PR/CI/deploy time, after the risky code has
already shaped the design.

Everything ships as **one self-extracting installer** that auto-detects your assistants and merges
in the recipes (`installer/dist/snyk-studio-install.sh` / `.ps1`).

### Recipe categories

The repo is organized into three families of recipes plus MCP wiring:

| Directory | Recipe type | What it does | When it fires |
|---|---|---|---|
| `guardrail_directives/secure_at_inception/` | **Secure at Inception guardrails** | Auto-scan AI-generated code for vulns the moment it's written | Continuously, as the assistant writes code |
| `guardrail_directives/secure_at_commit/` | **Secure at Commit guardrails** *(experimental)* | Deterministically block `git commit` when staged code/deps introduce new vulns | At `git commit` time |
| `guardrail_directives/package_enforcement/` | **Package enforcement guardrails** | Block risky/vulnerable dependencies before install | At dependency-add time |
| `command_directives/synchronous_remediation/` | **Remediation commands & skills** | Find, fix, validate, and PR security issues in a guided flow | On demand |
| `mcp/` | **Snyk MCP integration** | Wires Snyk's CLI/scanners into the assistant via the Snyk MCP server | Automatically, once installed |

### Two delivery mechanisms, repeated throughout

- **Guardrails** = *automatic, always-on* controls. They come in flavors: **rule versions**
  (`.mdc` instructions injected into the model's context), **hook versions** (deterministic Python
  scripts the harness runs on events like `PostToolUse`/`Stop`), and per-assistant variants
  (`claude/`, `cursor/`, `codex/`, `copilot/`, `gemini/`, `kiro_hooks/`).
- **Commands & Skills** = *on-demand* workflows the developer or agent invokes.

The rest of this document focuses on the **skills** and the **composite commands** under
`command_directives/synchronous_remediation/`.

---

## 2. Skills prepared by Snyk

Skills live in `command_directives/synchronous_remediation/skills/`. A **skill** is a self-contained
module that teaches an AI agent a specialized workflow. Each skill folder contains:

1. **`SKILL.md`** — the definition: YAML frontmatter (`name`, `description`, `allowed-tools`) +
   markdown instructions.
2. **`README.md`** *(optional)* — install/usage docs.
3. **`references/`** *(optional)* — supporting material loaded **on demand**, not upfront.

Skills are invoked **automatically** when the agent matches a user request against the skill's
`description` field (intent recognition → load skill → execute workflow).

### 2.1 `snyk-fix` — the flagship skill (All-in-One remediation)

**File:** `skills/snyk-fix/SKILL.md` · **Version:** 1.1.0 · **License:** Apache-2.0

**Purpose:** A complete, end-to-end security remediation workflow — it scans, fixes, validates, and
optionally opens a PR, for **both** code (SAST) and dependency (SCA) vulnerabilities.

**Triggers** (from its `description`): "fix security vulnerabilities", "snyk fix", "security fix",
"remediate vulnerabilities", a specific CVE / Snyk ID / vuln type (XSS, SQLi, path traversal…),
"upgrade a vulnerable dependency", or "fix all high/critical" (batch mode).

**Allowed tools:** `snyk_code_scan`, `snyk_sca_scan`, `snyk_breakability_check`, `snyk_auth`,
`snyk_send_feedback`, plus `Read`, `Write`, `Edit`, `Bash`, `Grep`.

**Two operating modes:**
- **Single Mode (default)** — fix one vulnerability *type* per run (but ALL instances of it in the
  same file).
- **Batch Mode** — fix many vulnerabilities in priority order; triggered by "all", a severity
  filter, a count ("top 5"), or "batch". Bounded to **max 20 vulns, 15 files, 3 attempts per item**.

**The workflow (7 phases):** `Parse → Scan → Analyze → Fix → Validate → Summary → (Optional) PR`

1. **Phase 1 — Input Parsing.** Determine mode, scan type (`code` / `sca` / `both`), the target
   vulnerability, target path, and (batch) severity filter + max fixes — inferred from the request.
2. **Phase 1B — Batch Planning** (batch only). Run both scans, filter, group by type, sort
   Critical→Low (prefer issues with available fixes), show a numbered fix plan, and **wait for user
   confirmation**.
3. **Phase 2 — Discovery.** Run `snyk_code_scan` on the target path and/or `snyk_sca_scan` on the
   project root (in parallel when "both"). Select the highest-priority target
   (Critical+exploit > Critical > High+exploit > High > Medium > Low). For code, group **all
   instances of the same Snyk ID in the same file**. **Key SCA guardrail (Step 2.5):** if Snyk
   reports *no* fix version/upgrade path, the agent must **NOT invent a fix** — it emits a
   "No Fix Available" report and STOPs.
4. **Phase 3 — Code remediation.** Understand → plan → apply the fix to *all* instances (bottom-to-top
   to avoid line shifts, minimal change, no unrelated refactoring). Uses standard secure patterns
   (parameterized queries for SQLi, output encoding for XSS, canonicalize+validate for path traversal, etc.).
5. **Phase 4 — SCA remediation.** Pick exactly one **strategy**: **A** (direct upgrade),
   **B** (parent upgrade to pull a fixed transitive), or **C** (transitive fix via the
   lowest-impact resolver mechanism). **Breakability gates every SCA fix**:
   `snyk_breakability_check` runs *before* any change; LOW/MEDIUM auto-apply (MEDIUM documents its
   reasoning), HIGH requires user confirmation in interactive mode or a documented decision in
   autonomous mode. **Step 4.2a fallback**: if breakability data is unavailable, derive a
   substitute risk level from **semver distance × codebase usage**. Version selection optimizes for
   lowest breakability risk, not just lowest version number.
6. **Phase 4a — Full Advisory** (SCA no-apply path). When the fix is declined/too risky, emit a
   detailed manual-remediation advisory instead of touching files, then STOP.
7. **Phase 5 — Validation.** Re-run the same scan to confirm resolution, run tests, run linting.
   Iterate up to 3 attempts; **roll back all changes** if a clean fix can't be produced or new
   equal/higher-severity vulns are introduced.
8. **Phase 6 — Summary & PR prompt.** Show a compact remediation summary + validation table, send
   `snyk_send_feedback` metrics, and **wait for explicit user confirmation** before any PR.
9. **Phase 7 — Create PR** (if confirmed). Branch `fix/security-<identifier>`, stage only
   security-related files, commit, push, and `gh pr create`.

**Design principles worth noting:** deterministic guardrails (no inventing fixes, no fix without a
breakability check), safe rollback, minimal-diff fixes, and a hard "always ask before opening a PR"
rule.

> A **`single_all_in_one_command/snyk-fix.md`** command mirrors this same workflow for assistants
> that use slash-commands instead of skills (e.g. Cursor).

### 2.2 The other Snyk skills

All are Apache-2.0 and follow the same "SKILL.md + references/" structure. Each is auto-triggered by
its `description`.

| Skill | Purpose | Primary Snyk MCP tool | Triggers (examples) |
|---|---|---|---|
| **`secure-at-inception`** | Proactive scan of newly generated/modified code; detects changes, runs SAST/SCA/IaC, and **filters to only NEW issues** | `snyk_code_scan`, `snyk_sca_scan`, `snyk_iac_scan` | agent writes/modifies code, "check my changes", before commit |
| **`secure-dependency-health-check`** | Choose secure, healthy OSS packages by vuln status, maintenance, popularity, community | `snyk_package_health_check` | "which package should I use?", "is X safe?", "compare A vs B" |
| **`container-security`** | Scan Docker images for OS/app vulns + Dockerfile best practices | `snyk_container_scan` | "scan this image", "secure my Dockerfile", base-image security |
| **`iac-security`** | IaC security for Terraform, Kubernetes, CloudFormation, ARM | `snyk_iac_scan` | "scan Terraform", "IaC scan", editing K8s manifests |
| **`sbom-analyzer`** | Analyze/validate SBOMs (CycloneDX, SPDX) for vulns & third-party risk | `snyk_sbom_scan` | "analyze this SBOM", "vendor security", "validate supplier SBOM" |
| **`ai-inventory`** | Generate/analyze an AI Bill of Materials (AIBOM) for Python AI/ML projects | `snyk_aibom` | "AI BOM", "what models does this use?", "ML security" |
| **`drift-detector`** | Detect drift between Terraform state and actual cloud resources | `Bash` (Snyk/Terraform CLI) | "check for drift", "unmanaged cloud resources" |

> There is also a top-level **`snyk-batch-fix`** command (`command/snyk-batch-fix.md`) used mainly by
> the Secure-at-Inception *stop hook*: it fixes a batch of **pre-scanned** vulns (data passed in as a
> table) with **no discovery scan**, and does **not** prompt for a PR (it targets in-development code).

---

## 3. The aim of `composit_commands`

**Path:** `command_directives/synchronous_remediation/command/composit_commands/`
**Files:** `snyk-fix.md`, `snyk-code-fix.md`, `snyk-sca-fix.md`, `create-security-pr.md`

### 3.1 What it is

The composite commands take the *same* remediation workflow as the all-in-one `snyk-fix` and
**split it into four focused, single-responsibility commands** that can be chained or used
independently:

| Command | Role |
|---|---|
| `/snyk-fix` | **Dispatcher / orchestrator** — parses input, runs discovery, routes to the right handler, then produces the summary + PR prompt |
| `/snyk-code-fix` | Fixes SAST / code vulnerabilities |
| `/snyk-sca-fix` | Fixes dependency vulnerabilities |
| `/create-security-pr` | Creates the PR for the applied security fixes |

**Flow:** `/snyk-fix` (dispatcher) → routes to `/snyk-code-fix` **or** `/snyk-sca-fix` → control
returns to `/snyk-fix` for the summary → on user confirmation → `/create-security-pr`.

The dispatcher's routing rules (Phase 1) decide where to send the request: explicit `code`/`sca`,
a `SNYK-`/`CVE-` ID (run both scans to locate), a vuln type (→ code), a file reference (→ code), a
package name (→ sca), or, with no hints, run both and route by the highest-priority issue.

### 3.2 Why it exists — the aim

The composite architecture is about **separation of concerns and flexibility** vs. the monolithic
all-in-one skill:

1. **Modularity** — each command has a single responsibility.
2. **Direct access** — you can invoke a sub-command directly (`/snyk-code-fix`, `/create-security-pr`
   after a manual fix) instead of always going through the full flow.
3. **Easier testing** — each command is testable in isolation.
4. **Flexible customization** — teams can modify one phase (e.g. their PR conventions in
   `create-security-pr.md`) without touching the fix logic.
5. **Clear separation** — code fixes vs. dependency fixes vs. PR creation are cleanly divided.

In short: the all-in-one command/skill is the "simple, single-file" option; **composite commands are
for teams that want granular control over each remediation phase** and the ability to compose/reuse
pieces of the workflow.

---

## 4. Optimizing token consumption

Because these recipes run *inside* the assistant's context window on every edit and every fix, token
cost matters. The repo is deliberately structured to give users several levers. Here are the options
a Studio Recipes user has to keep token usage down:

### 4.1 Choose hooks over always-on rules for guardrails

Secure-at-Inception ships in two flavors, and this is the single biggest lever:

- **Rule version** (`rule_version/*.mdc`) — instructions are injected into the model's context and
  marked `alwaysApply: true`. They sit in **every** turn's context window → **constant token cost**.
- **Hook version** (`hooks_version/…/async_cli_version/`) — deterministic Python scripts the harness
  runs on `SessionStart` / `PostToolUse` / `Stop`. The scan happens **outside the model** (a
  background `snyk code test`), and tokens are only spent when findings are fed back for a fix.
  **Near-zero standing token cost.**

> **Recommendation:** prefer the **async CLI hook version** where the assistant supports hooks
> (Claude Code, Cursor, Codex, Copilot, Gemini, Kiro). Reserve the rule version for assistants
> without hook support.

### 4.2 Use the async CLI scan instead of the synchronous MCP scan

Within the hook guardrails there are `async_cli_version` and `sync_mcp_version`:

- **`async_cli_version`** runs the scan in the background via the Snyk **CLI**, off the model's
  critical path. The model isn't paying tokens to orchestrate the scan or to hold raw scan output.
- **`sync_mcp_version`** has the model drive the scan through an MCP tool call, so the tool call
  and its (potentially large) results consume context.

### 4.3 "New-only" filtering (don't feed the whole scan back)

The Secure-at-Inception hook and skill track exactly **which lines the agent modified** and
**filter results to only NEW vulnerabilities** on those lines. Instead of dumping an entire
repository scan into context, the model only ever sees the small delta it needs to fix — a large,
built-in token saving.

### 4.4 Prefer composite commands to load only the phase you need

The all-in-one `snyk-fix` SKILL.md is a large (~600-line) document. The **composite commands** split
it so the dispatcher only pulls in `/snyk-code-fix` *or* `/snyk-sca-fix` (not both) plus
`/create-security-pr` — so a given run loads a smaller slice of instructions into context.

### 4.5 Rely on skills' progressive disclosure

Skills only load their `SKILL.md` when triggered, and their `references/` files (e.g.
`terraform-security-patterns.md`, `severity-thresholds.md`, `sbom-formats.md`) are pulled in **only
when the workflow actually needs them** — not upfront. Keep bulky guidance in `references/` rather
than in the main `SKILL.md` body.

### 4.6 Scope and bound the work

- **Path targeting** — scan a specific file or subdirectory (`/snyk-fix server.ts`) instead of the
  whole repo, so scan output (and the fix context) is smaller.
- **Severity filters & counts** — `/snyk-fix` batch mode accepts a severity filter or "top N" to
  limit how many issues enter the loop.
- **Hard batch caps** — batch mode is bounded to **20 vulns / 15 files / 3 attempts per item**,
  and validation loops cap at **3 fix attempts** — preventing runaway, token-burning retry cycles.

### 4.7 Skip re-discovery with `snyk-batch-fix`

For in-development code, the `snyk-batch-fix` command consumes a **pre-scanned** vuln table handed
over by the Secure-at-Inception stop hook — **no discovery scan** is re-run, so those scan tokens
are saved entirely.

### 4.8 Keep outputs compact (built into the prompts)

The remediation summaries are explicitly designed to be terse: "must fit in one screen", **no
before/after code snippets**, "What Was Fixed" capped at 2–3 sentences, and no listing of remaining
issues. This bounds the model's *output* tokens on every fix.

### 4.9 Install a leaner profile / fewer assistants

The installer lets you control how much gets wired in at all:

- `--profile minimal` installs **only** Secure-at-Inception guardrails + MCP config (drops the
  on-demand fix commands and health-check skill) — fewer directives to load.
- `--profile default` adds `/snyk-fix`, `/snyk-batch-fix`, and the dependency health-check skill.
- `--ade <assistant>` targets a single assistant instead of every detected one.
- Teams can **pin a custom profile** to include only the recipes they use.

### 4.10 Cache-warming (latency, not tokens — but complementary)

The hook launches a background `snyk code test` at session start to prime Snyk's analysis cache.
This doesn't reduce tokens directly, but it makes subsequent scans fast enough that the model spends
less time (and fewer speculative tool calls) waiting on scans.

### Summary of levers

| Lever | Where | Token effect |
|---|---|---|
| Hooks instead of `.mdc` rules | `guardrail_directives/secure_at_inception/` | Removes constant always-on context cost |
| Async CLI scan instead of sync MCP | `…/async_cli_version` vs `…/sync_mcp_version` | Keeps scan orchestration + raw output out of context |
| New-only filtering | Secure-at-Inception hook/skill | Feeds only the modified-line delta to the model |
| Composite commands | `composit_commands/` | Loads only the needed fix phase |
| Progressive disclosure | skills' `references/` | Loads bulky guidance only on demand |
| Path/severity/count scoping | `/snyk-fix` args | Smaller scans, fewer issues in the loop |
| Batch & retry caps | `snyk-fix` / `snyk-batch-fix` | Prevents runaway retry loops |
| `snyk-batch-fix` (pre-scanned) | `command/snyk-batch-fix.md` | Skips re-discovery scan tokens |
| Compact-output prompts | summary phases | Bounds output tokens per fix |
| `--profile minimal` / `--ade` | installer | Fewer directives installed at all |

---

## 5. Quick reference — key paths

```
studio-recipes/
├── README.md                              # Product overview & quick start
├── installer/                             # Self-extracting installer (dist/*.sh, *.ps1) + profiles
├── mcp/                                   # Snyk MCP server wiring
├── guardrail_directives/                  # Automatic, always-on controls
│   ├── secure_at_inception/
│   │   ├── rule_version/                  # .mdc rules (always in context)
│   │   └── hooks_version/<assistant>/
│   │       ├── async_cli_version/         # Background CLI scan (token-light) ← recommended
│   │       └── sync_mcp_version/          # Model-driven MCP scan
│   ├── secure_at_commit/                  # (experimental) git-commit gate
│   └── package_enforcement/               # Block risky deps at install
└── command_directives/synchronous_remediation/
    ├── skills/                            # Auto-triggered skill workflows
    │   ├── snyk-fix/                       # ★ All-in-one remediation (SAST + SCA)
    │   ├── secure-at-inception/            # New-only proactive scan
    │   ├── secure-dependency-health-check/ # Pick safe packages
    │   ├── container-security/  iac-security/  sbom-analyzer/
    │   ├── ai-inventory/  drift-detector/
    └── command/
        ├── snyk-batch-fix.md               # Fix pre-scanned batch (no re-scan, no PR)
        ├── single_all_in_one_command/      # snyk-fix as one command file
        └── composit_commands/              # ★ Modular: dispatcher + code + sca + pr
```

---

*Generated 2026-07-07 from the `studio-recipes` repository (branch `main`).*
