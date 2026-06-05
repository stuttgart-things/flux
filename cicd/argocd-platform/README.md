# argocd-platform

A **bundle** that stands up the full Argo CD platform from a single Flux
`Kustomization`. The consumer points one Kustomization at the bundle and gets
Argo CD, the clusterbook-operator, the reusable Argo CD config, and any
opted-in platform stacks — all correctly ordered via `dependsOn`.

## Layout

```
cicd/argocd-platform/
├── base/                  # the platform-free core (point here for "just Argo CD + operator")
│   ├── kustomization.yaml
│   ├── ks-argo-cd.yaml            → ./cicd/argo-cd            (HelmRelease)
│   ├── ks-clusterbook-operator.yaml → ./apps/clusterbook-operator  (dependsOn argo-cd)
│   ├── ks-argocd-config.yaml      → ./cicd/argocd-platform/base/config (dependsOn argo-cd)
│   └── config/                    # appset-cluster-projects + proj-cicd
├── components/            # one opt-in kustomize Component per catalog platform
│   ├── network/  security/  cicd/  storage/
│   ├── kind/
│   └── homerun2-pr-preview/  machinery-pr-preview/  machinery-catalog-locator-pr-preview/
└── overlays/
    └── full/              # base + ALL platforms enabled (copy & trim per cluster)
```

Nothing here lists raw manifests — every `ks-*.yaml` is a Flux `Kustomization`
CR. When the consumer's Kustomization builds the bundle, Flux substitutes
`${VAR:-default}` into those child CRs, so each ends up with concrete values.
`dependsOn` guarantees Argo CD is healthy before the operator or any Argo CD CR
(AppProject / ApplicationSet) applies — no CRD races.

## Platforms are opt-in (kustomize components)

The **base carries no platforms**. Each catalog platform
(`argocd-catalog/platforms/<name>`) is a kustomize *component* that adds one
`dependsOn`-ordered Flux `Kustomization` pointing at the `argocd-catalog`
source. You enable platforms by listing components in an overlay:

```yaml
# cicd/argocd-platform/overlays/<your-cluster>/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
components:
  - ../../components/network
  - ../../components/cicd
  # …add only what this cluster needs
```

`overlays/full` is a ready-made overlay with all 8 platforms enabled — copy it
and delete what you don't want. Enabling a platform is safe even if a cluster
uses none of it: the AppSets are **label-gated**, so an enabled-but-unlabeled
platform matches zero clusters and deploys nothing.

Available components: `network`, `security`, `cicd`, `storage`, `kind`,
`homerun2-pr-preview`, `machinery-pr-preview`, `machinery-catalog-locator-pr-preview`.

## The label chain

```
argo-cd up
  └─> clusterbook-operator   reconciles ClusterbookCluster CRs →
                             registers each cluster as an Argo CD cluster-secret + stamps labels
        └─> appset-cluster-projects  (cluster generator) → one AppProject per cluster
        └─> platform AppSets         (from argocd-catalog) → select on those labels → deploy
```

So two independent decisions: **which platforms are installed** (components in
the overlay, here) and **which clusters they target** (labels on the
`ClusterbookCluster` CRs, in the consumer repo).

## Consumer usage

Point a Flux `Kustomization` at `./cicd/argocd-platform/base` (platform-free) or
at an overlay path such as `./cicd/argocd-platform/overlays/full`:

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
  path: ./cicd/argocd-platform/overlays/full
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUX_SOURCE: apps-upstream
      ARGOCD_CATALOG_SOURCE: argocd-catalog
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
> `flux-system` on the target cluster. Enabling any platform component also
> requires the `argocd-catalog` GitRepository source (`${ARGOCD_CATALOG_SOURCE}`)
> on the cluster.

## Variables

```bash
task get-variables   # extract every ${VAR:-default} in this folder
```

| Variable | Default | Used by |
|---|---|---|
| `BUNDLE_NAME` | `argocd-platform` | child Kustomization names + `dependsOn` refs |
| `FLUX_SOURCE` | `apps-upstream` | `sourceRef.name` of the base child Kustomizations |
| `ARGOCD_CATALOG_SOURCE` | `argocd-catalog` | `sourceRef.name` of every platform component |
| `ARGO_CD_VERSION` | `9.4.15` | argo-cd |
| `ARGO_CD_NAMESPACE` | `argocd` | argo-cd, health check |
| `CLUSTERBOOK_OPERATOR_VERSION` | `v0.19.0` | clusterbook-operator |
| `CLUSTERBOOK_OPERATOR_NAMESPACE` | `clusterbook-system` | clusterbook-operator |

(plus the Argo CD ingress / issuer / AVP vars passed through to `cicd/argo-cd` —
see `base/ks-argo-cd.yaml`.)

> Run multiple isolated bundles on one cluster by setting a distinct
> `BUNDLE_NAME` per consumer Kustomization.
