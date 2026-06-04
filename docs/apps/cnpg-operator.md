# CNPG Operator

The [CloudNativePG](https://cloudnative-pg.io) operator for managing PostgreSQL
clusters declaratively. Cluster-wide install in `cnpg-system`; a prerequisite
for [Backstage RAG Postgres](backstage-rag-postgres.md).

## Deploy

Point a Flux `Kustomization` at `./apps/cnpg-operator`:

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: cnpg-operator
  namespace: flux-system
spec:
  interval: 1h
  sourceRef:
    kind: GitRepository
    name: stuttgart-things # confirm the name in your cluster
  path: ./apps/cnpg-operator
  prune: true
  wait: true
```

## Substitution Variables

| Var | Default |
|---|---|
| `CNPG_NAMESPACE` | `cnpg-system` |
| `CNPG_VERSION` | `0.28.2` |

See [`apps/cnpg-operator/README.md`](https://github.com/stuttgart-things/flux/tree/main/apps/cnpg-operator)
for the full reference.
