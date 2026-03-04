# NFS CSI Driver

NFS CSI driver with automatic StorageClass provisioning.

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
      NFS_CSI_NAMESPACE: kube-system
      NFS_CSI_VERSION: v4.13.1
      NFS_CSI_ENABLE_CRDS: "false"
      NFS_CSI_ENABLE_SNAPSHOTTER: "true"
      NFS_SERVER_FQDN: "10.31.101.26"
      NFS_SHARE_PATH: /data/col1/sthings
      CLUSTER_NAME: my-cluster
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `NFS_CSI_NAMESPACE` | `kube-system` | Target namespace |
| `NFS_CSI_VERSION` | `v4.13.1` | Helm chart version |
| `NFS_CSI_ENABLE_SNAPSHOTTER` | `true` | Enable volume snapshotter |
| `NFS_CSI_ENABLE_CRDS` | `false` | Install snapshot CRDs |
| `NFS_SERVER_FQDN` | *(required)* | NFS server hostname or IP |
| `NFS_SHARE_PATH` | *(required)* | NFS export path |
| `CLUSTER_NAME` | `DOWNSTREAM` | Cluster name (used in share subdirectory) |

## Testing

After deployment, verify the StorageClasses:

```bash
kubectl get sc | grep nfs
# Expected: nfs3-csi and nfs4-csi
```

Create a test PVC:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-nfs-pvc
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: nfs4-csi
  resources:
    requests:
      storage: 1Gi
EOF

kubectl get pvc test-nfs-pvc
# STATUS should be: Bound
```

## Notes

- Uses HelmRepository from `https://raw.githubusercontent.com/kubernetes-csi/csi-driver-nfs/master/charts`
- Includes `post-release.yaml` that creates `nfs3-csi` and `nfs4-csi` StorageClasses via the `sthings-cluster` helper chart
- The `nfs-csi-configuration` HelmRelease depends on `nfs-csi`
