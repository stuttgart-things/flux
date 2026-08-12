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
      OPENEBS_VERSION: 4.2.0
      VOLUMESNAPSHOTS_ENABLED: "false"
      CSI_NODE_INIT_CONTAINERS_ENABLED: "false"
      LOCAL_HOSTPATH_ENABLED: "true"
      LOCAL_LVM_ENABLED: "false"
      LOCAL_ZFS_ENABLED: "false"
      REPLICATED_MAYASTOR_ENABLED: "false"
      OPENEBS_LOKI_ENABLED: "false"
      OPENEBS_ALLOY_ENABLED: "false"
EOF
```

## Before raising `OPENEBS_VERSION`

The chart changed shape between 4.2 and 4.5, in two ways that are invisible from
the value list:

| | 4.2.0 | 4.5.x |
|---|---|---|
| `loki` / `alloy` | not dependencies at all | `loki 6.29.0` and `alloy 1.0.1`, **both default true** |
| `localpv-provisioner` | unconditional | `condition: engines.local.hostpath.enabled` |

So a bare version bump would deploy a Loki StatefulSet, the MinIO StatefulSet
backing it (MinIO is Loki's object store — a sub-dependency with no toggle of
its own), an Alloy DaemonSet and two extra StorageClasses. On a small cluster
Loki cannot even schedule: it wants three replicas with pod anti-affinity.

`release.yaml` therefore sets `loki.enabled`, `alloy.enabled` and
`engines.local.hostpath.enabled` explicitly, even though the first two are
no-ops at 4.2.0. The chart ships no `values.schema.json`, so the unknown keys
are accepted rather than rejected — verified against both versions.

One more asymmetry worth knowing: the `preUpgradeHook` image override above is
needed at 4.2.0, whose default is the **removed** `docker.io/bitnami/kubectl`.
4.5.x defaults to `docker.io/openebs/kubectl` and no longer needs it. The
override is harmless either way, since `alpine/kubectl` ships the shell the
hook's `command: ["/bin/sh","-c"]` requires.

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-openebs \
-o ./infra/ \
--filename-pattern "{{.name}}.yaml"
```

See also: [claims CLI](https://github.com/stuttgart-things/claims) | [claim-machinery-api](https://github.com/stuttgart-things/claim-machinery-api)
