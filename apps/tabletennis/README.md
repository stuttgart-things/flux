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

On a bundle cluster, select `tabletennis-sops` or `tabletennis-sops-backup`
(alternatives of `tabletennis`, same child name): they apply this path with
the values from a `substituteFrom` Secret, `tabletennis-sops-secrets` by
default (`apps/platform/README.md`, "SOPS-only clusters"). Without the bundle,
point a Kustomization of your own at it, with the values in a SOPS-encrypted
Secret:

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

Through the bundle (`tabletennis-sops`, `tabletennis-sops-backup`) the pair is
ONE switch, `TABLETENNIS_SCOREBOARD_HANDOVER: off | sops` (default `off`): it
fills both component slots, so one cannot be selected without the other. The
token is a key of the `substituteFrom` Secret (`tabletennis-sops-secrets`),
which the AppProfiles generate. zaehlwerk's target is
`TABLETENNIS_ZAEHLWERK_SCHMETTERPAUSE_URL`, by default the HTTPRoute
(`https://<TABLETENNIS_SCHMETTERPAUSE_HOSTNAME>.<INFRA_DOMAIN>`). That needs
trust-manager's CA bundle, which zaehlwerk mounts as an optional ConfigMap. A
cluster without trust-manager sets the in-cluster Service instead:

```yaml
TABLETENNIS_SCOREBOARD_HANDOVER: sops
TABLETENNIS_ZAEHLWERK_SCHMETTERPAUSE_URL: http://schmetterpause.schmetterpause.svc.cluster.local
```

`schmetterpause-db-backup` needs ESO to copy trust-manager's CA bundle into
its Secret on every refresh. Its sops counterpart,
`schmetterpause-db-backup-sops`, takes a Secret the cluster repo ships, CA
included -- which then has to be re-encrypted by hand when that CA changes. It
also takes `SCHMETTERPAUSE_BACKUP_SERVER_NAME`, for archiving beside another
cluster's backups in one bucket.

`schmetterpause-db-backup-subst` is `-sops` with that Secret rendered in
the tabletennis build. The cluster ships no Secret manifest and no separate
Kustomization. It adds three keys to the `substituteFrom` Secret instead. Select
it **instead of** `-sops`, because it includes `-sops`:

```yaml
  components:
    - ../../components/schmetterpause-db-backup-subst
```

| Variable | Required | Notes |
|---|---|---|
| `SCHMETTERPAUSE_BACKUP_ACCESS_KEY_ID` | yes | S3 access key, `ACCESS_KEY_ID` in the Secret |
| `SCHMETTERPAUSE_BACKUP_SECRET_ACCESS_KEY` | yes | S3 secret key, `ACCESS_SECRET_KEY` |
| `SCHMETTERPAUSE_BACKUP_CA_PEM_B64` | for HTTPS | the endpoint's CA, `base64 -w0 ca.pem`. The default is a placeholder certificate (no key exists): the ObjectStore always names `endpointCA`, and a plain-HTTP endpoint never reads it |
| `SCHMETTERPAUSE_BACKUP_BUCKET` | yes | as for `-sops` |
| `SCHMETTERPAUSE_BACKUP_S3_ENDPOINT` | yes | as for `-sops`; `http://…` for in-cluster MinIO |
| `SCHMETTERPAUSE_BACKUP_SERVER_NAME`, `…_RETENTION`, `…_SCHEDULE` | no | as for `-sops` |

The CA is base64 because a multi-line PEM cannot pass through `postBuild`
substitution into a block scalar: every line after the first loses its
indentation. As with the other sops values, an unset key is not refused at
apply. It arrives as `""`, and the Cluster's `ContinuousArchiving` condition
reports the S3 error.

