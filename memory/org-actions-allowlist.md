---
name: org-actions-allowlist
description: stuttgart-things org restricts third-party GitHub Actions; unlisted ones cause startup_failure
metadata:
  type: project
---

The `stuttgart-things` GitHub org restricts which third-party Actions may run. A workflow that `uses:` an action not on the org allowlist fails with **`startup_failure`** — 0 jobs, no logs, no API-readable reason (only a web-UI banner). This looks identical to a YAML/parse error but is NOT — `actionlint` and the workflow JSON-schema pass clean.

**Why:** org-level Actions policy (Settings → Actions → Policies → Allowed actions).

**How to apply:** When a new workflow gets `startup_failure` despite passing `actionlint` / pre-commit, suspect a non-allowlisted third-party action before debugging YAML. Fix is org-side allowlisting (a repo admin does it), not a code change. First-party `actions/*` and `github/*` are always allowed. Verified 2026-07-15 with `cycjimmy/semantic-release-action` / `fluxcd/flux2/action` in the flux repo's Release workflow.
