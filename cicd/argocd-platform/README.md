# argocd-platform

A **bundle** that stands up the full Argo CD platform from a single Flux
`Kustomization`. Instead of the consumer wiring up Argo CD, the
clusterbook-operator, and the Argo CD config as three separate Kustomizations,
they point one Kustomization at `./cicd/argocd-platform` and get all three —
correctly ordered.

## What it deploys

```
argocd-platform-argo-cd            # ./cicd/argo-cd            (HelmRelease — Argo CD itself)
  ├─ argocd-platform-clusterbook-operator   # ./apps/clusterbook-operator   (dependsOn argo-cd)
  └─ argocd-platform-argocd-config          # ./cicd/argocd-platform/config (dependsOn argo-cd)
```

The bundle's `kustomization.yaml` does not list raw manifests — it lists three
Flux `Kustomization` CRs (`ks-*.yaml`). When the consumer's Kustomization builds
the bundle, Flux substitutes `${VAR:-default}` into those child CRs, so each one
ends up with concrete `postBuild.substitute` values. `dependsOn` guarantees
Argo CD is healthy before the operator or any Argo CD CR (AppProject /
ApplicationSet) is applied — avoiding CRD races.

## The label chain

```
argo-cd up
  └─> clusterbook-operator   reconciles ClusterbookCluster CRs →
                             registers each cluster as an Argo CD cluster-secret + stamps labels
        └─> appset-cluster-projects  (cluster generator) → one AppProject per cluster
        └─> platform AppSets         (from argocd-catalog) → select on those labels → deploy
```

## What is / isn't in the bundle

| In the bundle (fleet-generic, reusable) | Stays per-cluster (consumer repo) |
|---|---|
| `cicd/argo-cd` (Argo CD install) | `ClusterbookCluster` CRs (`clusterbook-cluster-<name>.yaml`) |
| `apps/clusterbook-operator` | Which platforms to enable (`*-platform-appsets.yaml` → `argocd-catalog`) |
| `config/appset-cluster-projects.yaml` (AppProject per cluster) | Label gates on the ClusterbookCluster CR (`network-platform/*`, …) |
| `config/proj-cicd.yaml` (cicd AppProject) | |

Platform selection is label-driven on the `ClusterbookCluster` CR, so the bundle
stays generic and each fleet opts into platforms without forking it.

## Consumer usage

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: argocd-platform
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: apps-upstream          # url: https://github.com/stuttgart-things/flux.git
  path: ./cicd/argocd-platform
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUX_SOURCE: apps-upstream
      ARGO_CD_VERSION: "9.4.15"
      ARGO_CD_NAMESPACE: argocd
      INGRESS_DOMAIN: platform.sthings-vsphere.labul.sva.de
      CLUSTERBOOK_OPERATOR_VERSION: v0.19.0
      # …override any ${VAR} from `task get-variables`
    substituteFrom:
      - kind: Secret
        name: argocd-secrets
```

> The `${ARGO_CD_*}` substitutions feed `cicd/argo-cd`, which also reads the
> `argocd-secrets` Secret via `substituteFrom`. That Secret must exist in
> `flux-system` on the target cluster.

## Variables

```bash
task get-variables   # extract every ${VAR:-default} in this folder
```

| Variable | Default | Used by |
|---|---|---|
| `BUNDLE_NAME` | `argocd-platform` | child Kustomization names + `dependsOn` refs |
| `FLUX_SOURCE` | `apps-upstream` | `sourceRef.name` of every child Kustomization |
| `ARGO_CD_VERSION` | `9.4.15` | argo-cd |
| `ARGO_CD_NAMESPACE` | `argocd` | argo-cd, health check |
| `CLUSTERBOOK_OPERATOR_VERSION` | `v0.19.0` | clusterbook-operator |
| `CLUSTERBOOK_OPERATOR_NAMESPACE` | `clusterbook-system` | clusterbook-operator |

(plus the Argo CD ingress / issuer / AVP vars passed through to `cicd/argo-cd` —
see `ks-argo-cd.yaml`.)

> Run multiple isolated bundles on one cluster by setting a distinct
> `BUNDLE_NAME` per consumer Kustomization.
