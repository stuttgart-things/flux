# backstage-rag-postgres

A [CloudNativePG](https://cloudnative-pg.io) (CNPG) managed PostgreSQL with the
[`pgvector`](https://github.com/pgvector/pgvector) extension, dedicated to the
Backstage [Roadie RAG-AI plugin](https://github.com/RoadieHQ/rag-ai)
(`@roadiehq/rag-ai`) for storing TechDocs/Catalog embeddings.

This is a **second**, optional Postgres — it does **not** touch the Backstage
core database (the embedded Bitnami Postgres in `apps/backstage`). Deploy it only
in clusters that run the RAG plugin.

## What Gets Deployed

Into `${BACKSTAGE_NAMESPACE}` (default `portal`):

1. **external-secret.yaml** — two `ExternalSecret`s (ESO → Vault):
   - `rag-postgres-creds` (`kubernetes.io/basic-auth`) — owner `username`/`password`
   - `rag-postgres-s3-creds` — MinIO `ACCESS_KEY_ID`/`SECRET_ACCESS_KEY` for backups
2. **cluster.yaml** — the CNPG `Cluster` (`rag-postgres`): 1 instance, custom
   pgvector image, `backstage_rag` DB owned by `rag`, `CREATE EXTENSION vector`,
   5Gi storage, and WAL/base backups to MinIO via `barmanObjectStore`.
3. **backup.yaml** — a Velero `Schedule` backing up the Kubernetes objects
   (Cluster CR + the two ExternalSecrets, selected by label
   `backup=backstage-rag-postgres`). Database *contents* are covered by CNPG's
   own S3 backup; this covers the K8s *objects* for full DR.

## Prerequisites

- [`apps/cnpg-operator`](../cnpg-operator) reconciled (provides the CNPG CRDs)
- [`infra/external-secrets`](../../infra/external-secrets) — ESO controller **and**
  a Vault-backed `ClusterSecretStore` (default name `vault-cluster`)
- A reachable MinIO and a pre-created backup bucket (see [Backups](#backups))
- The pgvector operand image pushed to GHCR (see [Building the image](#building-the-pgvector-image))

## Substitution Variables

Run `task get-variables` in this folder for the full list. Key ones:

| Var | Default | Notes |
|---|---|---|
| `BACKSTAGE_NAMESPACE` | `portal` | Namespace (same as Backstage) |
| `STORAGE_CLASS` | `nfs4-csi` | PVC storage class |
| `RAG_PG_IMAGE` | `ghcr.io/stuttgart-things/postgresql-pgvector` | pgvector operand image |
| `RAG_PG_IMAGE_TAG` | `16` | Image tag (PG major) |
| `RAG_PG_DATABASE` | `backstage_rag` | Bootstrap database |
| `RAG_PG_OWNER` | `rag` | DB owner role |
| `RAG_PG_STORAGE_SIZE` | `5Gi` | Volume size |
| `RAG_ESO_STORE_NAME` | `vault-cluster` | `ClusterSecretStore` name |
| `RAG_ESO_CREDS_PATH` | `kv/data/${BACKSTAGE_NAMESPACE}/rag-postgres` | Vault KV v2 path (owner creds) |
| `RAG_ESO_S3_PATH` | `kv/data/${BACKSTAGE_NAMESPACE}/rag-postgres-s3` | Vault KV v2 path (S3 creds) |
| `RAG_S3_BUCKET` | `backstage-rag-backups` | Backup bucket |
| `RAG_S3_ENDPOINT` | `https://artifacts.${INGRESS_DOMAIN}` | MinIO S3 endpoint |
| `RAG_BACKUP_RETENTION` | `7d` | CNPG backup retention |
| `VELERO_NAMESPACE` | `velero` | Namespace for the `Schedule` |
| `RAG_VELERO_CRON` | `0 1 * * *` | Velero schedule (daily 01:00) |
| `RAG_VELERO_TTL` | `168h0m0s` | Velero retention (7 days) |

## Required Vault Secrets

Populate these KV v2 paths (defaults assume the `kv` mount; adjust to your
`ClusterSecretStore` `path`):

| Vault path | Keys |
|---|---|
| `kv/<ns>/rag-postgres` | `username`, `password` (the `rag` DB owner) |
| `kv/<ns>/rag-postgres-s3` | `access_key`, `secret_key` (bucket-scoped MinIO user) |

## Building the pgvector image

CNPG's standard images don't bundle pgvector, so we ship a thin operand image
(see [`image/Dockerfile`](image/Dockerfile)). Build & push manually (no CI yet):

```bash
docker buildx build \
  --platform linux/amd64 \
  -t ghcr.io/stuttgart-things/postgresql-pgvector:16 \
  --push apps/backstage-rag-postgres/image
```

The CNPG operand image is pulled by the kubelet (not Flux), so the GHCR package
must be **public** — otherwise pods fail with `ErrImagePull`. New packages
default to private; make it public once (Package settings → Change visibility),
or add an `imagePullSecret` to the namespace and reference it via
`spec.imagePullSecrets` in `cluster.yaml`.

## Backups

CNPG writes WAL + base backups to MinIO via `barmanObjectStore`. Pre-create the
bucket and a bucket-scoped user (same approach as
[`infra/velero/README.md`](../../infra/velero/README.md)):

```bash
mc mb myminio/backstage-rag-backups          # create the bucket
# then create a user limited to that bucket and store its access/secret key in
# Vault at kv/<ns>/rag-postgres-s3
```

## Enabling in a Cluster

Per-cluster Flux `Kustomization`s live in `stuttgart-things/stuttgart-things`,
not here. Add one referencing this path (confirm the `GitRepository` name):

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
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things # confirm the actual name in your cluster
  path: ./apps/backstage-rag-postgres
  prune: true
  wait: true
  postBuild:
    substitute:
      BACKSTAGE_NAMESPACE: portal
      STORAGE_CLASS: nfs4-csi
      INGRESS_DOMAIN: automation.sthings-vsphere.labul.sva.de
```

## Connecting from the RAG plugin

CNPG creates `-rw` (primary), `-ro` (replicas) and `-r` (any) services. Point
the Roadie RAG plugin at the read-write service:

```
host:     rag-postgres-rw.${BACKSTAGE_NAMESPACE}.svc.cluster.local
port:     5432
database: backstage_rag
user:     rag            # password from the rag-postgres-creds secret
```

## Verify

```bash
# Cluster healthy, primary elected
kubectl -n portal get cluster rag-postgres
kubectl -n portal get pods -l cnpg.io/cluster=rag-postgres

# pgvector present
kubectl -n portal exec -it rag-postgres-1 -- \
  psql -U rag -d backstage_rag -c "\dx vector"

# Services (expect rag-postgres-rw / -ro / -r)
kubectl -n portal get svc | grep rag-postgres

# vector smoke test
kubectl -n portal run pgtest --rm -it --image=postgres:16 -- \
  psql "postgresql://rag@rag-postgres-rw:5432/backstage_rag" \
  -c "SELECT '[1,2,3]'::vector;"

# backups
kubectl -n portal get backup
```

## Restore

CNPG restores into a **new** cluster from the Barman object store. Sketch:

```yaml
spec:
  bootstrap:
    recovery:
      source: rag-postgres
  externalClusters:
    - name: rag-postgres
      barmanObjectStore:
        destinationPath: s3://backstage-rag-backups/
        endpointURL: https://artifacts.<INGRESS_DOMAIN>
        s3Credentials:
          accessKeyId:    { name: rag-postgres-s3-creds, key: ACCESS_KEY_ID }
          secretAccessKey: { name: rag-postgres-s3-creds, key: SECRET_ACCESS_KEY }
```

See the [CNPG recovery docs](https://cloudnative-pg.io/documentation/current/recovery/).
