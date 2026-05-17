# velero

HashiCorp Velero install for cluster and PV backup/restore, wired for S3-compatible storage (default: MinIO).

Required by parent issue [#111](https://github.com/stuttgart-things/flux/issues/111) (sharded Crossplane control planes) and child issue [#115](https://github.com/stuttgart-things/flux/issues/115) (restore-hook gating for provider readiness).

## Provisioning a bucket-scoped S3 user

For self-hosted MinIO, create a dedicated user with access limited to the velero bucket rather than reusing MinIO root credentials. Two paths — pick one:

### Option A: MinIO Console

1. **Policies → Create Policy** — name `velero-<bucket>-rw` (e.g. `velero-test-rw`), paste:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "VeleroBucketLevel",
         "Effect": "Allow",
         "Action": [
           "s3:GetBucketLocation",
           "s3:ListBucket",
           "s3:ListBucketMultipartUploads"
         ],
         "Resource": ["arn:aws:s3:::<bucket>"]
       },
       {
         "Sid": "VeleroObjectLevel",
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject",
           "s3:AbortMultipartUpload",
           "s3:ListMultipartUploadParts"
         ],
         "Resource": ["arn:aws:s3:::<bucket>/*"]
       }
     ]
   }
   ```

2. **Users → Create User** — Access Key `velero` (or similar), generate a strong Secret Key.
3. Attach the `velero-<bucket>-rw` policy to the user.
4. Drop the Access/Secret Key into a SOPS-encrypted `Secret` keyed as `VELERO_S3_ACCESS_KEY` / `VELERO_S3_SECRET_KEY`, then reference it via `postBuild.substituteFrom` in the consumer Kustomization (see [Substitution](#1-substitution-default) below).

### Option B: Terraform (`aminueza/minio` provider)

```hcl
resource "minio_iam_policy" "velero" {
  name = "velero-test-rw"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "VeleroBucketLevel"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"]
        Resource = ["arn:aws:s3:::velero-test"]
      },
      {
        Sid      = "VeleroObjectLevel"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
        Resource = ["arn:aws:s3:::velero-test/*"]
      }
    ]
  })
}

resource "minio_iam_user"                  "velero" { name = "velero" }
resource "minio_iam_user_policy_attachment" "velero" {
  user_name   = minio_iam_user.velero.name
  policy_name = minio_iam_policy.velero.id
}
resource "minio_iam_service_account" "velero" { target_user = minio_iam_user.velero.name }

output "velero_access_key" { value = minio_iam_service_account.velero.access_key }
output "velero_secret_key" { value = minio_iam_service_account.velero.secret_key; sensitive = true }
```

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

The base mounts a trust-manager-published ConfigMap into the velero pod at `/etc/ssl/custom` with `optional: true`, so the mount is always present and harmless if no ConfigMap exists. To **activate** it (have Go's crypto/x509 use the bundle instead of the system CA store), set `VELERO_SSL_CERT_DIR` to the mount path:

```yaml
postBuild:
  substitute:
    VELERO_SSL_CERT_DIR: /etc/ssl/custom
    # Optional overrides if your bundle ConfigMap name/path differ from the defaults:
    # VELERO_TRUST_BUNDLE_CONFIGMAP: cluster-trust-bundle
    # VELERO_TRUST_BUNDLE_MOUNT_PATH: /etc/ssl/custom
```

When `VELERO_SSL_CERT_DIR` is unset (default empty), Go treats the env var as not-set and falls back to the system CA store. The pattern mirrors `apps/clusterbook-operator`.

> **Note:** `SSL_CERT_DIR` _replaces_ Go's default CA directory list — your trust-manager Bundle must include `useDefaultCAs: true` if you also need public CAs (e.g. for AWS S3 over the public internet).

## Required variables

| Variable | Default | Description |
|---|---|---|
| `VELERO_NAMESPACE` | `velero` | Target namespace |
| `VELERO_VERSION` | `9.0.0` | velero Helm chart version |
| `VELERO_PLUGIN_AWS_VERSION` | `v1.13.0` | velero-plugin-for-aws image tag |
| `VELERO_KUBECTL_IMAGE_REPOSITORY` | `docker.io/bitnamilegacy/kubectl` | kubectl image used by the chart's CRD-install hook (bitnami sunset their free namespace late 2025) |
| `VELERO_KUBECTL_IMAGE_TAG` | `1.33.4` | kubectl image tag for the CRD-install hook |
| `VELERO_BUCKET` | *(required)* | S3 bucket name |
| `VELERO_S3_ENDPOINT` | *(required)* | S3 endpoint URL (MinIO URL for self-hosted) |
| `VELERO_S3_REGION` | `minio` | S3 region (MinIO accepts any string) |
| `VELERO_S3_FORCE_PATH_STYLE` | `true` | Path-style URLs (required for MinIO) |
| `VELERO_S3_INSECURE_SKIP_TLS_VERIFY` | `false` | Skip TLS verify on S3 endpoint |
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
| `VELERO_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | trust-manager ConfigMap mounted into the velero pod (always mounted, `optional: true`) |
| `VELERO_TRUST_BUNDLE_MOUNT_PATH` | `/etc/ssl/custom` | Mount path for the trust-bundle ConfigMap |
| `VELERO_SSL_CERT_DIR` | *(empty)* | When set, points Go's `crypto/x509` at the trust-bundle mount; empty falls back to system CAs |
