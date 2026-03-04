# stuttgart-things/flux

Flux CD GitOps repository containing Kustomize overlays and Helm releases for deploying infrastructure and applications to Kubernetes clusters.

## How It Works

Consumers point a Flux `GitRepository` at this repo (by tag or branch), then create `Kustomization` resources referencing paths like `./apps/vault` or `./infra/cert-manager`. All configurable values use Flux variable substitution (`${VAR:-default}`) so deployments can be customized per cluster.

## Repository Structure

```
apps/      # Application HelmReleases and OCI kustomizations
infra/     # Infrastructure components (cert-manager, cilium, metallb, etc.)
cicd/      # CI/CD tooling (crossplane, tekton)
helmfiles/ # Legacy Helmfile definitions
workflows/ # Kaeffken workflow templates for cluster provisioning
```

## Component Anatomy

Each component directory is a self-contained Kustomize base. The `kustomization.yaml` composes from these files (include only what is needed):

| File | Purpose |
|---|---|
| `requirements.yaml` | Namespace + source (HelmRepository or OCIRepository) |
| `release.yaml` | HelmRelease or Kustomization pointing at an OCI source |
| `pre-release.yaml` | Resources needed before the main release (e.g., Certificates) |
| `post-release.yaml` | Post-deployment resources with `dependsOn` on the main release |
| `certificate.yaml` | cert-manager Certificate resource |
| `httproute.yaml` | Gateway API HTTPRoute (preferred over Ingress) |

## Quick Links

- [Getting Started](getting-started/prerequisites.md) — Prerequisites and first deployment
- [Bootstrap](bootstrap/overview.md) — Set up Flux on a cluster
- [Apps](apps/index.md) — Application components
- [Infrastructure](infra/index.md) — Infrastructure components
- [CI/CD](cicd/index.md) — CI/CD tooling
- [Development](development/adding-components.md) — Contributing new components
