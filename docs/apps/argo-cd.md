# Argo CD

GitOps continuous delivery tool with Vault plugin integration.

## Prerequisites

Create a secret with Argo CD admin password and Vault credentials:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
data:
  ARGO_CD_SERVER_ADMIN_PASSWORD: <BASE64_HTPASSWD_VALUE>
  AVP_ROLE_ID: <BASE64_VALUE>
  AVP_SECRET_ID: <BASE64_VALUE>
  AVP_VAULT_ADDR: <BASE64_VALUE>
  VAULT_NAMESPACE: <BASE64_VALUE>
  VAULT_ADDR: <BASE64_VALUE>
kind: Secret
metadata:
  name: argocd-secrets
  namespace: flux-system
type: Opaque
EOF
```

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
  name: argo-cd
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/argo-cd
  prune: true
  wait: true
  postBuild:
    substitute:
      ARGO_CD_VERSION: "7.7.14"
      ARGO_CD_NAMESPACE: argo-cd
      SERVICE_TYPE: ClusterIP
      IMAGE_AVP: ghcr.io/stuttgart-things/sthings-avp:1.18.1
      INGRESS_HOSTNAME: argo-cd
      INGRESS_DOMAIN: example.com
      INGRESS_SECRET_NAME: argocd-server-tls
      ISSUER_NAME: cluster-issuer-approle
      ISSUER_KIND: ClusterIssuer
      ARGO_CD_PASSWORD_MTIME: "2024-09-16T12:51:06UTC"
    substituteFrom:
      - kind: Secret
        name: argocd-secrets
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `ARGO_CD_NAMESPACE` | `argocd` | Target namespace |
| `ARGO_CD_VERSION` | `7.7.14` | Helm chart version |
| `ARGO_CD_SERVER_ADMIN_PASSWORD` | *(required, from secret)* | Admin password in htpasswd format |
| `ARGO_CD_PASSWORD_MTIME` | `2024-09-16T12:51:06UTC` | Password modification time |
| `IMAGE_AVP` | `ghcr.io/stuttgart-things/sthings-avp:1.18.1-1.30.2-3.16.4` | Vault plugin sidecar image |
| `INGRESS_HOSTNAME` | *(required)* | Ingress hostname prefix |
| `INGRESS_DOMAIN` | *(required)* | Ingress domain suffix |
| `INGRESS_SECRET_NAME` | `argocd-server-tls` | TLS secret name |
| `ISSUER_NAME` | *(required)* | cert-manager issuer name |
| `ISSUER_KIND` | *(required)* | Issuer kind (ClusterIssuer/Issuer) |
| `VAULT_ADDR` | *(required, from secret)* | Vault server address |
| `VAULT_NAMESPACE` | *(required, from secret)* | Vault namespace |
| `VAULT_ROLE_ID` | *(required, from secret)* | Vault AppRole role ID |
| `VAULT_SECRET_ID` | *(required, from secret)* | Vault AppRole secret ID |

## Notes

- Uses the `sthings-avp` (Argo Vault Plugin) sidecar for Vault secret injection
- The `argocd-deployment` HelmRelease depends on `argocd-configuration` (pre-release)
- Includes ConfigManagementPlugins for Helm, Kustomize, and plain YAML with Vault templating
