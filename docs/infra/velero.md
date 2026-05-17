# Velero

HashiCorp Velero install for cluster and persistent volume backup/restore, pre-wired for S3-compatible storage (default: MinIO).

Anchors the work in [#111](https://github.com/stuttgart-things/flux/issues/111) (sharded Crossplane control planes) and [#115](https://github.com/stuttgart-things/flux/issues/115) (restore hooks for provider readiness).

## Prerequisites

- An S3-compatible bucket (MinIO, AWS S3, etc.) and credentials for it
- For **ESO credential mode**: External Secrets Operator installed and a `ClusterSecretStore` (e.g. wired to Vault `sthings.lab`)

## Credential modes

The base layer creates the `cloud-credentials` Secret via the `sthings-cluster` helper chart using substitution variables. To use ESO instead, enable the `components/external-secret/` kustomize Component and patch out the helper-chart HelmRelease — see the [README](https://github.com/stuttgart-things/flux/blob/main/infra/velero/README.md#2-external-secrets-operator-opt-in) for the patch.

## Trust bundle for self-signed S3 endpoints

For MinIO/S3 endpoints served with a private-CA certificate (Vault PKI etc.), enable the `components/trust-bundle/` Component. It mounts a trust-manager Bundle ConfigMap into the velero pod and sets `AWS_CA_BUNDLE` so the AWS Go SDK verifies the endpoint against it. The volume mount uses `optional: true` so the pod starts even before trust-manager has replicated the ConfigMap.

## Deployment

### GitRepository

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    tag: <version>
  url: https://github.com/stuttgart-things/flux.git
```

### Kustomization (substitution mode)

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: velero
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/velero
  prune: true
  wait: true
  postBuild:
    substitute:
      VELERO_BUCKET: cluster-backups
      VELERO_S3_ENDPOINT: https://minio.sthings.lab
      VELERO_S3_REGION: minio
    substituteFrom:
      - kind: Secret
        name: velero-s3-credentials   # SOPS-encrypted, contains VELERO_S3_ACCESS_KEY / VELERO_S3_SECRET_KEY
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `VELERO_NAMESPACE` | `velero` | Target namespace |
| `VELERO_VERSION` | `9.0.0` | velero Helm chart version |
| `VELERO_PLUGIN_AWS_VERSION` | `v1.13.0` | velero-plugin-for-aws image tag |
| `VELERO_BUCKET` | *(required)* | S3 bucket name |
| `VELERO_S3_ENDPOINT` | *(required)* | S3 endpoint URL |
| `VELERO_S3_REGION` | `minio` | S3 region |
| `VELERO_S3_FORCE_PATH_STYLE` | `true` | Path-style URLs (MinIO requirement) |
| `VELERO_S3_INSECURE_SKIP_TLS_VERIFY` | `false` | Skip TLS verify on S3 endpoint |
| `VELERO_CREDENTIALS_SECRET_NAME` | `cloud-credentials` | Secret consumed by Velero |
| `VELERO_S3_ACCESS_KEY` | *(required, substitution mode)* | MinIO access key |
| `VELERO_S3_SECRET_KEY` | *(required, substitution mode)* | MinIO secret key |
| `VELERO_SNAPSHOTS_ENABLED` | `false` | Enable volume snapshots |
| `VELERO_DEPLOY_NODE_AGENT` | `false` | Deploy node-agent for filesystem backup |
| `VELERO_METRICS_ENABLED` | `true` | Expose Prometheus metrics |
| `VELERO_SERVICE_MONITOR_ENABLED` | `false` | Create a Prometheus ServiceMonitor |
| `VELERO_ESO_SECRET_STORE_NAME` | `vault-cluster` | ClusterSecretStore name (ESO mode) |
| `VELERO_ESO_SECRET_PATH` | `kv/data/velero/s3` | Vault KV path (ESO mode) |

See [README](https://github.com/stuttgart-things/flux/blob/main/infra/velero/README.md) for the full list, including all ESO mode variables.

## Notes

- The Velero CRDs are installed by the chart; `cleanUpCRDs: false` keeps them in place across uninstalls so that scheduled-backup metadata survives.
- `velero-plugin-for-aws` is used for all S3-compatible providers including MinIO — there is no separate MinIO plugin.
- Scheduled backups are not defined in this base; create `Schedule` resources separately or extend the HelmRelease `values.schedules`.
