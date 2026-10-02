# notification-catcher

Reads homerun2 streams and posts what its routing file selects to Teams (and
other webhooks). A pure consumer: no Service, no route.

## Two ways to run it

| | Credentials | Routing file | Used by |
|---|---|---|---|
| `profiles/base` (+ `sops/`) | `HOMERUN2_REDIS_PASSWORD_B64` and `TEAMS_WEBHOOK_URL` from the consumer's `substituteFrom` Secret | supplied by the cluster (`homerun2-notification-catcher-notify`) | platform-sthings: git PRs and Grafana alerts, streams `messages,alerts` |
| bundle component `homerun2-notification-catcher` (+ `eso/`) | `redis-password` and `teams-webhook-url` in `${HOMERUN2_SECRET_PATH}`, through the ClusterSecretStore | a `notify-*` component, `tabletennis-results` by default | table tennis results, stream `tabletennis` (#431) |

## Table tennis results (bundle default)

Where it goes: the Teams channel behind `teams-webhook-url`. What goes there:
**a won match, never a point.** The one output matches `system: tabletennis`
and the tag `transition=match_won`, which zaehlwerk v0.3.0+ sets on the
winning transition. The card title is the panel's form, e.g. `WIN 2:0`.

Turning it on, in order:

1. Write `teams-webhook-url` (a Power Automate "post to channel" URL) into the
   cluster's `${HOMERUN2_SECRET_PATH}` entry. Without it the ExternalSecret
   fails and the catcher cannot start, not even in dry run.
2. Select `../components/homerun2-notification-catcher`. It starts in **dry
   run**: one real match must show exactly one line
   `dry-run: would send … teams-tabletennis-results` in
   `kubectl -n homerun2 logs deploy/homerun2-notification-catcher`.
3. Set `HOMERUN2_NOTIFICATION_CATCHER_DRY_RUN: off`. The next match posts one
   card.

Turning it off: `HOMERUN2_NOTIFICATION_CATCHER_DRY_RUN: on` stops the posting
and keeps the catcher running; removing the component line removes it.

A new instance does not post old results: from v3.0.2 a new consumer group
starts at `$`, only messages pitched after it exists (upstream #43). A restart
keeps its position.

## Cluster builds too (`tabletennis-results-and-cluster-builds`)

The same results output, unchanged, plus `teams-cluster-build-watch`: every
checkpoint cluster-build-watch's homerun sink pitches (`match: {system:
cluster-build-watch}`, no severity floor) on the same webhook. The sink pitches
onto homerun2's default stream, so the catcher reads both:

```yaml
HOMERUN2_NOTIFICATION_CATCHER_ROUTING: tabletennis-results-and-cluster-builds
HOMERUN2_NOTIFICATION_CATCHER_STREAMS: tabletennis,messages
```

Dry run applies to both outputs alike (stuttgart-things/dapr-workflows#49).

## Config changes roll the pod -- where Reloader runs

The catcher reads `REDIS_STREAMS` (`-env`), the routing file (`-notify`) and
its Secrets once, at start. Flux updates them in place, which by itself does
not restart anything: on labda-dev-a the pod ran an hour on the old routing
after stuttgart-things#3379 (dapr-workflows#49). The Deployment therefore
carries `reloader.stakater.com/auto: "true"`; Reloader rolls it whenever any
of those objects changes.

**Requires Reloader** (`infra/reloader`, bundle component
`infra/platform/components/reloader`) -- without it the annotation is inert.
Check with `kubectl get deploy -n reloader`.

A hash in the pod template (configMapGenerator, or a substituted checksum) was
not an option: the `-env` ConfigMap comes from the OCI base and is patched
inside the child Kustomization at apply time, `-notify` from a `notify-*`
component in the parent build -- or from the cluster repo (platform-sthings) --
so no single kustomize build sees all of them.

## Why the webhook is written `$${TEAMS_WEBHOOK_URL}`

The routing ConfigMap is applied by a Flux Kustomization with `postBuild`,
which would substitute `${TEAMS_WEBHOOK_URL}` itself, baking the URL (or
nothing) into a ConfigMap. `$$` is Flux's escape: the catcher receives the
literal placeholder and fills it from its own environment at start.
