# stuttgart-things/flux/infra/nfs-csi

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
    tag: v1.0.0
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
      NFS_CSI_VERSION: v4.13.1
      NFS_CSI_ENABLE_CRDS: "false"
      NFS_CSI_ENABLE_SNAPSHOTTER: "true"
EOF
```

## TESTING

After deploying, verify the NFS CSI StorageClasses are available and functional:

```bash
# 1. Check StorageClasses were created
kubectl get sc | grep nfs

# Expected output:
# nfs3-csi   nfs.csi.k8s.io   Delete   Immediate   false
# nfs4-csi   nfs.csi.k8s.io   Delete   Immediate   false
```

```bash
# 2. Create a test PVC and pod
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-nfs-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: nfs4-csi
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-nfs
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-nfs
  template:
    metadata:
      labels:
        app: test-nfs
    spec:
      containers:
        - name: busybox
          image: busybox:1.36
          command: ["sh", "-c", "echo 'NFS works!' > /data/testfile.txt && cat /data/testfile.txt && sleep 3600"]
          volumeMounts:
            - name: nfs-vol
              mountPath: /data
      volumes:
        - name: nfs-vol
          persistentVolumeClaim:
            claimName: test-nfs-pvc
EOF
```

```bash
# 3. Verify PVC is bound
kubectl get pvc test-nfs-pvc
# STATUS should be: Bound

# 4. Verify pod can write to NFS
kubectl exec deploy/test-nfs -- cat /data/testfile.txt
# Expected output: NFS works!

# 5. Optionally verify on the NFS server
ssh <nfs-server> "ls -la <NFS_SHARE_PATH>/<CLUSTER_NAME>/"
```

```bash
# 6. Cleanup
kubectl delete deployment test-nfs
kubectl delete pvc test-nfs-pvc
```

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-nfs-csi \
-p nfsServerFqdn=10.31.101.26 \
-p nfsSharePath=/data/col1/sthings \
-p nfsCsiClusterName=my-cluster \
-o ./infra/ \
--filename-pattern "{{.name}}.yaml"
```
