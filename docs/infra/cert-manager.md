# cert-manager

TLS certificate management with Vault PKI backend integration.

## Prerequisites

Create a secret with Vault PKI credentials:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
data:
  VAULT_ADDR: <BASE64_VALUE>
  VAULT_CA_BUNDLE: <BASE64_VALUE>
  VAULT_NAMESPACE: <BASE64_VALUE>
  VAULT_PKI_PATH: <BASE64_VALUE>
  VAULT_ROLE_ID: <BASE64_VALUE>
  VAULT_SECRET_ID: <BASE64_VALUE>
  VAULT_TOKEN: <BASE64_VALUE>
kind: Secret
metadata:
  name: cert-manager-secret
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
  name: cert-manager
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/cert-manager
  prune: true
  wait: true
  postBuild:
    substitute:
      CERT_MANAGER_NAMESPACE: cert-manager
      CERT_MANAGER_VERSION: "v1.18.2"
      CERT_MANAGER_INSTALL_CRDS: "true"
    substituteFrom:
      - kind: Secret
        name: cert-manager-secret
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `CERT_MANAGER_NAMESPACE` | `cert-manager` | Target namespace |
| `CERT_MANAGER_VERSION` | `v1.18.2` | Helm chart version |
| `CERT_MANAGER_INSTALL_CRDS` | `true` | Install CRDs |
| `VAULT_ADDR` | *(required, from secret)* | Vault server address |
| `VAULT_CA_BUNDLE` | *(required, from secret)* | Vault CA certificate bundle |
| `VAULT_NAMESPACE` | *(required, from secret)* | Vault namespace |
| `VAULT_PKI_PATH` | *(required, from secret)* | Vault PKI secrets engine path |
| `VAULT_ROLE_ID` | *(required, from secret)* | Vault AppRole role ID |
| `VAULT_SECRET_ID` | *(required, from secret)* | Vault AppRole secret ID |

## Notes

- Uses HelmRepository from `https://charts.jetstack.io`
- Includes `post-release.yaml` that creates a `ClusterIssuer` via the `sthings-cluster` helper chart
- The `cert-manager-configuration` HelmRelease depends on `cert-manager` (waits for CRDs to be available)
