# cnpg-operator

Deploys the [CloudNativePG](https://cloudnative-pg.io) (CNPG) operator — a
Kubernetes operator for managing PostgreSQL clusters declaratively.

This is a **cluster-wide** install: a single operator in `cnpg-system` watches
`Cluster` CRs in every namespace. It is a prerequisite for
[`apps/backstage-rag-postgres`](../backstage-rag-postgres), which deploys a
pgvector-enabled Postgres for the Backstage RAG-AI plugin.

## What Gets Deployed

1. **requirements.yaml** — `Namespace` (`cnpg-system` by default) and the
   `cloudnative-pg` HelmRepository (`https://cloudnative-pg.github.io/charts`).
2. **release.yaml** — the `cnpg-operator` HelmRelease (chart `cloudnative-pg`),
   installing the operator and its CRDs (`Cluster`, `Backup`, `ScheduledBackup`,
   `Pooler`, …) via `crds: CreateReplace`.

## Substitution Variables

| Var | Default | Notes |
|---|---|---|
| `CNPG_NAMESPACE` | `cnpg-system` | Namespace the operator runs in |
| `CNPG_VERSION` | `0.28.2` | `cloudnative-pg` chart version |
| `CNPG_CPU_REQUEST` | `100m` | Operator CPU request |
| `CNPG_MEMORY_REQUEST` | `100Mi` | Operator memory request |
| `CNPG_MEMORY_LIMIT` | `200Mi` | Operator memory limit |

Run `task get-variables` in this folder to (re)generate the list.

## Enabling in a Cluster

Per-cluster Flux `Kustomization`s live in `stuttgart-things/stuttgart-things`,
not in this repo. Point one at this path (confirm the `GitRepository` name your
cluster uses):

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: cnpg-operator
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things # confirm the actual name in your cluster
  path: ./apps/cnpg-operator
  prune: true
  wait: true
```

## Verify

```bash
kubectl -n cnpg-system get pods           # cnpg-controller-manager Running
flux get hr -n cnpg-system                # cnpg-operator Ready
kubectl get crd | grep cnpg.io            # clusters.postgresql.cnpg.io, ...
```
