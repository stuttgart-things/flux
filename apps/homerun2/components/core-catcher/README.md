# homerun2/core-catcher

Web-based event catcher service running in `web` mode. Connects to Redis for data persistence.

## Pattern

OCIRepository + Flux Kustomization

- **Source:** `oci://ghcr.io/stuttgart-things/homerun2-core-catcher-kustomize`
- **Image:** `ghcr.io/stuttgart-things/homerun2-core-catcher`

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Target namespace |
| `HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION` | `v0.5.0` | OCI kustomize artifact version |
| `HOMERUN2_CORE_CATCHER_VERSION` | `v0.5.0` | Container image tag |
| `HOMERUN2_REDIS_PASSWORD_B64` | *(required)* | Base64-encoded Redis password |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Customizations

- Removes upstream Ingress and HTTPRoute, provides custom Gateway API HTTPRoute
- Injects Redis credentials and connection (`redis-stack.homerun2.svc.cluster.local:6379`)
- Sets `CATCHER_MODE=web` environment variable
