# Vault (Infrastructure)

Minimal HashiCorp Vault deployment for infrastructure use, with Gateway API HTTPRoute.

## Deployment

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    tag: v1.0.0
  url: https://github.com/stuttgart-things/flux.git
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: vault
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/vault
  prune: true
  wait: true
  postBuild:
    substitute:
      VAULT_NAMESPACE: vault
      VAULT_VERSION: "1.9.0"
      STORAGE_CLASS: local-path
      REGISTRY: ghcr.io
      REPOSITORY: stuttgart-things/vault
      TAG: 1.20.2-debian-12-r2
      PULL_POLICY: IfNotPresent
      INJECTOR_ENABLED: "false"
      ENABLE_VOLUME_PERMISSIONS: "true"
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      VAULT_HOSTNAME: vault
      VAULT_DOMAIN: example.sthings-vsphere.labul.sva.de
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `VAULT_NAMESPACE` | `vault` | Target namespace |
| `VAULT_VERSION` | `1.9.0` | Helm chart version |
| `STORAGE_CLASS` | `local-path` | StorageClass for persistence |
| `REGISTRY` | `ghcr.io` | Container image registry |
| `REPOSITORY` | `stuttgart-things/vault` | Container image repository |
| `TAG` | `1.20.2-debian-12-r2` | Container image tag |
| `PULL_POLICY` | `IfNotPresent` | Image pull policy |
| `INJECTOR_ENABLED` | `false` | Enable Vault Agent Injector |
| `ENABLE_VOLUME_PERMISSIONS` | `true` | Enable volume permission init container |
| `OS_SHELL_REPOSITORY` | `stuttgart-things/os-shell` | OS shell image repository |
| `OS_SHELL_TAG` | `12-debian-12-r50` | OS shell image tag |
| `OS_SHELL_PULL_POLICY` | `IfNotPresent` | OS shell pull policy |
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `VAULT_HOSTNAME` | *(required)* | HTTPRoute hostname prefix |
| `VAULT_DOMAIN` | *(required)* | HTTPRoute domain suffix |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/stuttgart-things`
- Includes `httproute.yaml` for Gateway API access
- Injector is disabled by default (unlike the [apps/vault](../apps/vault.md) version)
- For a full-featured Vault deployment with injector, autounseal, and TLS certificates, see [apps/vault](../apps/vault.md)
