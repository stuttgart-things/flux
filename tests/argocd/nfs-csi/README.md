# nfs-csi on Argo CD

ArgoCD equivalent of [`infra/nfs-csi`](../../../infra/nfs-csi) (Flux). Splits
the Helm install of `csi-driver-nfs` and the `StorageClass` definitions into two
`Application`s (App-of-Apps), with a per-cluster `ApplicationSet` for fan-out.

## Layout

```
tests/argocd/nfs-csi/
├── apps/
│   ├── nfs-csi.yaml               # Helm chart (sync-wave -10)
│   └── nfs-csi-storageclasses.yaml# StorageClasses (wave 10)
├── manifests/
│   └── storageclasses/            # nfs3-csi + nfs4-csi StorageClasses
├── clusters/
│   └── example/
│       ├── cluster.yaml           # per-cluster params (NFS server / share)
│       └── values.yaml            # csi-driver-nfs Helm values
├── root-app.yaml                  # (Option A) static App-of-Apps root
└── appset.yaml                    # (Option B) ApplicationSets, per-cluster fan-out
```

## Mapping from Flux

| Flux                                          | ArgoCD                                                |
|-----------------------------------------------|-------------------------------------------------------|
| `requirements.yaml` (`HelmRepository`s)       | Argo CD's built-in Helm source (chart URL inline)     |
| `release.yaml` (HelmRelease, `csi-driver-nfs`)| `apps/nfs-csi.yaml`                                   |
| `post-release.yaml` (sthings-cluster `scs`)   | `apps/nfs-csi-storageclasses.yaml` + `manifests/storageclasses/` (plain `StorageClass`) |
| `dependsOn`                                   | `argocd.argoproj.io/sync-wave`                        |
| `${NFS_SERVER_FQDN}`, `${NFS_SHARE_PATH}`, `${CLUSTER_NAME}` | ApplicationSet `kustomize.patches` driven by `cluster.yaml` |

The StorageClasses are written directly here (instead of going through the
`sthings-cluster` Helm chart) — they're plain k8s objects, easier to read and
patch in tests.

## Deployment — Option A: static App-of-Apps

```bash
kubectl apply -f root-app.yaml
```

Applies both child Applications using the placeholder NFS server in
`manifests/storageclasses/` (`nfs.example.com`, `/exports`). For real use go
with Option B.

## Deployment — Option B: ApplicationSet (multi-cluster)

1. Add a directory under `clusters/` with `cluster.yaml` + `values.yaml`. The
   ApplicationSet will substitute `nfs.server`, `nfs.share`, and `nfs.subDir`
   into the StorageClass parameters per cluster.
2. Apply:

   ```bash
   kubectl apply -f appset.yaml
   ```

### `cluster.yaml` schema

```yaml
cluster:
  name: <short name used in Application names>
  server: <Kubernetes API URL or in-cluster URL>
nfsCsi:
  chartVersion: <Helm chart version, e.g. v4.13.1>
  namespace: <install namespace, typically kube-system>
nfs:
  server:  <NFS server FQDN or IP>
  share:   <exported path on the server>
  subDir:  <sub-directory used by the nfs3-csi StorageClass; usually $CLUSTER_NAME>
```

## Prerequisites

- Argo CD installed in the `argocd` namespace.
- The target nodes must have the `nfs-common` (or distro equivalent) package
  so they can mount NFS volumes — handle outside Argo CD.
- The NFS server must export `nfs.share` and allow the cluster nodes' IPs.
