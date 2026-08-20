# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a Flux CD GitOps repository containing Kustomize overlays and Helm releases for deploying infrastructure and applications to Kubernetes clusters. Consumers point a Flux `GitRepository` at this repo (by tag/branch), then create `Kustomization` resources referencing paths like `./apps/vault` or `./infra/cert-manager`.

## Task Commands

This project uses [go-task](https://taskfile.dev) instead of Make. The Taskfile also includes remote git tasks from `stuttgart-things/tasks`.

```bash
task get-variables   # Extract all ${VAR:-default} substitution variables from an app folder
task release         # Run semantic-release (dry-run then actual) and push a new version tag
task do              # Interactive task picker (requires gum)

task check-renovate    # Fail if a substituted chart version lacks its "# renovate:" annotation
task lint-renovate     # Validate renovate.json against the current Renovate schema
task preview-renovate  # Dry-run Renovate locally and list the updates it would propose
task verify-image-tags # Check every substituted image tag actually exists in its registry
task pr              # Create a pull request (via included git tasks)
```

To list all available tasks: `task -l`

## Repository Structure

```
apps/      # Application HelmReleases and OCI kustomizations
infra/     # Infrastructure components (cert-manager, cilium, metallb, etc.)
cicd/      # CI/CD tooling (crossplane, tekton)
helmfiles/ # Legacy Helmfile definitions
workflows/ # Kaeffken workflow templates for cluster provisioning
```

## App/Infra Component Anatomy

Each component directory is a self-contained Kustomize base. The `kustomization.yaml` composes from these files (include only what is needed):

| File | Purpose |
|---|---|
| `requirements.yaml` | Namespace + source (HelmRepository or OCIRepository) |
| `release.yaml` | HelmRelease or Kustomization pointing at an OCI source |
| `pre-release.yaml` | Resources needed before the main release (e.g., Certificates via `sthings-cluster` chart) |
| `post-release.yaml` | Post-deployment resources with `dependsOn` on the main release |
| `certificate.yaml` | cert-manager Certificate resource (via `sthings-cluster` chart) |
| `httproute.yaml` | Gateway API HTTPRoute (preferred over Ingress) |

### Two Source Patterns

**HelmRepository** (for Helm charts published to OCI or HTTPS registries):
```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
spec:
  type: oci
  url: oci://ghcr.io/stuttgart-things
```

**OCIRepository** (for apps shipping their own kustomize manifests as OCI artifacts):
```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
spec:
  url: oci://ghcr.io/stuttgart-things/<app>-kustomize
  ref:
    tag: ${APP_VERSION:-v0.0.0}
```

When using OCIRepository, `release.yaml` contains a Flux `Kustomization` (not a `HelmRelease`) and uses `patches:` to override images, remove Ingress, etc.

### Key Patterns

**`sthings-cluster` helper chart**: Used extensively to create arbitrary Kubernetes custom resources (Certificates, ClusterIssuers, Secrets) via HelmRelease values. Appears in `pre-release.yaml`, `post-release.yaml`, and `certificate.yaml` files.

**Release ordering with `dependsOn`**: Post-release HelmReleases use `spec.dependsOn` to wait for the main release. Example: cert-manager's `post-release.yaml` creates a ClusterIssuer only after cert-manager itself is running.

**Gateway API over Ingress**: New components use `httproute.yaml` with Gateway API `HTTPRoute` instead of Helm chart ingress fields. Set `INGRESS_ENABLED: false` in the HelmRelease and provide a separate HTTPRoute resource.

## Variable Substitution

All configurable values use Flux's `postBuild.substitute` pattern with the syntax `${VAR_NAME:-default_value}`. Variables are UPPERCASE with underscores. The consumer's `Kustomization` CR provides values at deploy time.

Run `task get-variables` to extract all variables and their defaults from any app folder.

## Commit Convention

Uses Angular commit convention for semantic-release (configured in `.releaserc`). Format: `type: description`

- `feat:` → minor version bump
- `fix:` → patch version bump
- `BREAKING CHANGE` in footer → major bump

Tags follow `v${version}` format (e.g., `v1.3.0`).

## Release & OCI Artifact Publishing

The `Release` workflow (`.github/workflows/release.yaml`) runs on every push to `main`:

1. **release** – semantic-release cuts the SemVer tag + GitHub Release and updates `CHANGELOG.md`. Releases now happen in CI — do **not** run `task release` locally as well (it would race on the tag/CHANGELOG).
2. **plan** – resolves the version tag (new release version, else the latest existing tag) and diffs the merge to find changed `apps/*` / `infra/*` components.
3. **push** – packages each **changed** component as a Flux OCI artifact via `flux push artifact`.

- **Naming:** `oci://ghcr.io/stuttgart-things/flux/<apps|infra>/<name>` (e.g. `flux/apps/vault`)
- **Tags:** the release version (e.g. `v1.17.0`) **and** the rolling `latest`
- Only changed components get the new version tag; unchanged components keep their existing tags (content — and therefore `latest` — is unchanged). Consumers reference an artifact via `OCIRepository` instead of `GitRepository` (see README → OCI ARTIFACTS).

**Manual backfill / re-push:** the workflow also has a `workflow_dispatch` trigger with a `push-all` boolean input (default `true`). Running it publishes **all** `apps/*` and `infra/*` components at the current release version — used to seed the registry or force a re-push. On manual dispatch the `release` job is skipped (no new tag is cut); the version tag is taken from the latest existing git tag.

```bash
gh workflow run release.yaml --ref main -f push-all=true    # backfill everything
gh workflow run release.yaml --ref main -f push-all=false   # changed-only (rarely useful manually)
```

Note: because `release` is skipped on manual dispatch, the `push` job is gated on `!cancelled() && needs.plan.result == 'success'` — otherwise the skipped `release` would propagate a transitive skip through `plan` and yield an empty push matrix.

Note: the workflow uses third-party actions (semantic-release, flux2). The `stuttgart-things` org restricts non-first-party actions — an unlisted one fails the run with `startup_failure` (0 jobs, no logs) despite passing actionlint; the fix is org-side allowlisting, not a code change.

## SOPS Secrets Encryption

Encrypt/decrypt secrets using Dagger SOPS module with Age keys:

```bash
# Encrypt
export AGE_PUBLIC_KEY="age1..."
dagger call -m github.com/stuttgart-things/dagger/sops encrypt \
  --age-key="env:AGE_PUBLIC_KEY" --plaintext-file="./secret.yaml" \
  --file-extension="yaml" export --path="./secret.enc.yaml"

# Decrypt
export SOPS_AGE_KEY="AGE-SECRET-KEY-1..."
dagger call -m github.com/stuttgart-things/dagger/sops decrypt \
  --age-key="env:SOPS_AGE_KEY" --encrypted-file="./secret.enc.yaml" contents
```

Flux decryption is wired via the `sops-age` secret in `flux-system` and a kustomize-controller patch on the FluxInstance.

## Pre-commit Hooks

Run `pre-commit run --all-files` to validate before pushing. Active checks: trailing whitespace, end-of-file-fixer, large files, merge conflicts, symlinks, private key detection, shellcheck, hadolint, GitHub Actions schema validation, and high-entropy secret detection.

## CI Gate

`.github/workflows/validate.yaml` runs on every pull request and blocks the merge on three jobs:

| Job | Runs |
|---|---|
| Chart version annotations | `hack/check-chart-annotations.sh` |
| Image tags resolve | `hack/verify-image-tags.py` |
| Renovate config | `renovate-config-validator` on Node 24 |

The workflow calls the scripts directly rather than going through `task`. The Taskfile includes a remote Taskfile, which `task` refuses to load unattended (`not trusted by user`, exit 104) unless given `--yes` — and that would mean trusting a network-fetched Taskfile on every CI run. The `task` targets call the same scripts, so local and CI run identical code.

## Dependency Management

Renovate is configured (`renovate.json`) with Flux-specific YAML file matching to automatically propose version updates for Helm charts and OCI artifacts.

### Chart versions need a `# renovate:` annotation

Renovate's `flux` manager reads `chart.spec.version`, but it cannot parse Flux
variable substitution — `version: ${VAULT_VERSION:-1.9.0}` is skipped with
`skipReason: contains-variable` and produces **no PR, no warning, no log entry**.

Every HelmRelease whose chart version uses `${VAR:-default}` therefore carries a
comment naming the datasource and where to look it up. A `customManager` in
`renovate.json` matches the comment plus the following `version:` line and
updates the default in place:

```yaml
  chart:
    spec:
      chart: cert-manager
      # renovate: datasource=helm depName=cert-manager registryUrl=https://charts.jetstack.io
      version: ${CERT_MANAGER_VERSION:-v1.19.2}
```

Derive the annotation from the `HelmRepository` the `sourceRef` points at:

| HelmRepository | Annotation |
|---|---|
| `type: oci`, `url: oci://<host>/<path>` | `datasource=docker depName=<host>/<path>/<chart>` |
| plain HTTPS repo | `datasource=helm depName=<chart> registryUrl=<url>` |

**When adding a HelmRelease, add the annotation too** — without it the chart is
silently invisible to Renovate and will never be updated.

`task check-renovate` fails on any chart version that is missing its annotation, and
`task preview-renovate` runs the real Renovate against the working tree (writing
nothing) to list the updates it would propose plus any lookup failures.

Note the substitution variable may contain digits (`${HOMERUN2_REDIS_VERSION:-17.1.4}`),
so every `matchStrings` regex in `renovate.json` uses `[A-Z0-9_]+` — a narrower
`[A-Z_]+` silently skips those components.

### Never set `extractVersionTemplate` on these managers

`extractVersion` does not only normalise the version for comparison — Renovate
writes the **extracted** value back. With `^v?(?<version>.*)$` a registry tag of
`v0.8.2` is written as `0.8.2`, and since most `ghcr.io/stuttgart-things/*`
artifacts are tagged **with** the `v`, the result is a default that resolves to
no tag at all. That failure only surfaces at deploy time.

Leave the field off and each datasource's own versioning applies, so the tag is
written back exactly as the registry publishes it — `v0.5.0` stays `v0.5.0`,
`1.25.9` stays `1.25.9`.

`task verify-image-tags` resolves every substituted default against the real
registry and is the check that catches this class of breakage.

### homerun2 components group per component

Each homerun2 component ships two artifacts — the image and its `-kustomize` OCI
artifact — driven by one substitution variable. If Renovate bumped them in
separate PRs they could be merged apart, and a variable pointing at a tag only
one of them has resolves to nothing (this is what broke `demo-pitcher`, #208).

A `packageRule` therefore groups them by component, so both always move in the
same PR:

```json
"groupName": "homerun2 {{{replace '-kustomize$' '' (replace '^ghcr\\.io/stuttgart-things/homerun2-' '' depName)}}}"
```

It sits after the broad `stuttgart-things images` rule and overrides it for
`homerun2-**`; everything else stays in the combined group. Verify group names
with `task preview-renovate` — they appear as branch names before any PR exists.
