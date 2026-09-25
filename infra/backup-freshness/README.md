# backup-freshness — the watcher in the other lab

Asks one question, hourly, from LabUL:

> Is there anything younger than `MAX_AGE` in the **destination** bucket of the
> cross-lab backup?

## Why a second probe

The first one runs on `machinery` in LabDA (stuttgart-things#3193) and checks
both ends of the chain. It cannot report its own death: if machinery stops,
nothing runs and nothing is said — and silence is exactly what a broken backup
looks like. That was the last open item in stuttgart-things#3039.

This closes it **without a heartbeat and without an inbound endpoint**. If
machinery is down, nothing new reaches the destination bucket, and this probe
sees that without ever having heard of machinery.

## Why not a Pushgateway

That was the first design, and it is wrong. A Pushgateway has no
authentication. Published through the gateway it is writable by anyone on the
network, and the damaging write is not junk — it is a **forged fresh
heartbeat**, which silently switches the dead-man's switch off. A watchdog that
can be put to sleep from outside is worse than none, because it is trusted.

Reading a bucket needs no inbound endpoint at all.

## What it still does not cover

**This cluster dying.** It is also the one carrying alerts to Teams, so its
death is silent too — one level up. Only something outside both labs closes
that, which is a dependency decision rather than a piece of code.

## Configuration

| substitution | default | |
|---|---|---|
| `BACKUP_FRESHNESS_DEST_BUCKET` | — | **required**, the bucket the copy writes into |
| `BACKUP_FRESHNESS_DEST_ENDPOINT` | — | **required**, that bucket's MinIO |
| `BACKUP_FRESHNESS_MAX_AGE` | `26h` | the daily `ScheduledBackup` is the slowest guaranteed producer; tighter cries wolf on a quiet Sunday |
| `BACKUP_FRESHNESS_SCHEDULE` | `37 * * * *` | off the hour, so it does not collide with everything else |
| `BACKUP_FRESHNESS_NAMESPACE` | `homerun2` | where the pitcher's token and the trust bundle already are |
| `BACKUP_FRESHNESS_SECRET` | `minio-replication-labda-target` | needs only `ListBucket` on the destination |
| `BACKUP_FRESHNESS_TOKEN_SECRET` | `homerun2-omni-pitcher-token` | the pitcher's `auth-token` |
| `BACKUP_FRESHNESS_WEBHOOK_URL` | in-cluster Service | the same path this cluster's Alertmanager uses |
| `BACKUP_FRESHNESS_IMAGE` | pinned by digest | the same image the machinery probe runs |

## Exit codes

Deliberate, so retries deliver alerts instead of re-raising them:

| result | exit | |
|---|---|---|
| fresh | 0 | |
| stale, alert delivered | 0 | the probe did its job; non-zero would re-send the same alert three times |
| stale, delivery failed | 1 | the retry is a genuine retry of delivery |
| could not list | 1 | a credential or network fault is **not** "no backups" and must not be pitched as one |
