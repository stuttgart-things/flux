# schmetterpause-db-recovery

Bootstraps `schmetterpause-db` from a Barman Cloud archive -- the base backups
and WAL another schmetterpause wrote -- instead of an empty `initdb`. Through
the [Barman Cloud plugin](../../../cnpg-barman-cloud), which must be installed.

Works beside `schmetterpause/sops` and `schmetterpause/eso` alike: it creates
no credentials, it reads the Secret named by `SCHMETTERPAUSE_RECOVERY_SECRET`.

| Object | Purpose |
|---|---|
| `ObjectStore/schmetterpause-db-origin` | `s3://${SCHMETTERPAUSE_RECOVERY_BUCKET}/` at `${SCHMETTERPAUSE_RECOVERY_S3_ENDPOINT}`; no retention, nothing archives into it |
| patch on `Cluster/schmetterpause-db` | `bootstrap.recovery` from `externalClusters/origin` (`serverName: ${SCHMETTERPAUSE_RECOVERY_SERVER_NAME}`); database, owner and `secret` stay those the DSN names |

## Variables

| Variable | Default | |
|---|---|---|
| `SCHMETTERPAUSE_RECOVERY_BUCKET` | *(required)* | bucket holding `<serverName>/base/` and `<serverName>/wals/` |
| `SCHMETTERPAUSE_RECOVERY_S3_ENDPOINT` | *(required)* | e.g. `https://artifacts.platform.sthings.lab` |
| `SCHMETTERPAUSE_RECOVERY_SERVER_NAME` | `schmetterpause-db` | the directory under the bucket: the source Cluster's name, or the `serverName` it archived under |
| `SCHMETTERPAUSE_RECOVERY_SECRET` | `schmetterpause-db-backup` | Secret with `ACCESS_KEY_ID`, `ACCESS_SECRET_KEY`, `trust-bundle.pem` |

## It only acts when the Cluster is created

CloudNativePG reads `bootstrap` once. Selecting this component on a running
Cluster changes nothing; the webhook allows the edit and the operator ignores
it. The recovery happens when the Cluster is deleted and Flux applies it
again, and deleting the Cluster deletes its PVC. On a cluster whose database
holds nothing yet:

```bash
kubectl -n schmetterpause delete cluster schmetterpause-db    # takes the PVC with it
flux reconcile kustomization <the one applying profiles/…> -n flux-system
kubectl -n schmetterpause get cluster schmetterpause-db -w    # "Cluster in healthy state"
kubectl -n schmetterpause rollout restart deploy/schmetterpause
```

No suspend: the Kustomization that applies the profile also applies the
application's child Kustomization with `suspend: false`, so suspending the
child would not survive the reconcile that re-creates the Cluster. The
application just loses its database for the minute or two the recovery takes
and errors meanwhile; the restart afterwards runs its `migrate up` init
container against the recovered schema.

The application must be at least as new as the schema in the archive: its
`migrate up` init container moves forward, never back.

**Check before trusting it** -- a Ready Kustomization says nothing about the
data:

```bash
kubectl -n schmetterpause exec schmetterpause-db-1 -- psql -d schmetterpause -Atc \
  "select (select count(*) from players), (select count(*) from matches), (select max(version_id) from goose_db_version)"
```

The owner's password is set from `schmetterpause-db` after recovery (`secret`),
so the application logs in with this cluster's password, not the source's.

## Do not archive into the source path

A recovered Cluster that archives WAL under the same bucket and `serverName`
as its source is refused by the plugin ("Expected empty archive") and fails.
Pair this with [`schmetterpause-db-backup-sops`](../schmetterpause-db-backup-sops)
only with a different `SCHMETTERPAUSE_BACKUP_SERVER_NAME`.

Removing the component after the recovery is inert too, and keeps a later
re-creation of the Cluster from silently recovering an old archive again.
