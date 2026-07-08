# Snyk MCP Demo — `snyk_breakability_check`

> **New feature:** `snyk_breakability_check` is a Snyk MCP tool that runs a
> **breaking-change assessment** for a dependency upgrade. Before you accept a
> Snyk-recommended fix (`Upgrade to <pkg>@<version>`), this tool tells you how
> risky that jump is — what APIs were removed, what runtime/OS floors moved, and
> whether you should upgrade incrementally instead of in one leap. It returns a
> `risk_level` of **`low`**, **`medium`**, or **`high`**.
>
> The value: Snyk SCA tells you **what to upgrade to close the vulnerability**;
> `snyk_breakability_check` tells you **whether that upgrade will break your app**.
> Together they turn "here are 47 vulnerabilities" into a prioritized, risk-aware
> remediation plan — and, crucially, help you find the **smallest safe fix**
> instead of always jumping to the newest major.

- **Audience:** Developers and DevOps engineers remediating open-source vulnerabilities.
- **Environment used for this run:** Snyk MCP `v1.1305.2`, project `uv-goof/simple` (Python / `uv`).
- **Prerequisites:** Snyk MCP server connected in your agent/IDE, authenticated
  (`snyk_auth`), and the project's package manager installed (here: Python + `uv`).

---

## Workflow at a glance

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

## Step 1 — Run `snyk_sca_scan`

Scan the project for open-source (SCA) vulnerabilities. Each issue includes the
**current version**, the list of **`fixedIn`** versions, and a **`remediation`**
upgrade target — those are the inputs you'll feed into Step 2.

**Tool call**

```jsonc
// tool: snyk_sca_scan
{
  "path": "/absolute/path/to/uv-goof/simple",  // MUST be an absolute path
  "command": "python3",                          // REQUIRED for Python projects
  "severity_threshold": "high"                   // focus on high + critical
}
```

> Notes:
> - `path` must be **absolute** (run `pwd` to get it).
> - For Python you **must** pass `command` (the Python executable).
> - `severity_threshold` is optional; used here to keep the demo focused.

**Result (abridged):** `47` high/critical issues. A representative slice — note
that most packages list **several** `fixedIn` versions, not just the newest one:

| Package | Current | `fixedIn` options (subset) | `remediation` (default target) | Example issue | Severity |
|---|---|---|---|---|
| django  | 2.2    | `2.2.22`, `2.2.28`, `3.2.14`, `4.2.15`, `4.2.17` | `django@4.2.17` | Command Injection (CVE-2024-53907) / SQLi | high / critical |
| urllib3 | 1.24.3 | `1.25.9`, `2.6.0`, `2.6.3` | `urllib3@2.6.3` | Data Amplification (CVE-2026-21441) | high |
| pyyaml  | 5.3.1  | `5.4` | `pyyaml@5.4` | Arbitrary Code Execution (CVE-2020-14343) | critical |
| flask   | 1.1.2  | `2.2.5`, `2.3.2` | `flask@2.2.5` | Information Exposure (CVE-2023-30861) | high |
| pyjwt   | 1.5.3  | `2.4.0`, `2.12.0`, `2.13.0` | `pyjwt@2.13.0` | Improper Authentication (CVE-2026-48526) | high |
| pillow  | 10.4.0 | `12.1.1`, `12.2.0`, `12.3.0` | `pillow@12.3.0` | Memory Allocation w/ Excessive Size | high |

The `remediation` field usually points at a **major-version jump**. That's the
riskiest option — and exactly why you should run a breakability check before
accepting it, and often check a **smaller `fixedIn` target** too.

---

## Step 2 — Run `snyk_breakability_check` on a handful of issues

Call the tool with the package name and the **from → to** versions from Step 1.
Here we check a mix: the **default (major) `remediation` targets**, and for a few
packages the **smaller same-major `fixedIn` targets** that still close a CVE.

**Tool calls (all can run in parallel):**

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

> Argument reference:
> - `package_name` — package to assess. For scoped npm use `@scope/name`; for
>   Maven use `groupId:artifactId`.
> - `package_version_from` — version **before** the upgrade (current version).
> - `package_version_to` — version **after** the upgrade (a `fixedIn` target).

