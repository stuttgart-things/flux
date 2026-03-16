# homerun2/scout

Service discovery and monitoring agent with TLS certificate trust configuration via trust-manager.

## Pattern

OCIRepository + Flux Kustomization

- **Source:** `oci://ghcr.io/stuttgart-things/homerun2-scout-kustomize`
- **Image:** `ghcr.io/stuttgart-things/homerun2-scout`

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Target namespace |
| `HOMERUN2_SCOUT_VERSION` | `v0.5.0` | Container image tag |
| `HOMERUN2_SCOUT_AUTH_TOKEN` | `changeme` | Auth token for scout API |
| `HOMERUN2_REDIS_PASSWORD_B64` | *(required)* | Base64-encoded Redis password |
| `HOMERUN2_SCOUT_TRUST_BUNDLE_CM` | `cluster-trust-bundle` | ConfigMap with CA bundle for TLS |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOMERUN2_SCOUT_HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Customizations

- Removes upstream Ingress and HTTPRoute, provides custom Gateway API HTTPRoute
- Mounts trust-manager CA bundle volume for TLS verification
- Sets `SSL_CERT_DIR=/etc/ssl/custom` environment variable
- Creates auth-token Secret
- Injects Redis credentials and connection (`redis-stack.homerun2.svc.cluster.local:6379`)
