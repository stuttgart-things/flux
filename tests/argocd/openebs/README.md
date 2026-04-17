# OpenEBS on Argo CD

ArgoCD equivalent of [`infra/openebs`](../../../infra/openebs) (Flux). Single
`Application` that installs the OpenEBS umbrella Helm chart, plus an
`ApplicationSet` for per-cluster fan-out.

## Layout

```
tests/argocd/openebs/
├── apps/
│   └── openebs.yaml               # Helm Application (umbrella chart)
├── clusters/
│   └── example/
│       ├── cluster.yaml           # per-cluster params for the ApplicationSet
│       └── values.yaml            # OpenEBS Helm values
├── root-app.yaml                  # (Option A) static App-of-Apps root
└── appset.yaml                    # (Option B) ApplicationSet, per-cluster fan-out
```

## Mapping from Flux

| Flux                                         | ArgoCD                                                |
|----------------------------------------------|-------------------------------------------------------|
| `requirements.yaml` (`Namespace` + `HelmRepository`) | `CreateNamespace=true` + Argo CD's built-in Helm source |
| `release.yaml` (HelmRelease)                 | `apps/openebs.yaml`                                   |
| `${VAR:-default}`                            | Helm `valuesObject` / `valueFiles`                    |

## Engine toggles

The defaults match the Flux release: every optional engine (`local.lvm`,
`local.zfs`, `replicated.mayastor`) is **off**. Only the local-pv engines
shipped by default are enabled. To opt into another engine, edit `values.yaml`
(or your cluster's overlay) — for example:

```yaml
engines:
  replicated:
    mayastor:
      enabled: true
mayastor:
  csi:
    node:
      initContainers:
        enabled: true
```

Mayastor additionally needs hugepages and the NVMe-TCP kernel module on the
node — handle that outside Argo CD.

## Deployment — Option A: static App-of-Apps

```bash
kubectl apply -f root-app.yaml
```

Applies the single `openebs` Application with the defaults from `apps/openebs.yaml`.

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
openebs:
  chartVersion: <Helm chart version, e.g. 4.2.0>
  namespace: <install namespace, typically openebs>
```

## Prerequisites

- Argo CD installed in the `argocd` namespace.
- A default StorageClass is intentionally NOT marked default by this chart —
  set one explicitly if needed.
