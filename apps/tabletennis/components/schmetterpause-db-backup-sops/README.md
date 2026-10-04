# schmetterpause-db-backup-sops

The same as [`schmetterpause-db-backup`](../schmetterpause-db-backup) --
continuous WAL archiving and a daily base backup for `schmetterpause-db`,
through the [Barman Cloud plugin](../../../cnpg-barman-cloud) -- for clusters
without ExternalSecrets. The credentials are the caller's: a Secret
`schmetterpause-db-backup` in the namespace, typically SOPS-encrypted in the
cluster repo.

| Object | Purpose |
|---|---|
| `ObjectStore/schmetterpause-db` | `s3://${SCHMETTERPAUSE_BACKUP_BUCKET}/` at `${SCHMETTERPAUSE_BACKUP_S3_ENDPOINT}`, gzip, retention `${SCHMETTERPAUSE_BACKUP_RETENTION}` (`7d`) |
| `ScheduledBackup/schmetterpause-db-daily` | a base backup at `${SCHMETTERPAUSE_BACKUP_SCHEDULE}` (`0 0 3 * * *`, seconds first), one immediately |
| patch on `Cluster/schmetterpause-db` | `spec.plugins`: archive WAL into that ObjectStore under `${SCHMETTERPAUSE_BACKUP_SERVER_NAME}` |

The Secret needs `ACCESS_KEY_ID`, `ACCESS_SECRET_KEY` and `trust-bundle.pem`
(the CA of the S3 endpoint).

To have this build render that Secret from substitution variables instead of
shipping it, select [`schmetterpause-db-backup-subst`](../schmetterpause-db-backup-subst)
in place of this component. It includes this component.

## `SCHMETTERPAUSE_BACKUP_SERVER_NAME`

The directory under the bucket; defaults to `schmetterpause-db`. The ESO
variant has no such variable and always archives under the Cluster's name.
Set it when another Cluster's archive shares the bucket -- above all after
[`schmetterpause-db-recovery`](../schmetterpause-db-recovery) from that
bucket: the plugin refuses to archive into a non-empty path, and the Cluster
fails.

## Checking it works

```bash
kubectl -n schmetterpause get cluster schmetterpause-db \
  -o jsonpath='{.status.conditions[?(@.type=="ContinuousArchiving")]}'
kubectl -n schmetterpause get backups.postgresql.cnpg.io
```
