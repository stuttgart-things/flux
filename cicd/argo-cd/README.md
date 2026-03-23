# stuttgart-things/flux/cicd/argo-cd

Deploys Argo CD via the official Helm chart (v9.4.15, appVersion v3.3.4) with Vault Plugin (AVP) sidecars for secret injection.

## Structure

```
argo-cd/
├── kustomization.yaml          # Base: namespace + certs + deployment
├── requirements.yaml           # Namespace + HelmRepositories (OCI)
├── pre-release.yaml            # Vault AppRole secret + TLS Certificate
├── release.yaml                # Argo CD HelmRelease with AVP sidecars
└── components/
    └── httproute/              # Optional: Gateway API HTTPRoute
        ├── kustomization.yaml
        └── httproute.yaml
```

## Requirements

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    branch: main
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>CREATE SECRET</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: argocd-secrets
  namespace: flux-system
type: Opaque
stringData:
  ARGO_CD_SERVER_ADMIN_PASSWORD: "<htpasswd-bcrypt-hash>" # pragma: allowlist secret
  VAULT_ROLE_ID: "<vault-approle-role-id>"
  VAULT_SECRET_ID: "<vault-approle-secret-id>"
  VAULT_ADDR: "https://vault.example.com"
  VAULT_NAMESPACE: "root"
EOF
```

Generate the admin password hash:

```bash
htpasswd -nbBC 10 "" 'your-password' | tr -d ':\n' | sed 's/$2y/$2a/'
```

</details>

## Deployment (with nginx Ingress)

```bash
kubectl apply -f - <<EOF
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
  path: ./cicd/argo-cd
  prune: true
  wait: true
  postBuild:
    substitute:
      ARGO_CD_VERSION: "9.4.15"
      ARGO_CD_NAMESPACE: argocd
      ARGO_CD_INGRESS_ENABLED: "true"
      ARGO_CD_INGRESS_CLASS: nginx
      INGRESS_HOSTNAME: argocd
      INGRESS_DOMAIN: example.sthings-vsphere.labul.sva.de
      INGRESS_SECRET_NAME: argocd-server-tls
      ISSUER_NAME: vault-pki
      ISSUER_KIND: ClusterIssuer
      ARGO_CD_PASSWORD_MTIME: "2024-09-16T12:51:06UTC"
    substituteFrom:
      - kind: Secret
        name: argocd-secrets
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: argocd-deployment
      namespace: argocd
EOF
```

## Deployment (with Gateway API HTTPRoute)

```bash
kubectl apply -f - <<EOF
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
  path: ./cicd/argo-cd
  prune: true
  wait: true
  postBuild:
    substitute:
      ARGO_CD_VERSION: "9.4.15"
      ARGO_CD_NAMESPACE: argocd
      ARGO_CD_INGRESS_ENABLED: "false"
      INGRESS_HOSTNAME: argocd
      INGRESS_DOMAIN: example.sthings-vsphere.labul.sva.de
      INGRESS_SECRET_NAME: argocd-server-tls
      ISSUER_NAME: vault-pki
      ISSUER_KIND: ClusterIssuer
      ARGO_CD_PASSWORD_MTIME: "2024-09-16T12:51:06UTC"
    substituteFrom:
      - kind: Secret
        name: argocd-secrets
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: argocd-deployment
      namespace: argocd
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: argo-cd-httproute
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/argo-cd/components/httproute
  prune: true
  wait: true
  dependsOn:
    - name: argo-cd
  postBuild:
    substitute:
      ARGO_CD_NAMESPACE: argocd
      ARGO_CD_HOSTNAME: argocd
      ARGO_CD_DOMAIN: example.sthings-vsphere.labul.sva.de
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
EOF
```

## Parameters

### Base

| Variable | Default | Description |
|---|---|---|
| `ARGO_CD_NAMESPACE` | `argocd` | Target namespace |
| `ARGO_CD_VERSION` | `9.4.15` | Helm chart version |
| `ARGO_CD_INGRESS_ENABLED` | `false` | Enable nginx Ingress (disable when using HTTPRoute) |
| `ARGO_CD_INGRESS_CLASS` | `nginx` | IngressClassName (when ingress enabled) |
| `INGRESS_HOSTNAME` | *(required)* | Hostname prefix for ingress/certificate |
| `INGRESS_DOMAIN` | *(required)* | Base domain for ingress/certificate |
| `INGRESS_SECRET_NAME` | `argocd-server-tls` | TLS secret name |
| `ISSUER_NAME` | *(required)* | cert-manager ClusterIssuer name |
| `ISSUER_KIND` | *(required)* | Issuer kind (ClusterIssuer) |
| `IMAGE_AVP` | `ghcr.io/stuttgart-things/sthings-avp:1.18.1-1.32.3-3.17.2` | Vault plugin sidecar image |
| `AVP_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | ConfigMap with CA bundle (from trust-manager) |
| `AVP_TRUST_BUNDLE_KEY` | `trust-bundle.pem` | Key in the trust bundle ConfigMap |
| `AVP_SSL_CERT_DIR` | `/etc/ssl/custom` | Directory to mount the CA bundle into (sets `SSL_CERT_DIR`) |
| `ARGO_CD_PASSWORD_MTIME` | `2024-09-16T12:51:06UTC` | Admin password modification time |
| `ARGO_CD_SERVER_ADMIN_PASSWORD` | *(from Secret)* | Admin password (bcrypt htpasswd hash) |
| `VAULT_ROLE_ID` | *(from Secret)* | Vault AppRole Role ID |
| `VAULT_SECRET_ID` | *(from Secret)* | Vault AppRole Secret ID |
| `VAULT_ADDR` | *(from Secret)* | Vault server address |
| `VAULT_NAMESPACE` | *(from Secret)* | Vault namespace |

### HTTPRoute Component

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `ARGO_CD_HOSTNAME` | *(required)* | Hostname prefix |
| `ARGO_CD_DOMAIN` | *(required)* | Base domain |
| `ARGO_CD_NAMESPACE` | `argocd` | Namespace for HTTPRoute |

## Vault Plugin Sidecars

Three AVP sidecar containers run alongside the repo-server for secret injection:

| Plugin | Purpose |
|---|---|
| `argocd-vault-plugin` | Processes raw YAML with `<path:...>` Vault placeholders |
| `argocd-vault-plugin-helm` | Runs `helm template` then pipes through AVP |
| `argocd-vault-plugin-kustomize` | Runs `kustomize build` then pipes through AVP |

Sidecar image: `ghcr.io/stuttgart-things/sthings-avp:1.18.1-1.32.3-3.17.2` (AVP 1.18.1, kubectl 1.32.3, kustomize 3.17.2)

## Verify

```bash
# Kustomizations
kubectl get kustomizations -n flux-system argo-cd argo-cd-httproute

# HelmReleases
kubectl get helmreleases -n argocd

# Pods
kubectl get pods -n argocd

# HTTPRoutes
kubectl get httproutes -n argocd

# Certificates
kubectl get certificates -n argocd

# Check CMP plugins are loaded
kubectl get cm argocd-cmp-cm -n argocd -o yaml | grep 'name: argocd-vault-plugin'

# Check AVP sidecar containers
kubectl get pods -n argocd -l app.kubernetes.io/component=repo-server -o jsonpath='{.items[0].spec.containers[*].name}'
```

See also: [claims CLI](https://github.com/stuttgart-things/claims) | [claim-machinery-api](https://github.com/stuttgart-things/claim-machinery-api)
