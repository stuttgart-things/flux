# homerun2/light-catcher

WLED (addressable LED) device controller that manages smart lighting effects through Redis communication.

## Pattern

OCIRepository + Flux Kustomization

- **Source:** `oci://ghcr.io/stuttgart-things/homerun2-light-catcher-kustomize`
- **Image:** `ghcr.io/stuttgart-things/homerun2-light-catcher`

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Target namespace |
| `HOMERUN2_LIGHT_CATCHER_KUSTOMIZE_VERSION` | see `requirements.yaml` | OCI kustomize artifact version |
| `HOMERUN2_LIGHT_CATCHER_VERSION` | see `release.yaml` | Container image tag |
| `HOMERUN2_LIGHT_CATCHER_STREAMS` | `messages` | `REDIS_STREAMS`, comma-separated, e.g. `messages,alerts` |
| `HOMERUN2_LIGHT_CATCHER_PROFILE_CM` | `homerun2-light-catcher-profile` | ConfigMap (key `profile.yaml`) mounted as the profile. The default is the base's own, which drives the wled-mock |
| `HOMERUN2_REDIS_PASSWORD_B64` | *(required)* | Base64-encoded Redis password |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOMERUN2_LIGHT_CATCHER_HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Customizations

- Removes upstream Ingress and HTTPRoute, provides custom Gateway API HTTPRoute
- Mounts the profile from `HOMERUN2_LIGHT_CATCHER_PROFILE_CM`: the base's own ConfigMap (all rules on the wled-mock) unless the caller names one of its own. The catcher reads it at startup only; the Deployment's `reloader.stakater.com/auto` rolls the pod on a change where Reloader runs -- elsewhere restart it by hand
- Injects Redis credentials and connection (`redis-stack.homerun2.svc.cluster.local:6379`)
