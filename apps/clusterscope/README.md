# clusterscope — Flux App

Deploys [clusterscope](https://github.com/stuttgart-things/clusterscope) via Flux using the OCI Kustomize artifact from `ghcr.io/stuttgart-things/clusterscope-kustomize`.

## Directory structure

```
apps/clusterscope/
├── kustomization.yaml   # Kustomize entry point (includes release + httproute)
├── release.yaml         # OCIRepository + Kustomization with patches
├── httproute.yaml       # HTTPRoute (Gateway API, variable-substituted)
├── components/
│   ├── vault-kubeconfigs/  # opt-in: kubeconfigs of the lab's clusters from Vault (live mode)
│   └── vault-git-auth/     # opt-in: git-sync credentials from Vault (private repos)
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
      CLUSTERSCOPE_VERSION: v0.23.1
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

## Lab view with live mode (example: LabUL on platform-sthings)

clusterscope reads its own cluster in-cluster and the other clusters of the lab
with kubeconfigs from Vault; the repo is private, so git-sync gets a token
from Vault too.

```yaml
spec:
  path: ./apps/clusterscope
  components:
    - components/vault-kubeconfigs
    - components/vault-git-auth
  postBuild:
    substitute:
      CLUSTERSCOPE_VERSION: v0.23.1
      CLUSTERSCOPE_LAB: labul
      CLUSTERSCOPE_LIVE: "true"
      CLUSTERSCOPE_PROBE: "true"
      CLUSTERSCOPE_SELF_CLUSTER: platform-sthings
      CLUSTERSCOPE_KUBECONFIG_DIR: /kubeconfigs
      CLUSTERSCOPE_KUBECONFIG_STORE: vault-kubeconfigs
      CLUSTERSCOPE_KUBECONFIG_CLUSTERS: ^(infra-sthings|homerun2-dev2)$
      GIT_SYNC_REPO: https://github.com/stuttgart-things/stuttgart-things  # no ".git": the link is named after it
      GIT_SYNC_DIR: /data/stuttgart-things/clusters/labul
      GIT_SYNC_AUTH_STORE: vault-homerun2-cd
      GIT_SYNC_AUTH_PATH: homerun2-cd/data/kargo
      GIT_SYNC_AUTH_USERNAME_PROPERTY: gitUsername
      GIT_SYNC_AUTH_PASSWORD_PROPERTY: gitToken
```

`components/vault-kubeconfigs` selects the Vault entries (KV v2, path = cluster
name, property `kubeconfig`) by the regexp in `CLUSTERSCOPE_KUBECONFIG_CLUSTERS`
and writes them as one Secret with one key per cluster, mounted at
`/kubeconfigs`. Both Secrets are optional for the pod: it starts without them
and picks them up once ESO has synced.

Until git-sync has cloned the repo, `-root` does not exist and clusterscope
restarts a few times; it settles after the first sync.

## Substitution variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTERSCOPE_NAMESPACE` | `clusterscope` | Kubernetes namespace |
| `CLUSTERSCOPE_VERSION` | `v0.23.1` | OCI artifact tag (from v0.23.1 on, the base pins the image of the same version) |
| `CLUSTERSCOPE_TECH` | `flux` | GitOps tech: `flux` or `argocd` |
| `CLUSTERSCOPE_PORT` | `8080` | HTTP serve port |
| `CLUSTERSCOPE_LAB` | — | Lab name when the path has no `clusters/<lab>/…` |
| `CLUSTERSCOPE_LIVE` | `false` | Live mode: GitOps status, workload health, endpoints |
| `CLUSTERSCOPE_SELF_CLUSTER` | — | Cluster clusterscope runs in (read in-cluster) |
| `CLUSTERSCOPE_KUBECONFIG_DIR` | — | `/kubeconfigs` with `components/vault-kubeconfigs` |
| `CLUSTERSCOPE_PROBE` | `false` | Probe every HTTPRoute URL on each refresh |
| `CLUSTERSCOPE_REFRESH` | `60` | Live refresh interval (seconds) |
| `CLUSTERSCOPE_KUBECONFIG_CLUSTERS` | `^$` (none) | vault-kubeconfigs: regexp over Vault entry names |
| `CLUSTERSCOPE_KUBECONFIG_STORE` | `vault-kubeconfigs` | vault-kubeconfigs: ClusterSecretStore |
| `CLUSTERSCOPE_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | trust-manager CA bundle for the endpoint probes (optional) |
| `CLUSTERSCOPE_TRUST_BUNDLE_KEY` | `trust-bundle.pem` | key in that ConfigMap |
| `CLUSTERSCOPE_ESO_REFRESH_INTERVAL` | `1h` | ExternalSecret refresh |
| `GIT_SYNC_AUTH_SECRET` | `git-sync-auth` | Secret with username/password for git-sync (optional) |
| `GIT_SYNC_AUTH_STORE` | *(required for vault-git-auth)* | vault-git-auth: ClusterSecretStore |
| `GIT_SYNC_AUTH_PATH` | *(required for vault-git-auth)* | vault-git-auth: Vault key |
| `GIT_SYNC_AUTH_USERNAME_PROPERTY` | `username` | vault-git-auth: property |
| `GIT_SYNC_AUTH_PASSWORD_PROPERTY` | `password` | vault-git-auth: property |
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
        1. Override container args: -root=GIT_SYNC_DIR -tech=TECH -serve=:PORT -lab -live -probe …
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
