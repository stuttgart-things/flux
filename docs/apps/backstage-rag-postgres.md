# Backstage RAG Postgres

A [CloudNativePG](https://cloudnative-pg.io)-managed PostgreSQL with the
[`pgvector`](https://github.com/pgvector/pgvector) extension, dedicated to the
Backstage [Roadie RAG-AI plugin](https://github.com/RoadieHQ/rag-ai) for storing
TechDocs/Catalog embeddings. Optional, second database — separate from the
Backstage core DB.

## Prerequisites

- [CNPG Operator](cnpg-operator.md) reconciled
- External Secrets controller + a Vault `ClusterSecretStore` (`vault-cluster`)
- A pgvector operand image pushed to `ghcr.io/stuttgart-things/postgresql-pgvector`
- A MinIO backup bucket (`backstage-rag-backups`) and bucket-scoped user

## Deploy

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: backstage-rag-postgres
  namespace: flux-system
spec:
  dependsOn:
    - name: backstage
    - name: cnpg-operator
    - name: external-secrets
  interval: 1h
  sourceRef:
    kind: GitRepository
    name: stuttgart-things # confirm the name in your cluster
  path: ./apps/backstage-rag-postgres
  prune: true
  wait: true
  postBuild:
    substitute:
      BACKSTAGE_NAMESPACE: portal
      STORAGE_CLASS: nfs4-csi
      INGRESS_DOMAIN: automation.sthings-vsphere.labul.sva.de
```

## Connection

```
host: rag-postgres-rw.<BACKSTAGE_NAMESPACE>.svc.cluster.local
db:   backstage_rag
user: rag
```

See [`apps/backstage-rag-postgres/README.md`](https://github.com/stuttgart-things/flux/tree/main/apps/backstage-rag-postgres)
for required Vault paths, image build, backups, verification and restore.
