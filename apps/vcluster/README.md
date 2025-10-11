# stuttgart-things/flux/vcluster

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: vcluster
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/vcluster
  prune: true
  wait: true
  postBuild:
    substitute:
      VCLUSTER_VERSION: "0.29.1"
      VCLUSTER_NAMESPACE: vcluster
      VCLUSTER_STORAGE_ENABLED: "true"
      VCLUSTER_STORAGE_SIZE: 10Gi
      VCLUSTER_STORAGE_CLASS: longhorn
---
EOF
```