`schmetterpause-db-recovery` bootstraps the database from such an archive
instead of `initdb`. It creates no credentials and works with either variant.

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
| `TABLETENNIS_SCHMETTERPAUSE_ADMIN` | `off`, `on` | `SP_BOOTSTRAP_ADMIN` — the display name (`TABLETENNIS_SCHMETTERPAUSE_BOOTSTRAP_ADMIN`) that gets the admin flag at every start; also in the `tabletennis-sops*` bundle components |
| `TABLETENNIS_SCHMETTERPAUSE_SCOREBOARD` | `off`, `on` (`sops` under `profiles/sops`) | `SP_SCOREBOARD_TOKEN` — schmetterpause's `/api/players` and `/api/results` |
| `TABLETENNIS_ZAEHLWERK_HANDOVER` | `off`, `on` (`sops` under `profiles/sops`) | `SCHMETTERPAUSE_URL` + `SCHMETTERPAUSE_TOKEN` — a won match reported into schmetterpause |
| `TABLETENNIS_SCOREBOARD_HANDOVER` | `off`, `sops` | the two rows above as one switch, in the `tabletennis-sops*` bundle components only |
| `TABLETENNIS_FOB_CHECKIN` | `off`, `sops` | Check-in by fob, both ends as one switch, in the `tabletennis-sops*` bundle components only: `SP_RFID_UID_KEY` (`schmetterpause-fobs-sops`, from `SCHMETTERPAUSE_RFID_UID_KEY`) and zaehlwerk's `CHECKIN_TOKEN` (`zaehlwerk-checkin-sops`, from `ZAEHLWERK_CHECKIN_TOKEN`). See "Check-in at the table" |
| `TABLETENNIS_SCHMETTERPAUSE_ZAEHLWERK` | `off`, `on` | `SP_ZAEHLWERK_URL` = `TABLETENNIS_SCHMETTERPAUSE_ZAEHLWERK_URL` (default `https://<zaehlwerk hostname>.<domain>`) plus trust-manager's CA bundle in schmetterpause's pod — the running score on the start page, and with the scoreboard check-in by phone. In the `tabletennis-sops*` bundle components |
| `TABLETENNIS_SCHMETTERPAUSE_POLICY` | `off`, `on` | Kyverno's check on the application image's CI signature |
| `TABLETENNIS_ZAEHLWERK_PONG` | `off`, `on`, `attract` | The game next to zaehlwerk (zaehlwerk ADR-0006): whole matches through the buttons' ingest contract, played in a browser at `https://${TABLETENNIS_ZAEHLWERK_PONG_HOSTNAME:-zaehlwerk-pong}.<domain>` (one device, against the computer, two devices, or two bots). `attract` adds attract mode: two bots play by themselves once the table has been free for `TABLETENNIS_ZAEHLWERK_PONG_ATTRACT_AFTER` (default `10m`) — a variant, because the game's "off" is that variable being absent. Every pong match is a demo, never reported to schmetterpause, and a real match takes the table from it (zaehlwerk ADR-0008); the page has no login, so it sits on zaehlwerk's gateway. The bots' skill is `TABLETENNIS_ZAEHLWERK_PONG_BOT_SKILL` (`mittel`; `leicht`, `schwer`, or two comma-separated); one set to 11 by default (`PONG_BEST_OF=1`), and from v0.22.0 the lobby also offers best of 3 and 5 and suggests schmetterpause's players as names (zaehlwerk's URL and token, optional; names only, still a demo), and from v0.23.0 it offers a diagonal serve, as in doubles, and from v0.26.0 the service can play a bot game itself, which runs on with no tab open and every tab only watches (zaehlwerk ADR-0014). The image `zaehlwerk-pong` has zaehlwerk's tag (`ZAEHLWERK_VERSION`) and exists from v0.16.0 on; zaehlwerk's published base does not render it. With check-in on, `on` and `attract` also set zaehlwerk's `PONG_URL` to that address (from v0.22.0 also its *Pong* link), so the watch screen's side select hands an idle table to the game's screensaver after 3 minutes and takes it back on a check-in (zaehlwerk ADR-0013, v0.21.0+); from v0.24.0 `/ui/live` is that screen without demos and without the screensaver, for a display next to a real table. Also on the `tabletennis-sops*` bundles |
| `TABLETENNIS_ZAEHLWERK_PIEZO_SIM` | `off`, `on` | The piezo board simulator next to zaehlwerk: plays every match started on the scoring page. A won match is handed over like any other, so demo/test clusters only. Needs zaehlwerk ≥ v0.8.0; tuned with `TABLETENNIS_ZAEHLWERK_PIEZO_VERSION` (default `v0.11.0`), `…_PIEZO_PACE` (`1s`); the board plays best of 3 |. From v0.11.0 it serves a control endpoint on its Service `zaehlwerk-piezo-sim:8081`, which the table mock below pauses and tunes
| `TABLETENNIS_ZAEHLWERK_BUTTONS_SIM` | `off`, `on` | The table mock next to zaehlwerk: two emulated buttons and their hub, pressed on a page at `https://${TABLETENNIS_ZAEHLWERK_BUTTONS_HOSTNAME:-zaehlwerk-buttons}.<domain>`, with switches for the radio's and the hub's faults. The page also pauses and tunes a piezo board at `TABLETENNIS_ZAEHLWERK_BUTTONS_PIEZO_URL` (default: the piezo-sim's Service; with the piezo-sim off it reports the board as not answering). It takes points back without a login and scores into the running match, so demo/test/lab clusters only. From zaehlwerk v0.22.0 the switch also sets `BUTTONS_URL`, and zaehlwerk's scoring page links the page as *Buttons*. Needs zaehlwerk ≥ v0.10.0, the piezo section v0.11.0; image `TABLETENNIS_ZAEHLWERK_BUTTONS_VERSION` (default `v0.26.0`; from v0.12.0 the page can switch to a display device, from v0.18.0 it holds fobs to the reader, from v0.20.0 one per player of zaehlwerk's schmetterpause and with zaehlwerk's undo event, so keep it at zaehlwerk's version). Both switches also exist on the `tabletennis-sops*` bundles |

**`TABLETENNIS_ZAEHLWERK_SET_OPENER`** is a plain value, not a switch: who serves
first in the sets after the first, as zaehlwerk's `SET_OPENER` (v0.14.0,
zaehlwerk ADR-0005). `alternate` (default) is the rulebook, ITTF 2.13.6; `loser`
is the house rule where whoever lost the previous set opens the next one. A
match can still choose its own through the API.

**`TABLETENNIS_LINK_DOMAIN`** is a plain value too: the domain the pages' links
send a browser to, `INFRA_DOMAIN` by default. It covers zaehlwerk's *Buttons* and *Pong*
links (`BUTTONS_URL`, `PONG_URL`, so also the screensaver's address) and the
buttons page's way back to zaehlwerk. Set it where the same hostnames also have
routes on another Gateway, for example a public one with a Let's Encrypt wildcard next
to the internal one. The cluster still has to provide those routes. Links only:
nothing calls these addresses, and this layer's own routes stay on `INFRA_DOMAIN`.
zaehlwerk's *Schmetterpause* link is `TABLETENNIS_ZAEHLWERK_SCHMETTERPAUSE_URL`, which
zaehlwerk also calls, see below.

### The scoreboard and the handover are one feature

`schmetterpause-scoreboard-on` opens the surface; `zaehlwerk-handover-on` is the
client for it. **Select both or neither.** Either alone fails quietly:

* handover without scoreboard — zaehlwerk posts to a route the application never
  registered. Every finished match comes back 404, the match still scores and
  shows, and only zaehlwerk's log says so.
* scoreboard without handover — an `/api` nothing calls.

Under `profiles/sops` through the bundle they are one variable,
`TABLETENNIS_SCOREBOARD_HANDOVER`, so this cannot happen there (see "The
switches under sops" above). On the ESO path they are two, and:

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

### Check-in at the table

Two ways to claim a table half, both reported without an operator
(schmetterpause ADR-0024 to ADR-0026, zaehlwerk ADR-0010/0011). Both need the
scoreboard and the handover on.

* **By fob** — `TABLETENNIS_FOB_CHECKIN: sops`. The hub posts a fob and a half
  to zaehlwerk's `/ingest/checkin` with `CHECKIN_TOKEN` as bearer; zaehlwerk
  resolves the fob at schmetterpause, which knows fobs only with
  `SP_RFID_UID_KEY`. Either key alone checks nobody in, hence one switch. The
  published zaehlwerk base hands Secret keys to the container one by one and
  names `CHECKIN_TOKEN` from v0.19.0 on, so zaehlwerk v0.19.0+ is required
  (up to v0.18.0 `zaehlwerk-checkin-sops` added the env entry itself). The
  table mock (`zaehlwerk-buttons-sim-on`) reads the same key from
  `zaehlwerk-panel`, optionally: it holds the page's fobs to the reader once
  the switch is on. From v0.20.0 it offers one fob per player, read from
  zaehlwerk's `SCHMETTERPAUSE_URL` with its `SCHMETTERPAUSE_TOKEN`; a player's
  fob is unknown to a real schmetterpause until that player links it.
* **By phone** — `TABLETENNIS_SCHMETTERPAUSE_ZAEHLWERK: 'on'`. The QR code of
  a half opens `/table/left` or `/table/right` on schmetterpause, which claims
  the half at zaehlwerk's `POST /checkin/claim` with the scoreboard token. No
  key of its own, but the **pod** calls `SP_ZAEHLWERK_URL`, so the address
  has to resolve in-cluster and its certificate has to be trusted: the
  component mounts trust-manager's bundle (`cluster-trust-bundle`, optional)
  and sets `SSL_CERT_DIR`, as zaehlwerk's base does. The browser uses the same
  address for the live score, so it must also resolve for players, with
  schmetterpause's origin in `TABLETENNIS_ZAEHLWERK_ALLOWED_ORIGINS` (the
  default).

```yaml
TABLETENNIS_SCOREBOARD_HANDOVER: sops
TABLETENNIS_FOB_CHECKIN: sops
TABLETENNIS_SCHMETTERPAUSE_ZAEHLWERK: 'on'
# secret tabletennis-sops-secrets: SCHMETTERPAUSE_RFID_UID_KEY, ZAEHLWERK_CHECKIN_TOKEN
```

### Versions

| | needs |
|---|---|
| the scoreboard | schmetterpause **v0.10.0+** — in v0.9.0 the handlers do not exist |
| the handover | zaehlwerk **v0.5.0+** — earlier tags do not mount the trust-manager bundle, so every call over the HTTPRoute fails on the cluster CA while the pod looks healthy |
| an observer keeping score | schmetterpause **v0.14.0+** (`GET /api/operators`, its ADR-0023) and zaehlwerk **v0.6.0+**, which offers observers in *Keeping score*. Either alone changes nothing: the older side falls back to the player list |
| check-in by fob or phone | schmetterpause **v0.17.0+** and zaehlwerk **v0.19.0+** (`/ingest/checkin` with `CHECKIN_TOKEN` from the base, `/checkin/claim`); the table mock's fobs need `zaehlwerk-buttons` **v0.18.0+**, a fob per player **v0.20.0+** |
| the side select and the screensaver | zaehlwerk **v0.21.0+** with check-in on; the screensaver also needs `TABLETENNIS_ZAEHLWERK_PONG` `on` or `attract`. Older tags ignore `PONG_URL` |
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
