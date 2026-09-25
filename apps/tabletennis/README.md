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

### Without external-secrets (`profiles/sops`)

`profiles/base` reads its credentials through ExternalSecrets
(`components/<app>/eso`). `profiles/sops` is the same pair with plain Secrets
instead (`components/<app>/sops`). Use it on clusters where Flux already
decrypts SOPS and an external-secrets controller, a `ClusterSecretStore` and an
OpenBao auth mount would exist only to deliver these few values. That is
typically an edge cluster.

It is not a bundle component: point a Kustomization of your own at it, with the
values in a SOPS-encrypted Secret:

```yaml
spec:
  path: ./apps/tabletennis/profiles/sops
  dependsOn:
    - name: cnpg-operator     # the Cluster CRD, else the dry-run fails the apply
  postBuild:
    substituteFrom:
      - kind: Secret
        name: tabletennis-secrets-subst
    substitute:
      DOMAIN: example.lab
      GATEWAY_NAME: my-gateway
```

| Variable | Required | Notes |
|---|---|---|
| `SCHMETTERPAUSE_SESSION_KEY` | yes | ≥ 32 characters; `openssl rand -base64 32` |
| `SCHMETTERPAUSE_DB_PASSWORD` | yes | goes into `SP_DATABASE_URL` as well, so URL-safe: `openssl rand -hex 32` |
| `ZAEHLWERK_OMNI_PITCHER_TOKEN` | with a panel | sentinel default; zaehlwerk reads it only with a panel |
| `ZAEHLWERK_REDIS_PASSWORD` | with a panel | as above |

The database username is fixed at `schmetterpause`, the owner `database.yaml`
bootstraps. `schmetterpause-db` is built with all three keys the ESO template
produces (`username`, `password`, `SP_DATABASE_URL` with `?sslmode=require`) and
the same `kubernetes.io/basic-auth` type.

**An unset required value is not refused at apply.** For a Secret's
`stringData`, the API server stores YAML null as `""`. The guard is
schmetterpause itself, which refuses to serve with an empty or short session
key. The pod does not come up and the Kustomization does not go Ready. There is
no equivalent check on the password, so set it.

**The switches under sops.** `schmetterpause-scoreboard-on` and
`zaehlwerk-handover-on` write their token into ExternalSecrets, which this
profile deletes. So each has a sops counterpart that writes it into the plain
Secret instead. Add both as components of your Kustomization:

```yaml
  components:
    - ../../components/schmetterpause-scoreboard-sops
    - ../../components/zaehlwerk-handover-sops
```

Both read one variable, `SCHMETTERPAUSE_SCOREBOARD_TOKEN` (`openssl rand -hex
32`). It has no default, because a known token would open `/api`. Unset, it
arrives as `""`. schmetterpause then registers no `/api` at all, and zaehlwerk
logs `authenticated=false`, so check both after enabling it.

`schmetterpause-db-backup` has no sops counterpart. It needs ESO to copy
trust-manager's CA bundle into its Secret on every refresh, and a plain Secret
cannot follow a ConfigMap.

**Picking the wrong variant fails the build.** The `eso/` and `sops/` components
stamp the app Kustomizations with
`tabletennis.stuttgart-things.com/credentials: eso|sops`. Every mode-specific
component tests that annotation first, so a wrong pairing refuses to build and
names itself in the error:

```
.../components/zaehlwerk-handover-on': testing value
/metadata/annotations/tabletennis.stuttgart-things.com~1credentials failed
```

Before, the ESO switch under sops targeted an ExternalSecret that no longer
existed and silently did nothing.

**Moving a running cluster between the two:**

* A Secret's type is immutable. A cluster whose `schmetterpause-db` was created
  as `Opaque` (a hand-built setup, say) gets `conflict with
  "kustomize-controller": .type` until that Secret is deleted once.
* ESO owns the Secrets it writes. Going from `eso` to `sops` deletes the
  ExternalSecrets, and the garbage collector takes their Secrets with them
  until the next reconcile applies the plain ones again. Reconcile the
  Kustomization by hand right after switching.

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
| `TABLETENNIS_SCHMETTERPAUSE_SCOREBOARD` | `off`, `on` (`sops` under `profiles/sops`) | `SP_SCOREBOARD_TOKEN` — schmetterpause's `/api/players` and `/api/results` |
| `TABLETENNIS_ZAEHLWERK_HANDOVER` | `off`, `on` (`sops` under `profiles/sops`) | `SCHMETTERPAUSE_URL` + `SCHMETTERPAUSE_TOKEN` — a won match reported into schmetterpause |
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
| an observer keeping score | schmetterpause **v0.14.0+** (`GET /api/operators`, its ADR-0023) and zaehlwerk **v0.6.0+**, which offers observers in *Keeping score*. Either alone changes nothing: the older side falls back to the player list |
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
