# Bootstrap with Flux Operator

Install the Flux Operator and create a `FluxInstance` for full control over Flux components.

## 1. Install the Flux Operator

```bash
helm upgrade --install flux-operator \
  oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator \
  --namespace flux-system \
  --create-namespace \
  --version 0.24.0
```

## 2. Create Git Authentication Secret

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: git-token-auth
  namespace: flux-system
type: Opaque
stringData:
  username: $GITHUB_USER
  password: $GITHUB_TOKEN
EOF
```

## 3. Create SOPS Secret (Optional)

Required only if you use SOPS-encrypted secrets. See [SOPS Secrets](sops-secrets.md) for details.

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: sops-age
  namespace: flux-system
type: Opaque
stringData:
  age.agekey: AGE-SECRET-KEY-1...
EOF
```

## 4. Apply FluxInstance

```bash
kubectl apply -f - <<EOF
---
apiVersion: fluxcd.controlplane.io/v1
kind: FluxInstance
metadata:
  name: flux
  namespace: flux-system
  annotations:
    fluxcd.controlplane.io/reconcileEvery: "1h"
    fluxcd.controlplane.io/reconcileTimeout: "5m"
spec:
  distribution:
    version: "2.x"
    registry: "ghcr.io/fluxcd"
    artifact: "oci://ghcr.io/controlplaneio-fluxcd/flux-operator-manifests"
  components:
    - source-controller
    - kustomize-controller
    - helm-controller
    - notification-controller
    - image-reflector-controller
    - image-automation-controller
  cluster:
    type: kubernetes
    multitenant: false
    networkPolicy: true
    domain: "cluster.local"
  kustomize:
    patches:
      - patch: |
          - op: add
            path: /spec/decryption
            value:
              provider: sops
              secretRef:
                name: sops-age
        target:
          group: kustomize.toolkit.fluxcd.io
          version: v1
          kind: Kustomization
      - target:
          kind: Deployment
          name: "(kustomize-controller|helm-controller)"
        patch: |
          - op: add
            path: /spec/template/spec/containers/0/args/-
            value: --concurrent=10
          - op: add
            path: /spec/template/spec/containers/0/args/-
            value: --requeue-dependency=5s
  sync:
    kind: GitRepository
    url: https://github.com/stuttgart-things/stuttgart-things.git
    ref: refs/heads/main
    path: clusters/<your-cluster>
    pullSecret: git-token-auth
EOF
```

Update `spec.sync.path` to match your cluster's directory in the main GitOps repo.

## Key Configuration

- **SOPS patch**: Automatically adds SOPS decryption to all `Kustomization` resources
- **Concurrency patch**: Increases concurrent reconciliations to 10 with 5s requeue delay
- **Components**: All six Flux controllers are enabled including image automation
