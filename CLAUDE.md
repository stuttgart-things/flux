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

## Dependency Management

Renovate is configured (`renovate.json`) with Flux-specific YAML file matching to automatically propose version updates for Helm charts and OCI artifacts.
