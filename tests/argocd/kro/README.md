# kro on Argo CD

ArgoCD equivalent of [`cicd/kro`](../../../cicd/kro) (Flux). Single
`Application` that installs the kro OCI Helm chart, plus an `ApplicationSet`
for per-cluster fan-out.

## Layout

```
tests/argocd/kro/
├── apps/
│   └── kro.yaml                   # Helm Application (OCI chart)
├── clusters/
│   └── example/
│       ├── cluster.yaml           # per-cluster params for the ApplicationSet
│       └── values.yaml            # kro Helm values (empty by default)
├── root-app.yaml                  # (Option A) static App-of-Apps root
└── appset.yaml                    # (Option B) ApplicationSet, per-cluster fan-out
```

## Mapping from Flux

| Flux                                      | ArgoCD                                                |
|-------------------------------------------|-------------------------------------------------------|
| `requirements.yaml` (`Namespace` + OCI `HelmRepository`) | `CreateNamespace=true` + Argo CD OCI Helm source |
| `release.yaml` (HelmRelease, `install.crds: CreateReplace`) | `apps/kro.yaml` with `Replace=true` sync option |
| `${KRO_VERSION}`                          | `targetRevision` (inline or templated via ApplicationSet) |

The Flux HelmRelease sets `install.crds: CreateReplace` / `upgrade.crds: CreateReplace`.
The Argo CD Applications use `syncOptions: [Replace=true]` to achieve the same
effect for CRDs — CRDs are replaced rather than patched, matching kro's
release expectations.

## OCI Helm note

The chart lives at `oci://registry.k8s.io/kro/charts/kro`. Argo CD expresses
OCI Helm sources as:

```yaml
source:
  repoURL: registry.k8s.io/kro/charts
  chart: kro
  targetRevision: 0.9.1
```

No `oci://` prefix in `repoURL`. Argo CD 2.8+ with `helm.enableOciSupport` (on
by default in recent versions) is required.

## Deployment — Option A: static App-of-Apps

```bash
kubectl apply -f root-app.yaml
```

Applies the single `kro` Application with defaults from `apps/kro.yaml`.

## Deployment — Option B: ApplicationSet (multi-cluster)

1. Add a directory under `clusters/` with `cluster.yaml` + `values.yaml`. See
   `clusters/example/`.
2. Apply:

   ```bash
   kubectl apply -f appset.yaml
   ```

### `cluster.yaml` schema

```yaml
cluster:
  name: <short name used in Application names>
  server: <Kubernetes API URL or in-cluster URL>
kro:
  chartVersion: <Helm chart version, e.g. 0.9.1>
  namespace: <install namespace, typically kro-system>
```

## Prerequisites

- Argo CD installed in the `argocd` namespace.
- Argo CD must be able to pull from `registry.k8s.io` (OCI, anonymous).
