# stuttgart-things/flux/infra/cert-manager

## REQUIREMENTS

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
    branch: feature/add-cert-manager
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>SECRET</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: v1
data:
  VAULT_ADDR: <ADD-B64-VALUE>
  VAULT_CA_BUNDLE: <ADD-B64-VALUE>
  VAULT_NAMESPACE: <ADD-B64-VALUE>
  VAULT_PKI_PATH: <ADD-B64-VALUE>
  VAULT_ROLE_ID: <ADD-B64-VALUE>
  VAULT_SECRET_ID: <ADD-B64-VALUE>
  VAULT_TOKEN: <ADD-B64-VALUE>
kind: Secret
metadata:
  labels:
    kustomize.toolkit.fluxcd.io/name: flux-system
    kustomize.toolkit.fluxcd.io/namespace: flux-system
  name: cert-manager-secret
  namespace: flux-system
type: Opaque
EOF
```

</details>


## KUSTOMIZATION

```bash
kubectl apply -f - <<EOF
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
    name: flux-system
  path: ./infra/cert-manager
  prune: true
  wait: true
  postBuild:
    substitute:
      CERT_MANAGER_VERSION: 1.16.2
      CERT_MANAGER_NAMESPACE: cert-manager
      CERT_MANAGER_INSTALL_CRDS: "true"
    substituteFrom:
      - kind: Secret
        name: cert-manager-secret
EOF
```
