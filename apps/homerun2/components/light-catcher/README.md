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
| `HOMERUN2_LIGHT_CATCHER_VERSION` | `v0.3.0` | Container image tag |
| `HOMERUN2_REDIS_PASSWORD_B64` | *(required)* | Base64-encoded Redis password |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOMERUN2_LIGHT_CATCHER_HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Customizations

- Removes upstream Ingress and HTTPRoute, provides custom Gateway API HTTPRoute
- Deletes KCL-generated profile ConfigMap (calling side provides its own)
- Injects Redis credentials and connection (`redis-stack.homerun2.svc.cluster.local:6379`)
