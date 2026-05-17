# velero

HashiCorp Velero install for cluster and PV backup/restore, wired for S3-compatible storage (default: MinIO).

Required by parent issue [#111](https://github.com/stuttgart-things/flux/issues/111) (sharded Crossplane control planes) and child issue [#115](https://github.com/stuttgart-things/flux/issues/115) (restore-hook gating for provider readiness).

## Credential modes

Two mutually-exclusive ways to populate the `cloud-credentials` Secret consumed by the Velero HelmRelease:

### 1. Substitution (default)

The base `pre-release.yaml` is a plain `Secret` manifest populated from Flux `postBuild.substitute` values (`VELERO_S3_ACCESS_KEY`, `VELERO_S3_SECRET_KEY`). Pair with SOPS for the actual credential values:

```yaml
postBuild:
  substituteFrom:
    - kind: Secret
      name: velero-s3-credentials   # SOPS-encrypted in the consumer overlay
```

### 2. External Secrets Operator (opt-in)

Use the kustomize Component at `components/external-secret/` to pull credentials from Vault via ESO instead. Enable it in your consumer Flux `Kustomization` overlay and patch out the base `cloud-credentials` Secret so the two don't fight over it:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
spec:
  path: ./infra/velero
  components:
    - ./components/external-secret
  patches:
    - target:
        kind: Secret
        name: cloud-credentials
      patch: |
        $patch: delete
        apiVersion: v1
        kind: Secret
        metadata:
          name: cloud-credentials
          namespace: velero
```

Requires External Secrets Operator and a `ClusterSecretStore` already installed in the cluster.

## Trust bundle for self-signed S3 endpoints

If your MinIO/S3 endpoint is served with a certificate signed by a private CA (e.g. Vault PKI), enable the `components/trust-bundle/` kustomize Component. It mounts a trust-manager-published ConfigMap (default: `cluster-trust-bundle`, key `trust-bundle.pem`) into the velero pod and sets `AWS_CA_BUNDLE` so the AWS Go SDK verifies the endpoint against it.

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
spec:
  path: ./infra/velero
  components:
    - ./components/trust-bundle
  postBuild:
    substitute:
      VELERO_TRUST_BUNDLE_CONFIGMAP: cluster-trust-bundle
      VELERO_TRUST_BUNDLE_KEY: trust-bundle.pem
```

The ConfigMap volume is mounted with `optional: true` so the velero pod can start even if trust-manager hasn't yet replicated the ConfigMap into the namespace.

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
| `VELERO_ESO_SECRET_STORE_NAME` | `vault-cluster` | ClusterSecretStore name (mode 2 only) |
| `VELERO_ESO_SECRET_STORE_KIND` | `ClusterSecretStore` | Secret store kind (mode 2 only) |
| `VELERO_ESO_SECRET_PATH` | `kv/data/velero/s3` | Vault KV path holding the S3 credentials (mode 2 only) |
| `VELERO_ESO_ACCESS_KEY_PROPERTY` | `access_key` | KV property for access key (mode 2 only) |
| `VELERO_ESO_SECRET_KEY_PROPERTY` | `secret_key` | KV property for secret key (mode 2 only) |
| `VELERO_ESO_REFRESH_INTERVAL` | `1h` | ESO refresh interval (mode 2 only) |
| `VELERO_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | trust-manager ConfigMap to mount (trust-bundle Component only) |
| `VELERO_TRUST_BUNDLE_KEY` | `trust-bundle.pem` | Key inside the ConfigMap (trust-bundle Component only) |
| `VELERO_TRUST_BUNDLE_MOUNT_PATH` | `/etc/ssl/custom` | Mount path inside the velero pod (trust-bundle Component only) |
