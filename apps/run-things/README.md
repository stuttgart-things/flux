# stuttgart-things/flux/run-things

Flux app for run-things — service portal & health monitor for infrastructure services. Deploys via OCI kustomize base (built from KCL manifests) with Gateway API HTTPRoute.

## Kustomization Example

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: run-things
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./apps/run-things
  prune: true
  wait: true
  postBuild:
    substitute:
      RUN_THINGS_NAMESPACE: run-things
      RUN_THINGS_VERSION: v0.2.0
      RUN_THINGS_HOSTNAME: run-things
      RUN_THINGS_CONFIG_NAME: portal-labul
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `RUN_THINGS_NAMESPACE` | `run-things` | Target namespace |
| `RUN_THINGS_VERSION` | `v0.2.0` | Image + kustomize OCI tag |
| `RUN_THINGS_HOSTNAME` | `run-things` | HTTPRoute hostname prefix |
| `RUN_THINGS_CONFIG_NAME` | `portal-labul` | ServicePortal CR name |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute hostname |

## ServicePortal CR

The ServicePortal CR is **environment-specific data** and should be placed in the cluster config folder (e.g., `clusters/<env>/run-things-serviceportal.yaml`), not in this generic Flux app. Use these annotations so Flux seeds it once but never overwrites runtime changes:

```yaml
annotations:
  kustomize.toolkit.fluxcd.io/prune: disabled
  kustomize.toolkit.fluxcd.io/reconcile: disabled
```

## Example ServicePortal CR

```yaml
apiVersion: github.stuttgart-things.com/v1
kind: ServicePortal
metadata:
  name: portal-labul
  namespace: run-things
spec:
  services:
    - name: ArgoCD
      description: GitOps continuous delivery
      category: CI/CD
      url: https://argocd.example.com
      healthCheck:
        enabled: true
        interval: 30
        expectedStatus: 200
        tlsCheck: true
    - name: Harbor
      description: Container registry
      category: Registry
      url: https://harbor.example.com
      healthCheck:
        enabled: true
        interval: 30
        expectedStatus: 200
```

## Endpoints

| Endpoint | Description |
|---|---|
| `https://<hostname>.<domain>/` | HTMX dashboard |
| `https://<hostname>.<domain>/admin` | Admin panel (add/edit/delete services) |
| `https://<hostname>.<domain>/api/v1/services` | REST API — list services |
| `https://<hostname>.<domain>/api/v1/health` | Health probe |
