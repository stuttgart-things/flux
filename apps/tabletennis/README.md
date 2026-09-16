# apps/tabletennis

Office table tennis: **schmetterpause** (matchmaking, league and tournaments,
with its CloudNativePG database) and **zaehlwerk** (live scorekeeping at the
table). Two services in two namespaces, one thing to operate — a cluster that
wants one almost always wants both, which is why `profiles/base` ships the pair.

Both are consumed as published kustomize bases over `OCIRepository`, patched
here for the cluster's gateway, hostnames and secret store. The counterpart in
the argocd catalog is `apps/tabletennis/install`; the two are meant to reach the
same end state, and the table at the bottom of that chart's README says where
the spellings differ.

## Selecting it

Through the `apps/platform` bundle, as either `tabletennis` or
`tabletennis-backup` — the same child Kustomization over the same path, so a
cluster switches between them without the apps being pruned and re-created.
Never both.

```yaml
  components:
    - ../components/tabletennis-backup
```

## Switches

Each is a pair (or triple) of components, selected by name through a variable.
They are components rather than values because **an empty
`postBuild.substitute` value cannot express "off"**: kustomize drops the quotes,
Flux replaces the unset variable with nothing, and the bare `key:` that remains
parses as YAML `null`, which the API server refuses — failing the whole apps
layer, not just the object. `hack/check-substitute-strings.py` is that failure
written down.

| Variable | Values | What `on` adds |
|---|---|---|
| `TABLETENNIS_ZAEHLWERK_PANEL` | `off`, `homerun2` | `OMNI_PITCHER_URL` + `CATCHER_URL` — scores to the LED panel |
| `TABLETENNIS_SCHMETTERPAUSE_MONITORING` | `off`, `on`, `backup` | PodMonitors and alert rules (`backup` adds the WAL/base-backup rules) |
| `TABLETENNIS_SCHMETTERPAUSE_ADMIN` | `off`, `on` | `SP_BOOTSTRAP_ADMIN` — the display name that gets the admin flag at every start |
| `TABLETENNIS_SCHMETTERPAUSE_SCOREBOARD` | `off`, `on` | `SP_SCOREBOARD_TOKEN` — schmetterpause's `/api/players` and `/api/results` |
| `TABLETENNIS_ZAEHLWERK_HANDOVER` | `off`, `on` | `SCHMETTERPAUSE_URL` + `SCHMETTERPAUSE_TOKEN` — a won match reported into schmetterpause |
| `TABLETENNIS_SCHMETTERPAUSE_POLICY` | `off`, `on` | Kyverno's check on the application image's CI signature |

### The scoreboard and the handover are one feature

`schmetterpause-scoreboard-on` opens the surface; `zaehlwerk-handover-on` is the
client for it. **Select both or neither.** Either alone fails quietly:

* handover without scoreboard — zaehlwerk posts to a route the application never
  registered. Every finished match comes back 404, the match still scores and
  shows, and only zaehlwerk's log says so.
* scoreboard without handover — an `/api` nothing calls.

They read one Vault entry (`TABLETENNIS_SCHMETTERPAUSE_SCOREBOARD_VAULT_PATH`,
default `schmetterpause-scoreboard`), so the token is rotated once and the two
sides cannot disagree. **That entry is its own**, not the application's:
`vault-base-setup` writes an entry with `data_json` and rewrites it whole, so
putting the token on `schmetterpause` would mean restating `session-key`,
`username` and `password` in the same JSON — and a wrong `session-key` signs
every player out at once.

**Write the Vault property before selecting either.** ESO fails a *whole*
ExternalSecret over one missing property, so the wrong order takes
`SP_SESSION_KEY` and the database URL down with it. Flux still reports Ready;
the check is

```
kubectl -n schmetterpause get externalsecret schmetterpause-app
```

### Versions

| | needs |
|---|---|
| the scoreboard | schmetterpause **v0.10.0+** — in v0.9.0 the handlers do not exist |
| the handover | zaehlwerk **v0.5.0+** — earlier tags do not mount the trust-manager bundle, so every call over the HTTPRoute fails on the cluster CA while the pod looks healthy |
| monitoring | schmetterpause **v0.8.0+** — the release that added the `metrics` container port |
| the policy | schmetterpause **v0.9.0+**, and a Kyverno serving `policies.kyverno.io/v1` |

## What a cluster has to provide

* a Gateway (`INFRA_GATEWAY_NAME` / `INFRA_GATEWAY_NAMESPACE`) and a resolvable
  `INFRA_DOMAIN`
* `TABLETENNIS_SECRET_STORE` — the cluster's `ClusterSecretStore`, holding the
  entries `schmetterpause` and `zaehlwerk`. There is no safe default: guessing
  points ESO at another cluster's secrets, which reads as "the Secret never
  appears", so the default is the sentinel `set-TABLETENNIS_SECRET_STORE`.
* `cnpg-operator` from the infra bundle — schmetterpause's database is a
  CloudNativePG `Cluster` applied by this Kustomization, and without the CRD the
  dry-run rejects the whole apply.
* **Kyverno, from somewhere else,** if `TABLETENNIS_SCHMETTERPAUSE_POLICY: on` —
  this repository ships no Kyverno component. Until it exists the policy's own
  child Kustomization stays NotReady with `no matches for kind
  ImageValidatingPolicy`; nothing else in the bundle is affected.

`zaehlwerk` has **no authentication of its own** — no token, no session — so its
HTTPRoute *is* the access control. Keep the gateway internal: anyone who can
reach the hostname can start a match, score it, take a point back, end it, and
with the panel wired, take over the LED strip. Upstream states this as a design
decision rather than an oversight.

## What is not pruned

schmetterpause's `Namespace` and its CloudNativePG `Cluster` both carry
`kustomize.toolkit.fluxcd.io/prune: disabled`. The PVC holds an ownerReference
on the Cluster, and a deleted Namespace takes the Cluster and its volume with
it — so removing this component leaves a namespace and a database behind, to be
deleted by hand. That is the right trade for data git cannot restore.
