# stuttgart-things/flux/clusterbook-operator

Flux app for clusterbook-operator — Kubernetes operator that reconciles `ClusterbookCluster`, `ClusterbookAllocation`, `ClusterbookLoadBalancer`, and `ClusterbookProviderConfig` CRs against a Clusterbook backend. Deploys via OCI kustomize base (built from KCL manifests) which bundles CRDs, namespace, RBAC, ServiceAccount, and Deployment.

## Kustomization Example

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: clusterbook-operator
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./apps/clusterbook-operator
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTERBOOK_OPERATOR_NAMESPACE: clusterbook-system
      CLUSTERBOOK_OPERATOR_VERSION: v0.15.0
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTERBOOK_OPERATOR_NAMESPACE` | `clusterbook-system` | Target namespace |
| `CLUSTERBOOK_OPERATOR_VERSION` | `v0.15.0` | Image + kustomize OCI tag |

## ClusterbookProviderConfig CR

The `ClusterbookProviderConfig` CR is **environment-specific data** (it references the kubeconfig Secret of the cluster hosting the clusterbook backend) and should be placed in the cluster config folder (e.g., `clusters/<env>/clusterbook-providerconfig.yaml`), not in this generic Flux app. Use these annotations so Flux seeds it once but never overwrites runtime changes:

```yaml
annotations:
  kustomize.toolkit.fluxcd.io/prune: disabled
  kustomize.toolkit.fluxcd.io/reconcile: disabled
```

## Example ClusterbookCluster CR

```bash
kubectl apply -f - <<EOF
---
apiVersion: clusterbook.stuttgart-things.com/v1alpha1
kind: ClusterbookCluster
metadata:
  name: my-cluster
  namespace: clusterbook-system
spec:
  providerConfigRef:
    name: default
  network: 10.31.101
  reservation: my-cluster
EOF
```
