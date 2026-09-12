# homerun2/config-viewer

Read-only view of which homerun2 alert triggers what in which catcher: components, findings, a severity × system matrix and a dry run ([homerun-library#122](https://github.com/stuttgart-things/homerun-library/issues/122)). It reads the Deployments and ConfigMaps of its namespace through the Kubernetes API and never talks to Redis.

## Pattern

OCIRepository + Flux Kustomization

- **Source:** `oci://ghcr.io/stuttgart-things/homerun2-config-viewer-kustomize`
- **Image:** `ghcr.io/stuttgart-things/homerun2-config-viewer`

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Target namespace -- also the namespace the viewer reads |
| `HOMERUN2_CONFIG_VIEWER_KUSTOMIZE_VERSION` | see `requirements.yaml` | OCI kustomize artifact version |
| `HOMERUN2_CONFIG_VIEWER_VERSION` | see `release.yaml` | Container image tag |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOMERUN2_CONFIG_VIEWER_HOSTNAME` | `config-viewer` | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Customizations

- Removes the KCL-generated HTTPRoute; `route/` provides the Gateway API HTTPRoute
- No credentials: no Redis Secret, no token. The base ships a namespace-scoped `Role` + `RoleBinding` with `get`/`list` on `deployments` and `configmaps` only
