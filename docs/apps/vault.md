# Vault (App)

HashiCorp Vault deployment with injector, custom images, and optional autounseal and HTTPRoute.

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
  path: ./apps/vault
  prune: true
  wait: true
  postBuild:
    substitute:
      VAULT_NAMESPACE: vault
      VAULT_VERSION: "1.9.0"
      REGISTRY: ghcr.io
      REPOSITORY: stuttgart-things/vault
      TAG: 1.20.2-debian-12-r2
      PULL_POLICY: Always
      INGRESS_ENABLED: "false"
      INGRESS_CLASS_NAME: nginx
      STORAGE_CLASS: openebs-hostpath
      INJECTOR_ENABLED: "true"
      INJECTOR_REPOSITORY: stuttgart-things/vault-k8s
      INJECTOR_TAG: 1.7.0-debian-12-r4
      INJECTOR_PULL_POLICY: Always
      ENABLE_VOLUME_PERMISSIONS: "true"
      OS_SHELL_REPOSITORY: stuttgart-things/os-shell
      OS_SHELL_TAG: 12-debian-12-r50
      OS_SHELL_PULL_POLICY: Always
      VAULT_INGRESS_HOSTNAME: vault
      VAULT_INGRESS_DOMAIN: example.com
      ISSUER_NAME: cluster-issuer-approle
      ISSUER_KIND: ClusterIssuer
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `VAULT_NAMESPACE` | `vault` | Target namespace |
| `VAULT_VERSION` | `1.9.0` | Helm chart version |
| `REGISTRY` | `ghcr.io` | Vault container registry |
| `REPOSITORY` | `stuttgart-things/vault` | Vault container repository |
| `TAG` | `1.20.2-debian-12-r2` | Vault container tag |
| `PULL_POLICY` | `IfNotPresent` | Image pull policy |
| `INGRESS_ENABLED` | `false` | Enable chart Ingress |
| `INGRESS_CLASS_NAME` | `nginx` | Ingress class |
| `STORAGE_CLASS` | `standard` | StorageClass for persistence |
| `INJECTOR_ENABLED` | `true` | Enable Vault Agent Injector |
| `INJECTOR_REPOSITORY` | `stuttgart-things/vault-k8s` | Injector image repository |
| `INJECTOR_TAG` | `1.7.0-debian-12-r4` | Injector image tag |
| `INJECTOR_PULL_POLICY` | `IfNotPresent` | Injector pull policy |
| `ENABLE_VOLUME_PERMISSIONS` | `true` | Enable init container for volume permissions |
| `OS_SHELL_REPOSITORY` | `stuttgart-things/os-shell` | OS shell image repository |
| `OS_SHELL_TAG` | `12-debian-12-r50` | OS shell image tag |
| `OS_SHELL_PULL_POLICY` | `IfNotPresent` | OS shell pull policy |
| `VAULT_INGRESS_HOSTNAME` | *(required)* | Ingress hostname |
| `VAULT_INGRESS_DOMAIN` | *(required)* | Ingress domain |
| `ISSUER_NAME` | *(required)* | cert-manager issuer name |
| `ISSUER_KIND` | *(required)* | Issuer kind |

## Optional: Autounseal

Deploy `vault-autounseal` by adding a second Kustomization pointing to `./apps/vault/autounseal`:

| Variable | Default | Description |
|---|---|---|
| `VAULT_NAMESPACE` | `vault` | Target namespace |
| `UNSEAL_HELM_REPO_URL` | `https://pytoshka.github.io/vault-autounseal` | Unseal Helm repo URL |
| `VAULT_AUTOUNSEAL_VERSION` | `0.5.3` | Autounseal chart version |
| `VAULT_AUTOUNSEAL_URL` | `http://vault-server.vault.svc:8200` | Vault server URL |
| `VAULT_AUTOUNSEAL_LABEL_SELECTOR` | `app.kubernetes.io/component=server` | Pod label selector |

## Optional: HTTPRoute (Gateway API)

Add a second Kustomization pointing to `./apps/vault/httproute` with `INGRESS_ENABLED: "false"`:

| Variable | Default | Description |
|---|---|---|
| `VAULT_NAMESPACE` | `vault` | Target namespace |
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `VAULT_HOSTNAME` | *(required)* | Hostname prefix |
| `VAULT_DOMAIN` | *(required)* | Domain suffix |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/stuttgart-things`
- Includes `pre-release.yaml` for TLS certificate via `sthings-cluster` helper chart
- See also [infra/vault](../infra/vault.md) for a minimal infrastructure-focused Vault deployment
