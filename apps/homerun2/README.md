# stuttgart-things/flux/homerun2

## On a bundle cluster (apps/platform)

Selected like any other app component. The **Components** column is the
`spec.components` list each one carries; credentials follow `HOMERUN2_SECRETS`
(below), so the same table serves an ESO cluster and a SOPS one.

| Bundle component | Components | What it deploys |
|---|---|---|
| `homerun2` | redis-stack, then omni-pitcher + core-catcher + scout + led-catcher | the namespace and redis-stack (`homerun2-redis`), then the apps once redis answers |
| `homerun2-demo-pitcher` | demo-pitcher | demo-pitcher (waits on `homerun2`) |
| `homerun2-light-catcher` | light-catcher + wled-mock | light-catcher and wled-mock (waits on `homerun2`) |
| `homerun2-config-viewer` | config-viewer | config-viewer: which alert triggers what in which catcher, read from the namespace through the Kubernetes API -- no credentials (waits on `homerun2`) |
| `homerun2-light-catcher-tabletennis` | light-catcher-tabletennis | a second light-catcher, for the table tennis table, on the `tabletennis` stream in namespace `homerun2-tabletennis` (waits on `homerun2`) |
| `homerun2-notification-catcher` | notification-catcher | forwards what it catches to the outputs it is configured with (Teams). Installed in its own DRY_RUN default: it logs `would have sent` and posts nowhere until a cluster runs it from a Kustomization of its own (waits on `homerun2`) |
| `homerun2-smoke-test` | `smoke-test` | a Job: omni-pitcher health, 401 without token, 2xx with it, one probe per component, in-cluster and through the gateway. Runs again when the Job spec changes, which includes any component version (they land in the pod template as `homerun2.stuttgart-things.com/tested-versions`); the `Completed` pod stays on purpose -- with a TTL, Flux would recreate the deleted Job and re-run it every interval |

A cluster sets `HOMERUN2_REDIS_STORAGE_CLASS`, which defaults to a sentinel, and
picks a credential mode.

