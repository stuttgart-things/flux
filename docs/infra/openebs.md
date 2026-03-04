# OpenEBS

Container-attached storage with local hostpath provisioning.

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
  name: openebs
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/openebs
  prune: true
  wait: true
  postBuild:
    substitute:
      OPENEBS_NAMESPACE: openebs
      OPENEBS_VERSION: "4.2.0"
      VOLUMESNAPSHOTS_ENABLED: "false"
      CSI_NODE_INIT_CONTAINERS_ENABLED: "false"
      LOCAL_LVM_ENABLED: "false"
      LOCAL_ZFS_ENABLED: "false"
      REPLICATED_MAYASTOR_ENABLED: "false"
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `OPENEBS_NAMESPACE` | `openebs` | Target namespace |
| `OPENEBS_VERSION` | `4.2.0` | Helm chart version |
| `VOLUMESNAPSHOTS_ENABLED` | `false` | Enable volume snapshot support |
| `CSI_NODE_INIT_CONTAINERS_ENABLED` | `false` | Enable CSI node init containers |
| `LOCAL_LVM_ENABLED` | `false` | Enable Local LVM provisioner |
| `LOCAL_ZFS_ENABLED` | `false` | Enable Local ZFS provisioner |
| `REPLICATED_MAYASTOR_ENABLED` | `false` | Enable Mayastor replicated storage |

## Notes

- Uses HelmRepository from `https://openebs.github.io/openebs`
- Default configuration provides `openebs-hostpath` StorageClass only
- Enable additional engines (LVM, ZFS, Mayastor) as needed for your storage requirements
