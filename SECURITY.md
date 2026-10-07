# MARIA — Security Policy & Design

Security is a foundational design principle of MARIA, not an afterthought. This document describes the security model, threat mitigations, and rules that all contributors must follow.

---

## Core Security Principles

### 1. Never Expose Credentials

- **No API keys in source code.** Ever. Not even in comments, examples, or tests.
- **No hard-coded credentials.** All secrets come from environment variables or encrypted storage.
- **`.env` files are gitignored.** The repository only contains `.env.example` with placeholder values.
- **BYOK (Bring Your Own Key).** Users provide their own API keys. MARIA never ships with keys.

### 2. Least-Privilege Permissions

- Every tool declares the **minimum permissions** it needs.
- The permission engine grants only what is declared.
- Tools cannot escalate their own privileges.
- Default policy: **deny all, grant explicitly.**

### 3. Human-in-the-Loop

- **Critical actions always require human confirmation:**
  - Deleting files
  - Executing system commands
  - Modifying system settings
  - Sending messages on behalf of the user
  - Making purchases or financial transactions
  - Accessing sensitive data
- The confirmation prompt clearly describes what will happen.
- "Approve all" is never available for CRITICAL-risk actions.

### 4. Defense in Depth

- Multiple layers of protection, not just one.
- Even if one layer fails, others still protect the user.

---

## Permission Model

### Risk Levels

| Level | Description | Approval |
|-------|-------------|----------|
| `LOW` | Read-only, non-sensitive (e.g., list files in a directory) | Auto-approved |
| `MEDIUM` | Potentially impactful but reversible (e.g., create a file) | Auto-approved with logging |
| `HIGH` | Significant impact, hard to reverse (e.g., delete files, run commands) | Requires human confirmation |
| `CRITICAL` | Irreversible or highly sensitive (e.g., system modification, send messages) | Always requires confirmation + stated reason |

### Permission Categories

```
filesystem.read        — Read files and directories
filesystem.write       — Create or modify files
filesystem.delete      — Delete files or directories
terminal.execute       — Run shell commands
terminal.admin         — Run elevated/admin commands
browser.navigate       — Open URLs
browser.interact       — Click, type, submit forms
git.read               — Read git status, log, diff
git.write              — Commit, push, create branches
system.info            — Read system information
system.modify          — Change system settings
network.request        — Make HTTP requests
messaging.send         — Send messages on behalf of user
```

### Permission Grants

Permissions are granted per-session by default. Persistent grants can be configured but require explicit user setup:

```yaml
# Example permission policy (future config format)
permissions:
  defaults:
    filesystem.read: allow
    filesystem.write: prompt
    filesystem.delete: prompt
    terminal.execute: prompt
    terminal.admin: deny
    system.modify: deny
  trusted_directories:
    - "~/projects"
    - "~/documents"
```

---

## Credential Storage

### Architecture

```
User provides API key
        │
        ▼
  Encryption (Fernet / AES-256)
        │
        ▼
  Stored in local encrypted file
  (~/.maria/credentials.enc)
        │
        ▼
  Master key derived from:
  - Windows DPAPI (preferred)
  - OS keyring
  - User-provided passphrase (fallback)
```

### Rules

1. Credentials are **encrypted at rest.**
2. Credentials are **never logged**, even at DEBUG level.
3. Credentials are **never sent to AI providers** as part of conversation content.
4. Credentials are **never included in error messages or stack traces.**
5. The credential store is **excluded from backups** by default.

---

## Audit Logging

All security-relevant events are logged to an append-only audit log:

- Tool executions (what, when, parameters, result status)
- Permission checks (what was requested, what was decided)
- Human confirmations (what was shown, what was decided)
- Credential access (which credential, by which component)
- Authentication events

The audit log:
- Is stored locally in `~/.maria/audit/`.
- Uses structured JSON format.
- Is append-only (MARIA never modifies past entries).
- Can be reviewed by the user at any time.

---

## Autonomous Mode Safety

When MARIA operates in autonomous/sleep mode (future):

1. **Strict action whitelist.** Only pre-approved action types are allowed.
2. **No CRITICAL actions.** Anything rated CRITICAL is queued for human review.
3. **Rate limiting.** Maximum actions per time window.
4. **Kill switch.** User can instantly halt all autonomous operations.
5. **Summary reports.** MARIA reports what it did during autonomous periods.

---

## Network Security

- **Local-first.** MARIA runs on localhost by default.
- **No open ports** unless explicitly configured.
- **Android ↔ PC communication** will use encrypted WebSocket (TLS).
- **API keys** are sent only to their respective AI provider endpoints.
- **No telemetry.** MARIA does not phone home.

---

## For Contributors

### Security Checklist

Before submitting code, verify:

- [ ] No secrets, API keys, or credentials in the code.
- [ ] No secrets in test fixtures or example data.
- [ ] New tools declare accurate `risk_level` and `required_permissions`.
- [ ] HIGH/CRITICAL actions include human confirmation.
- [ ] Credentials are accessed only through the credential vault.
- [ ] Error messages do not leak sensitive information.
- [ ] User input is validated before use.
- [ ] File paths are sanitized (no path traversal).
- [ ] Shell commands are parameterized (no injection).

### Reporting Vulnerabilities

If you discover a security vulnerability, please **do not** open a public issue. Instead:

1. Email the maintainer directly (address to be published).
2. Include a clear description and reproduction steps.
3. Allow reasonable time for a fix before disclosure.

---

*Security is everyone's responsibility. When in doubt, err on the side of caution.*
