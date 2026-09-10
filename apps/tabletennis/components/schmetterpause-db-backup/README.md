# schmetterpause-db-backup

Continuous WAL archiving and a daily base backup for `schmetterpause-db`, through
the [Barman Cloud plugin](../../../cnpg-barman-cloud). Selected by the
`tabletennis-backup` bundle component in place of `tabletennis`.

| Object | Purpose |
|---|---|
| `ExternalSecret/schmetterpause-db-backup` | S3 pair from `${SCHMETTERPAUSE_BACKUP_SECRET_PATH}`, plus the CA bundle copied from the `cluster-trust-bundle` ConfigMap |
| `ObjectStore/schmetterpause-db` | `s3://${SCHMETTERPAUSE_BACKUP_BUCKET}/`, gzip for WAL and data, retention `${SCHMETTERPAUSE_BACKUP_RETENTION}` |
| `ScheduledBackup/schmetterpause-db-daily` | a base backup at `${SCHMETTERPAUSE_BACKUP_SCHEDULE}` (six fields, seconds first), one immediately |
| patch on `Cluster/schmetterpause-db` | `spec.plugins`: archive WAL through the plugin into that ObjectStore |

## Checking it works

```bash
kubectl -n schmetterpause get cluster schmetterpause-db \
  -o jsonpath='{.status.conditions[?(@.type=="ContinuousArchiving")]}'
kubectl -n schmetterpause get backups.postgresql.cnpg.io
```

`ContinuousArchiving=True` and a backup in phase `completed` are the two facts
that matter. A Kustomization reporting Ready says neither.

## Recovery

Recovery is a NEW Cluster bootstrapped from the object store -- never an
in-place overwrite. The new Cluster needs, in its own namespace, an
`ObjectStore` pointing at the same bucket and the Secret it references; the
simplest way is to restore into the same namespace under another name and
switch the application over once it is verified.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: schmetterpause-db-restore
  namespace: schmetterpause
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18
  storage:
    size: 1Gi
  bootstrap:
    recovery:
      source: origin
      # recoveryTarget:
      #   targetTime: "2026-09-10 13:50:40+00"   # point in time; omit for the latest WAL
  externalClusters:
    - name: origin
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: schmetterpause-db
          serverName: schmetterpause-db
```

Do not give the recovered Cluster the same `plugins` WAL archiver pointing at
the same `serverName`: two clusters archiving into one path corrupt each
other's timeline. Archive the recovered one under a new `serverName`, or not at
all until it replaces the original.
