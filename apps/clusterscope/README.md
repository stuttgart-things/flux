# clusterscope — Flux App

Deploys [clusterscope](https://github.com/stuttgart-things/clusterscope) via Flux using the OCI Kustomize artifact from `ghcr.io/stuttgart-things/clusterscope-kustomize`.

## Directory structure

```
apps/clusterscope/
├── kustomization.yaml   # Kustomize entry point (includes release + httproute)
├── release.yaml         # OCIRepository + Kustomization with patches
├── httproute.yaml       # HTTPRoute (Gateway API, variable-substituted)
└── README.md
```

## Resources created

| Resource | Kind | Namespace |
|---|---|---|
| `clusterscope-kustomize` | OCIRepository | `flux-system` |
| `clusterscope` | Kustomization | `flux-system` |
| Namespace, ServiceAccount, ClusterRole(Binding), Service, Deployment | via OCI base | `clusterscope` |
| `clusterscope` | HTTPRoute | `clusterscope` |

## Register in clusters repo

Add to your cluster's `apps.yaml`:

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: clusterscope
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/clusterscope
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTERSCOPE_NAMESPACE: clusterscope
      CLUSTERSCOPE_VERSION: v0.6.0
      CLUSTERSCOPE_TECH: flux

      # git-sync sidecar
      GIT_SYNC_REPO: https://github.com/stuttgart-things/harvester
      GIT_SYNC_BRANCH: main
      GIT_SYNC_PERIOD: 60s
      GIT_SYNC_DIR: /data/harvester/clusters

      # HTTPRoute
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: clusterscope
      DOMAIN: example.com
```

## Substitution variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTERSCOPE_NAMESPACE` | `clusterscope` | Kubernetes namespace |
| `CLUSTERSCOPE_VERSION` | `v0.6.0` | OCI artifact tag |
| `CLUSTERSCOPE_TECH` | `flux` | GitOps tech: `flux` or `argocd` |
| `CLUSTERSCOPE_PORT` | `8080` | HTTP serve port |
| `GIT_SYNC_REPO` | *(required)* | Git repository URL to sync |
| `GIT_SYNC_BRANCH` | `main` | Branch/ref to sync |
| `GIT_SYNC_PERIOD` | `60s` | Sync interval |
| `GIT_SYNC_DIR` | `/data/repo/clusters` | Path inside synced repo with cluster dirs |
| `GIT_SYNC_IMAGE` | `registry.k8s.io/git-sync/git-sync:v4.4.0` | git-sync image |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `HOSTNAME` | `clusterscope` | Hostname prefix |
| `DOMAIN` | *(required)* | Domain → URL: `HOSTNAME.DOMAIN` |

## How it works

```
Flux watches OCIRepository (ghcr.io/stuttgart-things/clusterscope-kustomize:VERSION)
  └── Kustomization applies OCI base with patches:
        1. Override container args: -root=GIT_SYNC_DIR -tech=TECH -serve=:PORT
        2. Add git-sync sidecar (shares emptyDir /data with clusterscope)
        3. Delete KCL-generated HTTPRoute (replaced by httproute.yaml)
  └── HTTPRoute created separately via httproute.yaml (variable-substituted)
```

### git-sync volume layout

```
pod (namespace: clusterscope)
├── container: clusterscope  (-root=/data/<repo>/clusters -tech=flux -serve=:8080)
│   └── volumeMount: gitdata → /data
└── container: git-sync      (--repo=GIT_SYNC_REPO --ref=GIT_SYNC_BRANCH --root=/data)
    └── volumeMount: gitdata → /data

/data/
└── <repo-name> → .worktrees/<hash>   (symlink created by git-sync)
    └── clusters/
        ├── infra/
        ├── platform/
        └── xplane/
```

Set `GIT_SYNC_DIR=/data/<repo-name>/clusters` to point clusterscope at the right directory.
