# velero

HashiCorp Velero install for cluster and PV backup/restore, wired for S3-compatible storage (default: MinIO).

Required by parent issue [#111](https://github.com/stuttgart-things/flux/issues/111) (sharded Crossplane control planes) and child issue [#115](https://github.com/stuttgart-things/flux/issues/115) (restore-hook gating for provider readiness).

## Credential modes

Two mutually-exclusive ways to populate the `cloud-credentials` Secret consumed by the Velero HelmRelease:

### 1. Substitution (default)

The base `pre-release.yaml` uses the `sthings-cluster` helper chart to create the Secret from Flux `postBuild.substitute` values (`VELERO_S3_ACCESS_KEY`, `VELERO_S3_SECRET_KEY`). Pair with SOPS for the actual credential values:

```yaml
postBuild:
  substituteFrom:
    - kind: Secret
      name: velero-s3-credentials   # SOPS-encrypted in the consumer overlay
```

### 2. External Secrets Operator (opt-in)

Use the kustomize Component at `components/external-secret/` to pull credentials from Vault via ESO instead. Enable it in your consumer Flux `Kustomization` overlay and patch out the `pre-release.yaml` resource so the two don't fight over `cloud-credentials`:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
spec:
  path: ./infra/velero
  components:
    - ./components/external-secret
  patches:
    - target:
        kind: HelmRelease
        name: velero-credentials
      patch: |
        $patch: delete
        apiVersion: helm.toolkit.fluxcd.io/v2
        kind: HelmRelease
        metadata:
          name: velero-credentials
          namespace: velero
```

Requires External Secrets Operator and a `ClusterSecretStore` already installed in the cluster.

## Required variables

| Variable | Default | Description |
|---|---|---|
| `VELERO_NAMESPACE` | `velero` | Target namespace |
| `VELERO_VERSION` | `9.0.0` | velero Helm chart version |
| `VELERO_PLUGIN_AWS_VERSION` | `v1.13.0` | velero-plugin-for-aws image tag |
| `VELERO_BUCKET` | *(required)* | S3 bucket name |
| `VELERO_S3_ENDPOINT` | *(required)* | S3 endpoint URL (MinIO URL for self-hosted) |
| `VELERO_S3_REGION` | `minio` | S3 region (MinIO accepts any string) |
| `VELERO_S3_FORCE_PATH_STYLE` | `true` | Path-style URLs (required for MinIO) |
| `VELERO_S3_INSECURE_SKIP_TLS_VERIFY` | `false` | Skip TLS verify on S3 endpoint |
| `VELERO_CREDENTIALS_SECRET_NAME` | `cloud-credentials` | Secret consumed by Velero |
| `VELERO_S3_ACCESS_KEY` | *(required in mode 1)* | MinIO access key |
| `VELERO_S3_SECRET_KEY` | *(required in mode 1)* | MinIO secret key |
| `VELERO_SNAPSHOTS_ENABLED` | `false` | Enable volume snapshots |
| `VELERO_DEPLOY_NODE_AGENT` | `false` | Deploy node-agent for filesystem backup (Kopia/Restic) |
| `VELERO_METRICS_ENABLED` | `true` | Expose Prometheus metrics |
| `VELERO_SERVICE_MONITOR_ENABLED` | `false` | Create a Prometheus ServiceMonitor |
| `STHINGS_CLUSTER_VERSION` | `0.3.20` | sthings-cluster helper chart version (mode 1 only) |
| `VELERO_ESO_SECRET_STORE_NAME` | `vault-cluster` | ClusterSecretStore name (mode 2 only) |
| `VELERO_ESO_SECRET_STORE_KIND` | `ClusterSecretStore` | Secret store kind (mode 2 only) |
| `VELERO_ESO_SECRET_PATH` | `kv/data/velero/s3` | Vault KV path holding the S3 credentials (mode 2 only) |
| `VELERO_ESO_ACCESS_KEY_PROPERTY` | `access_key` | KV property for access key (mode 2 only) |
| `VELERO_ESO_SECRET_KEY_PROPERTY` | `secret_key` | KV property for secret key (mode 2 only) |
| `VELERO_ESO_REFRESH_INTERVAL` | `1h` | ESO refresh interval (mode 2 only) |
