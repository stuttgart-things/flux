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

A bundle cluster selects **`infra/platform/components/velero-eso`** instead of `velero`. It is the same child Kustomization `velero` (so `velero-schedule` works with either), wired as below; set `VELERO_ESO_SECRET_STORE_NAME` to the cluster's store. The entry it reads is `<store mount>/velero` with properties `access_key` and `secret_key` -- the store carries the mount and KV version, so `VELERO_ESO_SECRET_PATH` is the entry name, not a path.

Outside the bundle, use the kustomize Component at `components/external-secret/` in your own Flux `Kustomization` and patch out the base `cloud-credentials` Secret so the two don't fight over it:

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

## ServiceMonitor (Prometheus scraping)

Setting `VELERO_SERVICE_MONITOR_ENABLED=true` makes the chart render a `monitoring.coreos.com/v1` `ServiceMonitor` resource. That CRD is **not** part of the standalone `prometheus` Helm chart — it ships with [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) or a standalone install of the [prometheus-operator](https://github.com/prometheus-operator/prometheus-operator).

If the CRD is missing the Helm install will fail with:

```
no matches for kind "ServiceMonitor" in version "monitoring.coreos.com/v1"
```

Workarounds:

- **Have prometheus-operator** → set `VELERO_SERVICE_MONITOR_ENABLED=true` (default uses label `release: prometheus` for Prometheus discovery; override via the chart's `metrics.serviceMonitor.additionalLabels` if your operator selects differently).
- **No operator, just want metrics** → leave `VELERO_SERVICE_MONITOR_ENABLED=false` (default). The `/metrics` endpoint is still exposed on the velero Service (port `8085`); scrape it with a static `prometheus.yml` job or a `kubernetes_sd_configs` scrape rule.

## Recurring backups

A `Schedule` lives in `./infra/velero/schedule`, selected as its own bundle component (`infra/platform/components/velero-schedule`), **not** as part of this path.

That separation is not tidiness. A `Schedule` is a `velero.io` CR whose CRD the HelmRelease here creates. Shipped in one Kustomization with that install, Flux applies **nothing** and never converges — the whole apply is rejected on a fresh cluster, not just the Schedule. The component `dependsOn: velero`, which is the only ordering that survives a bootstrap.

| Variable | Default | Description |
|---|---|---|
| `VELERO_SCHEDULE_NAME` | `daily-all` | Schedule name, and the `velero-schedule` label on the backups it takes |
| `VELERO_SCHEDULE_CRON` | `0 2 * * *` | Cron expression (cluster time, UTC on these nodes) |
| `VELERO_SCHEDULE_TTL` | `720h0m0s` | How long each backup is retained |
| `VELERO_SCHEDULE_STORAGE_LOCATION` | `default` | BackupStorageLocation to write to |
| `VELERO_SCHEDULE_PAUSED` | `false` | Not threaded — bool, see below |

Backups are **metadata only**, matching the base's `snapshotsEnabled` / `deployNodeAgent` defaults. Turning `snapshotVolumes` on without one of those produces backups that silently contain no volume data.

`VELERO_SCHEDULE_PAUSED` and the namespace lists are not threaded through `postBuild.substitute`: the first is a bool (which `map[string]string` rejects, failing the parent and every sibling), the second is a YAML sequence and substitution is textual. Patch the child from the consumer with a literal value instead — the component file carries the exact patch.

Sizing, measured on a small single-node RKE2 cluster (54 pods, Rancher + Flux + kube-prometheus-stack): **1060 items, 21 MiB** per full-cluster metadata run. Thirty days of dailies is well under a gigabyte.

## Required variables

| Variable | Default | Description |
|---|---|---|
| `VELERO_NAMESPACE` | `velero` | Target namespace |
| `VELERO_VERSION` | `12.1.0` | velero Helm chart version. **Minimum 10.0.0** — the base writes `configuration.extraEnvVars` in the list form the chart requires from 10.x on; pinning back to 9.x fails the install on the chart schema. |
| `VELERO_PLUGIN_AWS_VERSION` | `v1.14.2` | velero-plugin-for-aws image tag |
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
| `VELERO_ESO_SECRET_PATH` | `velero` | KV entry name holding the S3 credentials; the store supplies mount and version (mode 2 only) |
| `VELERO_ESO_ACCESS_KEY_PROPERTY` | `access_key` | KV property for access key (mode 2 only) |
| `VELERO_ESO_SECRET_KEY_PROPERTY` | `secret_key` | KV property for secret key (mode 2 only) |
| `VELERO_ESO_REFRESH_INTERVAL` | `1h` | ESO refresh interval (mode 2 only) |
| `VELERO_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | trust-manager ConfigMap mounted into the velero pod (always mounted, `optional: true`) |
| `VELERO_TRUST_BUNDLE_MOUNT_PATH` | `/etc/ssl/custom` | Mount path for the trust-bundle ConfigMap |
| `VELERO_SSL_CERT_DIR` | *(empty)* | When set, points Go's `crypto/x509` at the trust-bundle mount; empty falls back to system CAs |
