# homerun2/light-catcher-tabletennis

A second light-catcher, for the WLED strip at the table tennis table. It reads
only the `tabletennis` stream, which [zaehlwerk](https://github.com/stuttgart-things/zaehlwerk)
pitches every scoring transition to.

## Pattern

OCIRepository + Flux Kustomization, the same base as `light-catcher`:

- **Source:** `oci://ghcr.io/stuttgart-things/homerun2-light-catcher-kustomize`
- **Image:** `ghcr.io/stuttgart-things/homerun2-light-catcher`

## What it lights

| zaehlwerk sends | Tags matched | Effect |
|---|---|---|
| a won match | `transition=match_won` | Fireworks, 10s |
| a won set | `transition=set_won` | Rainbow, 4s |
| a point for side a | `transition=point`, `side=a` | Solid blue, 1s |
| a point for side b | `transition=point`, `side=b` | Solid red, 1s |
| an undo, a correction that lowered a score | -- | nothing (`no matching effect` in the log) |

Rules are matched in document order, first match wins (light-catcher v1.0.2+),
and a rule's `tags` must all be present in the message (v1.1.0+). zaehlwerk sets
the tags from v0.3.0.

## Why a second instance, and why its own namespace

**Not a second stream on `light-catcher`.** That instance's profile is wildcard
rules for cluster alerts; `info` on `systems: ["*"]` would fire DJ Light for
three seconds per point, and a profile cannot express "match and do nothing" or
"any system but this one".

**Not a name suffix in `homerun2`.** The kustomize base names every object
`homerun2-light-catcher` and selects on those labels -- the Service, the
Deployment selector, the pod anti-affinity. Renamed side by side, each Service
would route to both instances. In its own namespace the base applies unchanged;
redis is still reached at `redis-stack.${HOMERUN2_NAMESPACE}`.

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Where redis runs |
| `HOMERUN2_LIGHT_CATCHER_TABLETENNIS_NAMESPACE` | `homerun2-tabletennis` | This instance's namespace |
| `HOMERUN2_LIGHT_CATCHER_TABLETENNIS_WLED_ENDPOINT` | `http://homerun2-wled-mock.homerun2.svc.cluster.local` | The WLED device the effects go to |
| `HOMERUN2_LIGHT_CATCHER_KUSTOMIZE_VERSION` | `v1.1.3` | OCI kustomize artifact version, shared with `light-catcher` |
| `HOMERUN2_LIGHT_CATCHER_VERSION` | `v1.1.3` | Container image tag, shared with `light-catcher` |
| `HOMERUN2_SECRET_STORE` | *(required)* | ClusterSecretStore for `eso/` |
| `HOMERUN2_SECRET_PATH` | `homerun2` | Entry holding `redis-password` |
| `HOMERUN2_LIGHT_CATCHER_TABLETENNIS_HOSTNAME` | `light-catcher-tabletennis` | HTTPRoute hostname prefix (`route/`) |
| `GATEWAY_NAME`, `GATEWAY_NAMESPACE`, `DOMAIN` | *(required)* | HTTPRoute parent and domain (`route/`) |

## Customizations

- Removes the base's HTTPRoute (`route/` brings one with this hostname) and its placeholder redis Secret (`eso/` brings the real one)
- Points `REDIS_ADDR` at the homerun2 namespace, `REDIS_STREAM` at `tabletennis`, and uses consumer group `homerun2-light-catcher-tabletennis`
- Replaces the profile ConfigMap with the table's effects