---

### 2a. Results in JSON format

Each call returns a `risk_level` (`low` / `medium` / `high`), a Markdown
`assessment`, and an `instructions` field (guidance for the agent on how to
proceed). Note how the `instructions` differ by risk level.

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

### 2b. Results in human-readable format

**Summary — sorted by risk (lowest first)**

| Package | Upgrade | Risk | What it means | Suggested action |
|---|---|---|---|---|
| 🟢 django  | 2.2 → 2.2.28    | **Low**    | Patch within 2.2 LTS; fixes critical SQLi, no API changes | Apply — safe to auto-merge |
| 🟢 django  | 2.2 → 2.2.22    | **Low**    | Patch within 2.2 LTS; fixes header injection, no API changes | Apply — safe to auto-merge |
| 🟡 urllib3 | 1.24.3 → 1.25.9 | **Medium** | TLS cert verification now on by default | Apply, then test HTTPS endpoints for valid certs |
| 🟡 pyyaml  | 5.3.1 → 5.4     | **Medium** | No API breaks, but a packaging bug can fail builds | Apply, then verify it installs in CI |
| 🔴 django  | 2.2 → 4.2.17    | **High**   | Two LTS jumps; removed APIs, DB & Python floors | Prefer the 2.2.x patch above; else stage 2.2→3.2→4.2 |
| 🔴 urllib3 | 1.24.3 → 2.6.3  | **High**   | 1.x→2.x; Python 3.10+/OpenSSL 1.1.1+, TLS 1.2 min | Prefer 1.25.9; else audit runtime + removed APIs |
| 🔴 flask   | 1.1.2 → 2.2.5   | **High**   | Renamed `send_file` params, Werkzeug/Jinja bumps | Update calls, test extensions |
| 🔴 pyjwt   | 1.5.3 → 2.13.0  | **High**   | `jwt.decode()` now requires `algorithms` | Add `algorithms=[...]` to every decode |
| 🔴 pillow  | 10.4.0 → 12.3.0 | **High**   | `ImageCms` constants removed, Python 3.10+ | Migrate to `ImageCms.Flags`, verify Python |

> **The headline lesson.** The *same* vulnerable `django 2.2` shows up **three
> times** with **very different risk**: the default `remediation` target
> (`4.2.17`) is 🔴 **high**, but the smaller `2.2.28` / `2.2.22` patch targets are
> 🟢 **low** — and they still close real CVEs. Breakability lets you pick the
> **smallest safe fix** rather than blindly taking the newest major.

**Detail — Low risk (safe to apply)**

- **django 2.2 → 2.2.28 — 🟢 Low.** Patch release within the 2.2 LTS series;
  security/bug fixes only. Closes two high-severity SQL injection issues
  (CVE-2022-28346, CVE-2022-28347). Fully backward-compatible, no API changes.
  → `instructions`: *"Non-breaking change, proceed with the upgrade."*
- **django 2.2 → 2.2.22 — 🟢 Low.** Patch release within the same LTS series;
  no backward-incompatible changes per Django's versioning policy. Fixes an HTTP
  header injection vulnerability.
  → `instructions`: *"Non-breaking change, proceed with the upgrade."*

**Detail — Medium risk (apply, but verify the noted change)**

- **urllib3 1.24.3 → 1.25.9 — 🟡 Medium.** No API removals, but from 1.25.0 TLS
  certificate verification is **on by default**. Requests to endpoints with
  invalid/self-signed certs that used to pass will now raise `SSLError`. Confirm
  all HTTPS targets have valid certs before rolling out.
- **pyyaml 5.3.1 → 5.4 — 🟡 Medium.** No documented runtime API breaks, but 5.4
  has a known packaging issue (deprecated `license_file`) that can break builds
  on newer `setuptools`. Verify it installs cleanly in CI.

**Detail — High risk (plan / prefer a smaller target)**

