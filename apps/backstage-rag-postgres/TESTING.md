# Testing: backstage-rag-postgres + cnpg-operator

A runbook for validating this app on a test cluster. Two paths: a no-cluster
render check first, then a real Flux reconcile from this branch.

> Branch under test: `feat/backstage-rag-pgvector` (PR
> [#156](https://github.com/stuttgart-things/flux/pull/156)).

## Key facts

| Thing | Value |
|---|---|
| Operator | `apps/cnpg-operator` → ns `cnpg-system`, chart `cloudnative-pg` 0.28.2 |
| DB app | `apps/backstage-rag-postgres` → ns `portal` (`BACKSTAGE_NAMESPACE`) |
| Cluster CR | `rag-postgres`; services `rag-postgres-{rw,ro,r}` |
| DB / owner | `backstage_rag` / `rag` |
| Image (must exist) | `ghcr.io/stuttgart-things/postgresql-pgvector:16` |
| ESO store | `vault-cluster` (`ClusterSecretStore`), KV v2 |
| Vault paths | `kv/<ns>/rag-postgres` (`username`,`password`), `kv/<ns>/rag-postgres-s3` (`access_key`,`secret_key`) |
| Backup bucket | `backstage-rag-backups` on MinIO |

## tmux layout

```bash
tmux new -s rag
# Ctrl-b "  → split; in the bottom pane run the watchers:
watch -n5 'kubectl -n portal get cluster,pods,svc -l cnpg.io/cluster=rag-postgres 2>/dev/null; echo; flux get hr -n cnpg-system'
# top pane = run the steps below
```

## Step 0 — no-cluster render check (fast, safe)

```bash
cd ~/projects/flux
# raw kustomize (vars stay literal — just checks structure)
kustomize build apps/cnpg-operator
kustomize build apps/backstage-rag-postgres

# render WITH substitution exactly like Flux will, then server-dry-run
export BACKSTAGE_NAMESPACE=portal STORAGE_CLASS=nfs4-csi \
       INGRESS_DOMAIN=automation.sthings-vsphere.labul.sva.de
kustomize build apps/backstage-rag-postgres | envsubst | \
  kubectl apply --dry-run=server -f -   # needs CNPG CRDs already on cluster
```

## Step 1 — prerequisites (one-time, env-specific)

```bash
# 1a. build + push the pgvector image (needs: docker login ghcr.io)
docker buildx build --platform linux/amd64 \
  -t ghcr.io/stuttgart-things/postgresql-pgvector:16 \
  --push apps/backstage-rag-postgres/image

# 1b. MinIO bucket (needs: mc alias 'myminio' configured)
mc mb myminio/backstage-rag-backups

# 1c. Vault secrets (needs: vault login) — adjust mount/path to your CSS
vault kv put kv/portal/rag-postgres    username=rag password='<pw>'
vault kv put kv/portal/rag-postgres-s3 access_key='<minio-key>' secret_key='<minio-secret>'
```

## Step 2 — point Flux at the branch & reconcile

This repo is consumed by per-cluster Kustomizations, so the cleanest test is to
temporarily point a `GitRepository` at this branch and apply two Flux
`Kustomization`s to the **test** cluster (adjust the source name/URL if the
cluster already has one).

```bash
kubectl apply -f - <<'EOF'
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-rag-test
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/stuttgart-things/flux
  ref:
    branch: feat/backstage-rag-pgvector
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata: { name: cnpg-operator, namespace: flux-system }
spec:
  interval: 5m
  sourceRef: { kind: GitRepository, name: flux-rag-test }
  path: ./apps/cnpg-operator
  prune: true
  wait: true
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata: { name: backstage-rag-postgres, namespace: flux-system }
spec:
  dependsOn:
    - { name: cnpg-operator }
  interval: 5m
  sourceRef: { kind: GitRepository, name: flux-rag-test }
  path: ./apps/backstage-rag-postgres
  prune: true
  wait: true
  postBuild:
    substitute:
      BACKSTAGE_NAMESPACE: portal
      STORAGE_CLASS: nfs4-csi
      INGRESS_DOMAIN: automation.sthings-vsphere.labul.sva.de
EOF

flux reconcile source git flux-rag-test
flux get kustomizations
```

## Step 3 — verify

```bash
kubectl -n cnpg-system get pods                         # operator Running
kubectl -n portal get cluster rag-postgres              # phase: Cluster in healthy state
kubectl -n portal get pods -l cnpg.io/cluster=rag-postgres
kubectl -n portal get externalsecret                    # both SecretSynced=True

# pgvector present
kubectl -n portal exec -it rag-postgres-1 -- \
  psql -U rag -d backstage_rag -c "\dx vector"

# vector smoke test
kubectl -n portal run pgtest --rm -it --image=postgres:16 -- \
  psql "postgresql://rag@rag-postgres-rw:5432/backstage_rag" -c "SELECT '[1,2,3]'::vector;"

kubectl -n portal get svc | grep rag-postgres           # rw / ro / r
```

## Common failure points

- **`ErrImagePull`** on `rag-postgres-1` → Step 1a not done, or image is private
  (add an imagePullSecret).
- **ExternalSecret `SecretSyncedError`** → wrong store name (`vault-cluster`?),
  wrong KV path/mount, or Vault policy missing.
  `kubectl -n portal describe externalsecret rag-postgres-creds`.
- **Cluster stuck `Setting up primary`** → `kubectl -n portal logs rag-postgres-1`;
  usually the owner secret keys aren't `username`/`password`.
- **Backup errors** → bucket missing or wrong `INGRESS_DOMAIN`/endpoint:
  `kubectl -n portal get cluster rag-postgres -o jsonpath='{.status.conditions}'`.

## Teardown

```bash
kubectl -n flux-system delete kustomization backstage-rag-postgres cnpg-operator
kubectl -n flux-system delete gitrepository flux-rag-test
# CNPG Cluster + PVCs are pruned by Flux; double-check:
kubectl -n portal get cluster,pvc -l cnpg.io/cluster=rag-postgres
```
