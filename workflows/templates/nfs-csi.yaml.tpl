---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: nfs-csi
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/nfs-csi
  prune: true
  wait: true
  postBuild:
    substitute:
      NFS_SERVER_FQDN: 10.31.101.26
      NFS_SHARE_PATH: /data/col1/sthings
      CLUSTER_NAME: homerun-int
      NFS_CSI_NAMESPACE: kube-system
      NFS_CSI_VERSION: v4.9.0
      NFS_CSI_ENABLE_CRDS: "false"
      NFS_CSI_ENABLE_SNAPSHOTTER: "true"
