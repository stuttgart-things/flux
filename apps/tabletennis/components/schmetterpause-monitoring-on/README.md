# schmetterpause-monitoring

PodMonitors and alert rules for schmetterpause and its database. Ported from
`stuttgart-things/argocd` `apps/schmetterpause/monitoring`, which had no
counterpart here — the one place where the two platforms were not at parity, and
in that direction.

Three variants, selected by `TABLETENNIS_SCHMETTERPAUSE_MONITORING`:

| Value | Ships |
|---|---|
| `off` *(default)* | nothing |
| `on` | both PodMonitors + the app and database alerts |
| `backup` | everything `on` ships, plus the WAL-archiving and base-backup alerts |

`backup` is a Component that includes `on` rather than repeating it, so the two
cannot drift.

| Object | Variant | Purpose |
|---|---|---|
| `PodMonitor/schmetterpause` | on | the app's `/metrics` on container port `metrics` |
| `PodMonitor/schmetterpause-db` | on | the CloudNativePG instances on port `metrics` (9187) |
| `PrometheusRule/schmetterpause` | on | `SchmetterpauseMetricsDown`, `SchmetterpauseDatabaseExporterDown` |
| `PrometheusRule/schmetterpause-backup` | backup | `SchmetterpauseWALArchivingFailing`, `SchmetterpauseWALArchiveBacklog`, `SchmetterpauseBackupTooOld`, `SchmetterpauseBackupFailed` |

## Requirements

- **The Prometheus Operator CRDs** (`infra/kube-prometheus-stack`). Without them
  the dry-run rejects the **whole** tabletennis Kustomization, not just these
  objects — which is why this is a variant and not part of the base.
- **schmetterpause v0.8.0 or later** for the app monitor to find anything: that
  release added the container port `metrics` (`SP_METRICS_ADDR`). Against an
  older one the monitor selects the pods, scrapes nothing, and
  `SchmetterpauseMetricsDown` fires.
- For `backup`, the `tabletennis-backup` bundle component — those rules watch
  what [`schmetterpause-db-backup`](../schmetterpause-db-backup/) sets up.

## Why `backup` is a variant rather than always shipped

`barman_cloud_cloudnative_pg_io_last_available_backup_timestamp` is published by
the Barman Cloud **plugin**, and is absent entirely on a Cluster with no
ObjectStore. An expression over an absent series returns no result, so
`SchmetterpauseBackupTooOld` would never fire — and a rule that cannot fire is
worse than no rule, because the dashboard shows it as green.

The cnpg exporter's own `cnpg_collector_last_available_backup_timestamp` is not
usable instead: it stays `0` for plugin backups.

## Two things worth knowing about the expressions

**`SchmetterpauseWALArchivingFailing` compares timestamps, not age.** With nobody
writing, no WAL segment fills and "seconds since the last archival" grows all
night while everything is fine. A failure *newer* than the last success is the
signal.

**The backup age arrives as a product, `26 * 3600`.** `postBuild.substitute`
takes strings only, and a bare `26` or `93600` resolves to an int — which fails
every substitution in the block, not just that one (`hack/check-substitute-strings.py`
catches it). PromQL evaluates the product, and comparison binds looser than `*`,
so the expression reads `(time() - ts) > (26 * 3600)`. Same reason
`SCHMETTERPAUSE_DB_IMAGE` carries the whole image rather than the major version.

## Discovery does not depend on the labels

`infra/kube-prometheus-stack` sets `podMonitorSelectorNilUsesHelmValues: false`
and the same for rules, which leaves the Prometheus with an empty selector — and
an empty selector matches every PodMonitor and PrometheusRule in every namespace.
The `app.kubernetes.io/component: monitoring` labels are carried anyway, so these
objects still resolve on a cluster whose Prometheus narrows that selector, the way
[`infra/prometheus-pve-exporter`](../../../../infra/prometheus-pve-exporter/)'s
monitor does.

## Checking it works

```bash
kubectl -n schmetterpause get podmonitors,prometheusrules
# targets should be UP, two of them plus one per database instance
kubectl -n monitoring exec sts/prometheus-kube-prometheus-stack-prometheus -c prometheus -- \
  wget -qO- localhost:9090/api/v1/targets | grep -o 'schmetterpause[^"]*'
```

## Variables

| Variable | Default |
|---|---|
| `TABLETENNIS_SCHMETTERPAUSE_MONITORING` | `off` |
| `TABLETENNIS_SCHMETTERPAUSE_MONITORING_INTERVAL` | `60s` |
| `TABLETENNIS_SCHMETTERPAUSE_BACKUP_MAX_AGE_SECONDS` | `26 * 3600` — the ScheduledBackup is daily; 26 h leaves room for one slow run |
