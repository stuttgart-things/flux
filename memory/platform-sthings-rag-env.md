---
name: platform-sthings-rag-env
description: platform-sthings cluster specifics for testing backstage-rag-postgres (ESO store, domain, image visibility)
metadata:
  type: project
---

Testing `apps/backstage-rag-postgres` on the `platform-sthings` cluster
(KUBECONFIG=/home/sthings/.kube/platform-sthings) needs these env-specific values,
which differ from the app's defaults:

- **ESO ClusterSecretStore**: `vault-homerun2-cd` (the only one; default `vault-cluster` does NOT exist). Vault KV v2 mount is `homerun2-cd`, server `https://vault.infra.sthings-vsphere.labul.sva.de`. So `RAG_ESO_CREDS_PATH` must be `portal/rag-postgres` (relative to the mount), NOT `kv/data/portal/...`.
- **INGRESS_DOMAIN**: `platform.sthings-vsphere.labul.sva.de` (README/TESTING examples use `automation.sthings-vsphere...` which is wrong for this cluster). MinIO S3 endpoint resolves to `https://artifacts.platform.sthings-vsphere.labul.sva.de`.
- **pgvector operand image** `ghcr.io/stuttgart-things/postgresql-pgvector:16`: built+pushed 2026-06-04, GHCR package made **public** 2026-06-04 (anon pull OK) → `cluster.yaml` needs no imagePullSecret. Note: new GHCR packages default to private and the visibility flip is UI-only (no REST API).
- Present and working: Velero + BSL `default`, ESO operator, MinIO (ns `minio`), storageclass `nfs4-csi`.
- Flux only applies `${VAR:-default}` substitution when the Kustomization has a `postBuild` block — omitting it leaves literals unrendered.

DB-only smoke test (no ESO/backup) passed 2026-06-04; the `postInitSQL`→`postInitApplicationSQL` fix was merged in PR #156. See [[backstage-rag-postgres-eso-backup-todo]] for the remaining ESO/backup round.
