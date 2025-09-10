# stuttgart-things/flux/infra/openebs

## REQUIREMENTS

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-infra
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    branch: main
  url: https://github.com/stuttgart-things/flux.git
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
  name: openebs
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/openebs
  prune: true
  wait: true
  postBuild:
    substitute:
      VERSION: 4.2.
      VOLUMESNAPSHOTS_ENABLED: false
      CSI_NODE_INIT_CONTAINERS_ENABLED: false
      LOCAL_LVM_ENABLED: false
      LOCAL_ZFS_ENABLED: false
      REPLICATED_MAYASTOR_ENABLED: false
EOF
```