- **django 2.2 → 4.2.17 — 🔴 High.** Spans two LTS releases. Needs Python 3.8+
  and newer DBs (PostgreSQL 12+; drops MySQL 5.7 / MariaDB 10.3). Removes
  `ugettext*`, `force_text`/`smart_text`, the `postgresql_psycopg2` path, and
  `{% load staticfiles %}`; switches timezone `pytz` → `zoneinfo`; changes
  `DEFAULT_AUTO_FIELD`, `CSRF_TRUSTED_ORIGINS`, `DEFAULT_FILE_STORAGE` → `STORAGES`.
  **Prefer** the 🟢 `2.2.28` patch above unless you specifically need Django 4.x;
  otherwise stage the upgrade 2.2 → 3.2 → 4.2.
- **urllib3 1.24.3 → 2.6.3 — 🔴 High.** Major 1.x → 2.x. Needs Python 3.10+ and
  OpenSSL 1.1.1+. `getheaders()`/`getheader()` removed (use `response.headers`);
  `request_chunked()` → `request(chunked=True)`. Min TLS 1.2; `subjectAltName`-only
  verification; `contrib.ntlmpool`/`contrib.securetransport` removed.
  **Prefer** the 🟡 `1.25.9` target if it closes your CVE.
- **flask 1.1.2 → 2.2.5 — 🔴 High.** Drops Python 2 / 3.5. `from_json()` removed
  (use `from_file()`). `send_file`/`send_from_directory` params renamed
  (`attachment_filename`→`download_name`, `cache_timeout`→`max_age`,
  `filename`→`path`). Pulls in Werkzeug 2.x / Jinja 3.x; switches to `contextvars`
  (can break older extensions).
- **pyjwt 1.5.3 → 2.13.0 — 🔴 High.** `jwt.decode()` now **requires** the
  `algorithms` argument — existing calls without it fail. Removed
  `verify_expiration`/`verify`; `require_*` folded into `options={"require": [...]}`.
  Needs Python 3.9+ and `cryptography>=3`.
- **pillow 10.4.0 → 12.3.0 — 🔴 High.** Needs Python 3.10+ (11 dropped 3.8, 12
  dropped 3.9). `ImageCms` constants (e.g. `ImageCms.FLAGS['MATRIXINPUT']`)
  removed in favor of `ImageCms.Flags`. Internal helpers (`PSFile`, `PyAccess`,
  `Image.USE_CFFI_ACCESS`) removed.

---

## How to act on the results

1. **Let `risk_level` drive the decision:**
   - 🟢 **low** → `instructions` says *"Non-breaking change, proceed."* Safe to
     apply and auto-merge with the fix.
   - 🟡 **medium** → apply, but **test the specific behavior** the assessment
     calls out (e.g. urllib3 cert verification, pyyaml build).
   - 🔴 **high** → `instructions` says *inform the user first / prefer a
     non-breaking path.* Requires human review, tests, or a staged upgrade.
2. **Prefer the smallest `fixedIn` target that still closes the CVE.** As shown,
   `django@2.2.28` (🟢 low) fixes the critical SQLi that `django@4.2.17` (🔴 high)
   would also fix — with none of the breakage. Re-run `snyk_breakability_check`
   against the smaller target to confirm before choosing it.
3. **Plan multi-step upgrades** for `high`-risk majors you truly need
   (e.g. django 2.2 → 3.2 → 4.2).
4. **Gate CI on it:** auto-merge `low`, require a test run for `medium`, and
   require human review for `high`.

---

## Reproduce this demo

1. Ensure the Snyk MCP server is connected and you're authenticated
   (run `snyk_auth` if a tool reports you're not).
2. Run `snyk_sca_scan` with an **absolute** `path` and (for Python) `command: python3`.
3. From the results, pick a handful of upgrades. For each, note the current
   version **and** the full `fixedIn` list — include both the newest major and a
   smaller same-major target.
4. Call `snyk_breakability_check` once per candidate with `package_name`,
   `package_version_from`, and `package_version_to`.
5. Compare `risk_level` across targets and pick the **smallest safe fix**.

---

*Generated from a live run against `uv-goof/simple` on 2026-07-08 with Snyk MCP `v1.1305.2`. All `risk_level` values and assessments above are actual tool output.*