**`HOMERUN2_SECRETS` is the switch.** Every component's list in the bundle names
its credential directory through it, so `eso` (the default — a
`ClusterSecretStore`, `HOMERUN2_SECRET_STORE` required) and `sops` (plain
Secrets from a `substituteFrom` Secret the cluster repository carries,
SOPS-encrypted) are the same bundle with one line changed. The sops path needs
three more lines, and they are listed together in
[apps/platform/README.md](../platform/README.md#homerun2-eso-or-sops-one-line)
because forgetting `HOMERUN2_SECRETS_FROM_OPTIONAL: "false"` installs a redis
with no password that reports Ready.

**Redis comes first.** `homerun2` waits for `homerun2-redis`. omni-pitcher gives redis 30s at start and core-catcher does not retry at all, while a fresh redis-stack takes ~70s to answer -- applied together, the two restarted 2 and 4 times on labda-dev-a's first install.

**Routes come last.** Each of the first three brings a second Kustomization, `<name>-routes`, that applies the HTTPRoutes (`components/<c>/route`) only once the app Kustomization is Ready. Cilium resolves a route's backends once; a route applied before its Service serves HTTP 500 for good while everything reports Ready. `profiles/base` has the same split: its routes are in `profiles/base-routes`. Only the root still applies them inline.

**Credentials.** Every component's child Kustomization deletes the placeholder Secrets its base ships. The real ones come from `components/<c>/eso` (ExternalSecrets) or `components/<c>/sops` (plain Secrets from `substituteFrom`) — both exist for every component that reads one, and which is selected is a line in the component list, not a property of the profile you picked. The entry is `${HOMERUN2_SECRET_PATH}` (`redis-password`, `scout-auth-token`); the omni-pitcher token is read from `${HOMERUN2_OMNI_PITCHER_TOKEN_PATH}` / `..._PROPERTY`, so a cluster can share it with a client that already holds it.

**zaehlwerk.** tabletennis clusters with `TABLETENNIS_ZAEHLWERK_PANEL: homerun2` point zaehlwerk at omni-pitcher and the led-catcher in the same cluster; omni-pitcher routes `system: tabletennis` onto the `tabletennis` stream.

**A light at the table.** `homerun2-light-catcher-tabletennis` reads that stream with a profile of its own: a one-second flash in side a's or side b's colour per point, Rainbow on a set, Fireworks on the match. The rules match on the tags zaehlwerk v0.3.0+ sends (`transition=`, `side=`), which needs light-catcher v1.1.0+. It is a second instance in its own namespace rather than a second stream on `homerun2-light-catcher`, whose wildcard rules would fire on every point -- see `components/light-catcher-tabletennis`. It drives the homerun2 wled-mock until `HOMERUN2_LIGHT_CATCHER_TABLETENNIS_WLED_ENDPOINT` names a strip.

Homerun2 application stack using Kustomize Components pattern. Deploys Redis Stack + homerun2 microservices into a shared namespace.

## Components

| Component | Type | Description |
|-----------|------|-------------|
| `redis-stack` | HelmRelease | Redis Stack with Sentinel (integral dependency) |
| `omni-pitcher` | OCIRepository + Flux Kustomization | HTTP gateway for Redis Stream ingestion |
| `core-catcher` | OCIRepository + Flux Kustomization | Redis Streams consumer with web dashboard |
| `k8s-pitcher` | OCIRepository + Flux Kustomization | K8s cluster watcher (informers + collectors) |
| `scout` | OCIRepository + Flux Kustomization | Scout service with web dashboard |
| `light-catcher` | OCIRepository + Flux Kustomization | Redis Streams consumer triggering WLED light effects |
| `light-catcher-tabletennis` | OCIRepository + Flux Kustomization | A second light-catcher on zaehlwerk's `tabletennis` stream, in its own namespace |
| `wled-mock` | OCIRepository + Flux Kustomization | WLED mock server with dashboard (for dev/testing) |
| `demo-pitcher` | OCIRepository + Flux Kustomization | Web UI for manually pitching demo messages to Redis Streams |
| `led-catcher` | OCIRepository + Flux Kustomization | Redis Streams consumer for LED display output |
| `git-pitcher` | OCIRepository + Flux Kustomization | Watches Git repositories and pitches events to Redis Streams |
| `notification-catcher` | OCIRepository + Flux Kustomization | Redis Streams consumer that forwards messages as notifications |
| `config-viewer` | OCIRepository + Flux Kustomization | Read-only view of which alert triggers what in which catcher (reads the Kubernetes API, not Redis) |

## Selecting components

`path: ./apps/homerun2/root` plus `spec.components` on your own Flux
Kustomization. The root is an empty kustomization; the list is what deploys.

```yaml
spec:
  path: ./apps/homerun2/root
  components:
    - ../components/redis-stack
    - ../components/redis-stack/sops
    - ../components/omni-pitcher
    - ../components/omni-pitcher/sops
    - ../components/core-catcher
    - ../components/core-catcher/sops
    - ../components/notification-catcher
    - ../components/notification-catcher/sops
```

Two entries per component that reads a credential: the workload, then the
credential mode. Both modes exist for every one of them —

| Entry | What it adds |
|---|---|
| `../components/<c>` | the workload: an OCIRepository and a child Flux Kustomization |
| `../components/<c>/eso` | its credentials as ExternalSecrets from a `ClusterSecretStore` |
| `../components/<c>/sops` | its credentials as plain Secrets, filled from `postBuild.substituteFrom` |
| `../components/<c>/route` | its HTTPRoute — **a second Kustomization**, see below |

— so neither mode is the default and neither is a privileged path. Components
that read no credential (`wled-mock`, `config-viewer`, `git-pitcher`,
`k8s-pitcher`) have neither directory and are one line.

Write the mode as `../components/<c>/${HOMERUN2_SECRETS:-eso}` to make it a
variable instead; that is what the apps-platform bundle does, where the list is
upstream and the cluster only sets `HOMERUN2_SECRETS`.

### Routes go in a second Kustomization

Cilium resolves an HTTPRoute's backendRefs once. The Services here are created
by child Kustomizations seconds after the parent applies, and a route that got
there first serves HTTP 500 for good while every Kustomization reports Ready
(labda-dev-a, 2026-09-10, three of seven). So the `route` components belong to
a Kustomization that `dependsOn` the stack one **and** the Gateway's:

```yaml
spec:
  dependsOn:
    - name: homerun2
    - name: cilium-gateway
  path: ./apps/homerun2/root
  components:
    - ../components/omni-pitcher/route
    - ../components/core-catcher/route
```

### Why there are (almost) no profiles left

`spec.path` has to name a directory kustomize can build, and a `kind: Component`
directory is not one — so every combination a cluster wanted needed a
`profiles/` directory of its own, and because the credential mode is a component
too, the set was the cross product of components x `eso|sops` x
with/without routes. `base-led-catcher`, `base-light-catcher` and
`base-demo-pitcher` were three such directories, added one upstream pull
request at a time (#479, #481, #482), each because a cluster on the sops path
wanted one more component that existed only in an eso profile. With `root/`
that cross product is a list, and adding a component to a cluster is a line in
it rather than a pull request here.

Three presets remain, for consumers that already point at them:

| Profile | Components | Use case |
|---------|------------|----------|
| `profiles/base` | redis-stack, omni-pitcher, core-catcher, notification-catcher, scout — all `sops` | Minimal deployment: message ingestion + web dashboard + notifications + monitoring |
| `profiles/base-routes` | HTTPRoutes for omni-pitcher, core-catcher, scout | **Add-on** to `profiles/base`: a second Kustomization with `dependsOn` on the base one |
| `profiles/cicd` | git-pitcher | **Add-on**, not standalone: deploy *alongside* `profiles/base` as a second Kustomization |
| *(root `kustomization.yaml`)* | 11 of the 13 components, `sops`, routes inline | Full stack in one Kustomization |

`profiles/cicd` composes only `git-pitcher`, and that is deliberate. It is
consumed as its own Flux Kustomization next to a `profiles/base` one (see
`clusters/labul/vsphere/platform-sthings/apps/homerun2-cicd-stack.yaml`), so it
needs neither the redis/gateway variables nor a second copy of the core stack —
which would fight the base profile over the same objects.

Note the top-level `kustomization.yaml` does **not** include
`notification-catcher`; `profiles/base` and an explicit list do.

### Checked, not assumed

`hack/check-component-lists.py` builds every `spec.components` list in this
repository, **in both credential modes**. kustomize never sees those entries —
only Flux expands them, on a cluster — so a typo or a component that grew an
`eso/` and never got a `sops/` would otherwise surface at deploy time. It runs
in CI and as `task check-components`.

## SUBSTITUTION VARIABLES

Version defaults are not repeated in these tables. Each component pins them in `components/<name>/requirements.yaml` (the kustomize OCI tag) and `release.yaml` (the image tag), bundle copies sit in `apps/platform/components/homerun2*/ks-*.yaml`, and renovate bumps all of them in one `fix(deps)` PR per component. A version column here was one more copy that nothing updated.

### Global

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_NAMESPACE` | `homerun2` | no | Shared namespace for all components |
| `GATEWAY_NAME` | - | yes | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | no | Gateway parentRef namespace |
| `DOMAIN` | - | yes | HTTPRoute domain suffix |
| `FLUX_SOURCE_API_VERSION` | `v1` | no | OCIRepository API version (`v1` or `v1beta2`) |

### Redis Stack

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_REDIS_PASSWORD` | - | yes | Redis password (use substituteFrom Secret) |
| `HOMERUN2_REDIS_PASSWORD_B64` | - | yes | Base64-encoded Redis password (for patching KCL secrets) |
| `HOMERUN2_REDIS_VERSION` | `17.1.4` | no | Helm chart version |
| `HOMERUN2_REDIS_SERVICE_TYPE` | `ClusterIP` | no | Redis service type |
| `HOMERUN2_REDIS_PERSISTENCE_ENABLED` | `true` | no | Enable persistence |
| `HOMERUN2_REDIS_STORAGE_CLASS` | `standard` | no | Storage class |
| `HOMERUN2_REDIS_STORAGE_SIZE` | `8Gi` | no | PVC size |
| `HOMERUN2_REDIS_IMAGE_REGISTRY` | `ghcr.io` | no | Redis image registry |
| `HOMERUN2_REDIS_IMAGE_REPOSITORY` | `stuttgart-things/redis-stack-server` | no | Redis image repository |
| `HOMERUN2_REDIS_IMAGE_VERSION` | `7.2.0-v18` | no | Redis image tag |
| `HOMERUN2_REDIS_SENTINEL_REGISTRY` | `ghcr.io` | no | Sentinel image registry |
| `HOMERUN2_REDIS_SENTINEL_REPOSITORY` | `stuttgart-things/redis-sentinel` | no | Sentinel image repository |
| `HOMERUN2_REDIS_SENTINEL_VERSION` | `7.4.2-debian-12-r9` | no | Sentinel image tag |

### Omni Pitcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_OMNI_PITCHER_VERSION` | see `requirements.yaml` | no | OCI kustomize base + container image tag |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | `changeme` | no | Bearer auth token for the `/pitch` endpoint (use substituteFrom Secret) |

### Core Catcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_CORE_CATCHER_VERSION` | see `release.yaml` | no | Container image tag |
| `HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION` | see `requirements.yaml` | no | OCI kustomize base tag (use `-web` suffix for web mode) |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### K8s Pitcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_K8S_PITCHER_VERSION` | see `requirements.yaml` | no | OCI kustomize base + container image tag |
| `HOMERUN2_K8S_PITCHER_NAMESPACE` | `homerun2-flux` | no | Namespace (can differ from shared namespace) |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | `changeme` | no | Bearer auth token (shared with omni-pitcher, from substituteFrom Secret) |
| `HOMERUN2_K8S_PITCHER_TRUST_BUNDLE_CM` | `cluster-trust-bundle` | no | ConfigMap name with CA bundle for TLS trust |
| `HOMERUN2_K8S_PITCHER_PROFILE_CM` | `homerun2-k8s-pitcher-profile` | no | ConfigMap name containing the K8sPitcherProfile YAML |

### Light Catcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_LIGHT_CATCHER_KUSTOMIZE_VERSION` | see `requirements.yaml` | no | OCI kustomize base tag |
| `HOMERUN2_LIGHT_CATCHER_VERSION` | see `release.yaml` | no | Container image tag |
| `HOMERUN2_LIGHT_CATCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### Light Catcher (tabletennis)

Shares the version variables above.

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_LIGHT_CATCHER_TABLETENNIS_NAMESPACE` | `homerun2-tabletennis` | no | Namespace of this instance |
| `HOMERUN2_LIGHT_CATCHER_TABLETENNIS_WLED_ENDPOINT` | `http://homerun2-wled-mock.homerun2.svc.cluster.local` | no | The WLED device at the table |
| `HOMERUN2_LIGHT_CATCHER_TABLETENNIS_HOSTNAME` | `light-catcher-tabletennis` | no | HTTPRoute hostname prefix |

### WLED Mock

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_WLED_MOCK_VERSION` | see `requirements.yaml` | no | OCI kustomize base + container image tag |
| `HOMERUN2_WLED_MOCK_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### Demo Pitcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_DEMO_PITCHER_VERSION` | see `requirements.yaml` | no | OCI kustomize base + container image tag |
| `HOMERUN2_DEMO_PITCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### LED Catcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_LED_CATCHER_VERSION` | see `requirements.yaml` | no | OCI kustomize base + container image tag |
| `HOMERUN2_LED_CATCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### Git Pitcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_GIT_PITCHER_VERSION` | see `requirements.yaml` | no | OCI kustomize base + container image tag |

### Config Viewer

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_CONFIG_VIEWER_KUSTOMIZE_VERSION` | see `requirements.yaml` | no | OCI kustomize base tag |
| `HOMERUN2_CONFIG_VIEWER_VERSION` | see `release.yaml` | no | Container image tag |
| `HOMERUN2_CONFIG_VIEWER_HOSTNAME` | `config-viewer` | no | HTTPRoute hostname prefix |

### Scout

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_SCOUT_KUSTOMIZE_VERSION` | see `requirements.yaml` | no | OCI kustomize base tag |
| `HOMERUN2_SCOUT_VERSION` | see `release.yaml` | no | Container image tag |
| `HOMERUN2_SCOUT_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

The WLED mock provides a dashboard simulating a WLED device. Use it during development/testing instead of a real WLED device. The light-catcher's profile should point its endpoints to `homerun2-wled-mock.NAMESPACE.svc.cluster.local`.

The k8s-pitcher component **deletes** the KCL-generated profile ConfigMap. The calling side must provide its own profile ConfigMap with cluster-specific configuration (pitcher address, collectors, informers). For CRD watching, add the CRD API group to the ClusterRole on the calling side.

## SECRETS MANIFEST (SOPS ENCRYPTED)

Create a plaintext secret file (e.g., `homerun2-flux-secrets.yaml`):

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: homerun2-flux-secrets
  namespace: flux-system
type: Opaque
stringData:
  HOMERUN2_REDIS_PASSWORD: "your-secure-password" #pragma: allowlist secret
  HOMERUN2_REDIS_PASSWORD_B64: "<base64-encoded-password>" #pragma: allowlist secret
  HOMERUN2_OMNI_PITCHER_AUTH_TOKEN: "your-auth-token" #pragma: allowlist secret
```

Generate the base64 value:

```bash
echo -n 'your-secure-password' | base64
```

Encrypt with SOPS using age (via local sops):

```bash
sops --encrypt \
  --age <AGE_PUBLIC_KEY> \
  --encrypted-regex '^(data|stringData)$' \
  --input-type yaml --output-type yaml \
  homerun2-flux-secrets.yaml > homerun2-flux-secrets.enc.yaml \
  && mv homerun2-flux-secrets.enc.yaml homerun2-flux-secrets.yaml
```

Or encrypt via Dagger:

```bash
# encrypt
dagger call -m github.com/stuttgart-things/dagger/sops@v0.82.1 encrypt \
  --age-key env:AGE_PUB \
  --plaintext-file homerun2-flux-secrets.yaml \
  --file-extension yaml \
  export --path=homerun2-flux-secrets.yaml

# decrypt (for verification)
dagger call -m github.com/stuttgart-things/dagger/sops@v0.82.1 decrypt \
  --age-key env:SOPS_AGE_KEY \
  --encrypted-file homerun2-flux-secrets.yaml \
  export --path=/tmp/homerun2-flux-secrets.decrypted.yaml
```

Commit the encrypted file to the cluster repo. Flux will decrypt it at reconciliation time using the `sops-age` secret.

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: main
EOF
```

## KUSTOMIZATION EXAMPLE

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun2-flux
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/homerun2
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN2_NAMESPACE: homerun2-flux
      FLUX_SOURCE_API_VERSION: v1beta2
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: my-cluster.example.com
      HOMERUN2_OMNI_PITCHER_VERSION: v1.2.0
      HOMERUN2_OMNI_PITCHER_HOSTNAME: pitcher
      HOMERUN2_CORE_CATCHER_VERSION: v0.5.0
      HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION: v0.5.0-web
      HOMERUN2_CORE_CATCHER_HOSTNAME: catcher
      # K8s Pitcher
      HOMERUN2_K8S_PITCHER_VERSION: v0.4.0
      HOMERUN2_K8S_PITCHER_NAMESPACE: homerun2-flux
      HOMERUN2_K8S_PITCHER_PROFILE_CM: homerun2-k8s-pitcher-profile
      # Light Catcher + WLED Mock
      HOMERUN2_LIGHT_CATCHER_VERSION: v0.3.0
      HOMERUN2_LIGHT_CATCHER_HOSTNAME: light-catcher
      HOMERUN2_WLED_MOCK_VERSION: v0.3.0
      HOMERUN2_WLED_MOCK_HOSTNAME: wled-mock
      # Demo Pitcher
      HOMERUN2_DEMO_PITCHER_VERSION: v1.4.0
      HOMERUN2_DEMO_PITCHER_HOSTNAME: demo-pitcher
      # Redis Stack
      HOMERUN2_REDIS_VERSION: "17.1.4"
      HOMERUN2_REDIS_SERVICE_TYPE: ClusterIP
      HOMERUN2_REDIS_PERSISTENCE_ENABLED: "true"
      HOMERUN2_REDIS_STORAGE_CLASS: nfs4-csi
      HOMERUN2_REDIS_STORAGE_SIZE: 8Gi
    substituteFrom:
      - kind: Secret
        name: homerun2-flux-secrets
```

## COMPLETE EXAMPLE: MOVIE-SCRIPTS CLUSTER

Full deployment of the homerun2 stack on the `movie-scripts` cluster:

**Cluster config** (`clusters/labul/vsphere/movie-scripts/homerun2-flux.yaml`):

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun2-flux
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/homerun2
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN2_NAMESPACE: homerun2-flux
      FLUX_SOURCE_API_VERSION: v1beta2
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
      HOMERUN2_OMNI_PITCHER_VERSION: v1.2.0
      HOMERUN2_OMNI_PITCHER_HOSTNAME: pitcher
      HOMERUN2_CORE_CATCHER_VERSION: v0.5.0
      HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION: v0.5.0-web
      HOMERUN2_CORE_CATCHER_HOSTNAME: catcher
      # K8s Pitcher
      HOMERUN2_K8S_PITCHER_VERSION: v0.4.0
      HOMERUN2_K8S_PITCHER_NAMESPACE: homerun2-flux
      HOMERUN2_K8S_PITCHER_PROFILE_CM: homerun2-k8s-pitcher-profile
      # Light Catcher + WLED Mock
      HOMERUN2_LIGHT_CATCHER_VERSION: v0.3.0
      HOMERUN2_LIGHT_CATCHER_HOSTNAME: light-catcher
      HOMERUN2_WLED_MOCK_VERSION: v0.3.0
      HOMERUN2_WLED_MOCK_HOSTNAME: wled-mock
      # Demo Pitcher
      HOMERUN2_DEMO_PITCHER_VERSION: v1.4.0
      HOMERUN2_DEMO_PITCHER_HOSTNAME: demo-pitcher
      # Redis Stack
      HOMERUN2_REDIS_VERSION: "17.1.4"
      HOMERUN2_REDIS_SERVICE_TYPE: ClusterIP
      HOMERUN2_REDIS_PERSISTENCE_ENABLED: "true"
      HOMERUN2_REDIS_STORAGE_CLASS: nfs4-csi
      HOMERUN2_REDIS_STORAGE_SIZE: 8Gi
      HOMERUN2_REDIS_IMAGE_REGISTRY: ghcr.io
      HOMERUN2_REDIS_IMAGE_REPOSITORY: stuttgart-things/redis-stack-server
      HOMERUN2_REDIS_IMAGE_VERSION: 7.2.0-v18
      HOMERUN2_REDIS_SENTINEL_REGISTRY: ghcr.io
      HOMERUN2_REDIS_SENTINEL_REPOSITORY: stuttgart-things/redis-sentinel
      HOMERUN2_REDIS_SENTINEL_VERSION: 7.4.2-debian-12-r9
    substituteFrom:
      - kind: Secret
        name: homerun2-flux-secrets
```

**K8s Pitcher profile ConfigMap** (calling side defines this separately):

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: homerun2-k8s-pitcher-profile
  namespace: homerun2-flux
data:
  profile.yaml: |
    apiVersion: homerun2.sthings.io/v1alpha1
    kind: K8sPitcherProfile
    metadata:
      name: movie-scripts
    spec:
      pitcher:
        addr: https://pitcher.movie-scripts2.sthings-vsphere.labul.sva.de/pitch
        insecure: false
      auth:
        tokenFrom:
          secretKeyRef:
            name: homerun2-k8s-pitcher-token
            namespace: homerun2-flux
            key: auth-token
      collectors:
        - kind: Node
          interval: 60s
        - kind: Pod
          namespace: "*"
          interval: 30s
        - kind: Event
          namespace: "*"
          interval: 15s
      informers:
        - group: ""
          version: v1
          resource: pods
          namespace: "*"
          events: [add, update, delete]
        - group: apps
          version: v1
          resource: deployments
          namespace: homerun2-flux
          events: [add, update, delete]
```

**Resulting endpoints:**

| Service | URL |
|---------|-----|
| Omni Pitcher | `https://pitcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Core Catcher | `https://catcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Light Catcher | `https://light-catcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| WLED Mock | `https://wled-mock.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Demo Pitcher | `https://demo-pitcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| K8s Pitcher | *(cluster-internal, watches K8s API and pitches to Omni Pitcher)* |
| Redis Stack | `redis-stack.homerun2-flux.svc.cluster.local:6379` (internal) |

## HOW IT WORKS

Uses the Kustomize Components pattern:

1. **Root kustomization.yaml** composes eleven components (`redis-stack` + `omni-pitcher` + `core-catcher` + `k8s-pitcher` + `scout` + `light-catcher` + `wled-mock` + `demo-pitcher` + `led-catcher` + `git-pitcher` + `config-viewer`); `notification-catcher` is reachable only through `profiles/base`
2. **Outer Flux Kustomization** (consumer) reads `./apps/homerun2` from GitRepository, substitutes variables
3. **Redis Stack component** deploys Redis via HelmRelease into the shared namespace
4. **Omni Pitcher component** creates an OCIRepository + inner Flux Kustomization that reconciles the kustomize base from OCI, patches secrets, overrides image tag, and wires Redis connection
5. **Core Catcher component** same pattern as pitcher — patches secrets, sets `CATCHER_MODE=web`, removes KCL-generated HTTPRoute (replaced by component-level HTTPRoute with custom hostname)
6. **K8s Pitcher component** watches the K8s API via informers/collectors and sends events to omni-pitcher. Mounts CA trust bundle for TLS. Profile ConfigMap is defined on the calling side (cluster-specific config)
7. **Light Catcher component** consumes messages from Redis Streams and triggers WLED light effects based on configurable YAML profiles. Exposes an HTMX dashboard via HTTPRoute
8. **WLED Mock component** provides a mock WLED device with dashboard for development/testing. The light-catcher profile endpoints should point to `homerun2-wled-mock.NAMESPACE.svc.cluster.local` when using the mock
9. **Demo Pitcher component** provides a web UI for manually composing and pitching demo messages directly to Redis Streams. Useful for testing and demos without needing curl or the omni-pitcher API

Adding more homerun2 services is done by adding new component folders under `components/`. New profiles can be created under `profiles/` by composing the desired components.

## COMPLETE EXAMPLE: STHINGS-PLATFORM CLUSTER (BASE PROFILE)

Minimal deployment using the `profiles/base` profile (redis-stack, omni-pitcher, core-catcher, notification-catcher, scout):

**Cluster config** (`clusters/labul/vsphere/sthings-platform/apps/homerun2.yaml`):

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun2
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/homerun2/profiles/base
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN2_NAMESPACE: homerun2
      FLUX_SOURCE_API_VERSION: v1
      GATEWAY_NAME: sthings-platform-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: sthings-platform.sthings-vsphere.labul.sva.de
      HOMERUN2_OMNI_PITCHER_VERSION: v1.6.2
      HOMERUN2_OMNI_PITCHER_HOSTNAME: omni
      HOMERUN2_CORE_CATCHER_VERSION: v0.8.0
      HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION: v0.7.1
      HOMERUN2_CORE_CATCHER_HOSTNAME: core
      HOMERUN2_REDIS_VERSION: "17.1.4"
      HOMERUN2_REDIS_SERVICE_TYPE: ClusterIP
      HOMERUN2_REDIS_PERSISTENCE_ENABLED: "true"
      HOMERUN2_REDIS_STORAGE_CLASS: nfs4-csi
      HOMERUN2_REDIS_STORAGE_SIZE: 8Gi
      HOMERUN2_REDIS_IMAGE_REGISTRY: ghcr.io
      HOMERUN2_REDIS_IMAGE_REPOSITORY: stuttgart-things/redis-stack-server
      HOMERUN2_REDIS_IMAGE_VERSION: 7.2.0-v18
      HOMERUN2_REDIS_SENTINEL_REGISTRY: ghcr.io
      HOMERUN2_REDIS_SENTINEL_REPOSITORY: stuttgart-things/redis-sentinel
      HOMERUN2_REDIS_SENTINEL_VERSION: 7.4.2-debian-12-r9
    substituteFrom:
      - kind: Secret
        name: homerun2-secrets
```

**Resulting endpoints:**

| Service | URL |
|---------|-----|
| Omni Pitcher | `https://omni.sthings-platform.sthings-vsphere.labul.sva.de` |
| Core Catcher | `https://core.sthings-platform.sthings-vsphere.labul.sva.de` |
| Redis Stack | `redis-stack.homerun2.svc.cluster.local:6379` (internal) |

## TESTING WITH CURL

Send test events to the omni-pitcher `/pitch` endpoint:

**Minimal event:**

```bash
curl -X POST https://pitcher.<DOMAIN>/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Test Message",
    "message": "This is a test message"
  }'
```

**Full event with all fields:**

```bash
curl -X POST https://pitcher.<DOMAIN>/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Deployment Notification",
    "message": "Service xyz deployed successfully to production",
    "severity": "success",
    "author": "ci-pipeline",
    "system": "demo-system",
    "tags": "deployment,production,success",
    "assigneeaddress": "ops-team@example.com",
    "assigneename": "Ops Team",
    "artifacts": "docker://registry.example.com/xyz:1.0.0",
    "url": "http://example.com/deployment/xyz"
  }'
```

**Example using the movie-scripts cluster:**

```bash
curl -X POST https://pitcher.movie-scripts2.sthings-vsphere.labul.sva.de/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Infrastructure Alert",
    "message": "CPU usage exceeded 90% on node-3",
    "severity": "warning",
    "author": "monitoring",
    "system": "movie-scripts",
    "tags": "infra,cpu,alert"
  }'
```

**Health check:**

```bash
curl https://pitcher.<DOMAIN>/health
```

**Payload fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `title` | string | yes | - | Short title of the message |
| `message` | string | yes | - | Message content |
| `severity` | string | no | `info` | `info`, `warning`, `error`, `success` |
| `author` | string | no | `unknown` | Creator of the message |
| `system` | string | no | `homerun2-omni-pitcher` | Originating system |
| `tags` | string | no | - | Comma-separated tags |
| `assigneeaddress` | string | no | - | Assignee email/address |
| `assigneename` | string | no | - | Assignee name |
| `artifacts` | string | no | - | Related artifacts (e.g., container image) |
| `url` | string | no | - | Related URL |

**Response:**

```json
{
  "objectId": "550e8400-e29b-41d4-a716-446655440000-demo-system",
  "streamId": "messages",
  "status": "success",
  "message": "Message successfully enqueued"
}
```

## RELATED DOCUMENTATION

- [homerun2-omni-pitcher](https://stuttgart-things.github.io/homerun2-omni-pitcher/) — API gateway docs
- [homerun2-core-catcher](https://stuttgart-things.github.io/homerun2-core-catcher/) — Consumer/dashboard docs
- [homerun2-demo-pitcher](https://stuttgart-things.github.io/homerun2-demo-pitcher/) — Demo pitcher web UI docs
- [homerun2-light-catcher](https://stuttgart-things.github.io/homerun2-light-catcher/) — WLED light effects consumer docs
