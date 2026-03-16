# homerun2/omni-pitcher

Central API service for pitch/throw tracking and data aggregation. Requires an auth token for secured endpoints.

## Pattern

OCIRepository + Flux Kustomization

- **Source:** `oci://ghcr.io/stuttgart-things/homerun2-omni-pitcher-kustomize`
- **Image:** `ghcr.io/stuttgart-things/homerun2-omni-pitcher`

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Target namespace |
| `HOMERUN2_OMNI_PITCHER_VERSION` | `v1.2.0` | Container image tag |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | `changeme` | Auth token for pitcher API |
| `HOMERUN2_REDIS_PASSWORD_B64` | *(required)* | Base64-encoded Redis password |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Customizations

- Removes upstream Ingress, provides custom Gateway API HTTPRoute
- Creates `homerun2-omni-pitcher-token` Secret with the auth token
- Injects Redis credentials and connection (`redis-stack.homerun2.svc.cluster.local:6379`)
