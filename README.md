# stuttgart-things/flux

Flux CD building blocks for stuttgart-things clusters: Kustomize bases and Helm
releases for infrastructure, apps and CI/CD tooling, plus three **platform
bundles** that let a cluster switch each one on with a single line.

This repo holds no cluster config. Clusters live in
[`stuttgart-things/stuttgart-things`](https://github.com/stuttgart-things/stuttgart-things)
and point at a tagged release of this repo.

📖 **Docs:** <https://stuttgart-things.github.io/flux/>

## Contents

- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [The platform bundles](#the-platform-bundles)
- [Using a single component](#using-a-single-component)
- [Releases and OCI artifacts](#releases-and-oci-artifacts)
- [Bootstrapping Flux](#bootstrapping-flux)
- [Secrets (SOPS)](#secrets-sops)
- [Contributing](#contributing)

## Repository layout

```
infra/       cluster infrastructure    cilium, cert-manager, openebs, velero, ...
apps/        applications              openbao, harbor, backstage, keycloak, ...
cicd/        delivery tooling          argo-cd, tekton, crossplane, dapr, kro, ...
  */platform/  the bundle for that layer: root/ + one Component per tool
hack/        CI checks (bundles, substitution, renovate annotations, image tags)
docs/        the TechDocs / mkdocs site
```

Every component directory is a self-contained Kustomize base: a
`requirements.yaml` (namespace + Helm/OCI source), a `release.yaml` (the
HelmRelease, or a Flux Kustomization over an OCI artifact), and optional
`pre-release.yaml`, `post-release.yaml` and `httproute.yaml`. All configurable
values are Flux substitutions of the form `${VAR:-default}`.

## Quick start

**1. Point Flux at a release of this repo.** Infra components read the source
`flux-infra`, apps and cicd components `flux-apps`. Both are this repo, usually
at the same tag:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-infra          # and a second one named flux-apps
  namespace: flux-system
spec:
  interval: 1h
  url: https://github.com/stuttgart-things/flux.git
  ref:
    tag: v1.94.0            # pin a release; see the Releases page
```

**2. Select components from a bundle.** One Kustomization per layer. Each line
under `components` deploys one tool; removing the line prunes it again.

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infra-platform
  namespace: flux-system
spec:
  interval: 1h
  timeout: 5m
  prune: true
  wait: true
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/platform/root
  components:
    - ../components/cilium-lb
    - ../components/cilium-gateway
    - ../components/cert-manager-install
    - ../components/openebs
  postBuild:
    substitute:
      INFRA_DOMAIN: lab.example.com
      CILIUM_LB_IP_START: "10.0.0.200"
      CILIUM_LB_IP_STOP: "10.0.0.210"
```

`apps-platform` (`./apps/platform/root`) and `cicd-platform`
(`./cicd/platform/root`) work the same way. All three read the same
`INFRA_DOMAIN`, `INFRA_GATEWAY_NAME` and `INFRA_GATEWAY_NAMESPACE`, so a cluster
can keep them in one ConfigMap and `substituteFrom` it into every bundle.

## The platform bundles

| Bundle | Path | Components | What it covers |
|---|---|---|---|
| [`infra/platform`](infra/platform) | `./infra/platform/root` | 24 | Cilium LB + Gateway, cert-manager + issuers, trust-manager, storage (openebs, nfs-csi), monitoring (prometheus, kube-prometheus-stack), external-secrets, SOPS, velero, CloudNativePG, reloader, flux-web, headlamp |
| [`apps/platform`](apps/platform) | `./apps/platform/root` | 25 | openbao, vault, harbor, keycloak, openldap, backstage, minio, redis-stack, rancher, vcluster, clusterbook, homepage, uptime-kuma, homerun2, tabletennis, ... |
| [`cicd/platform`](cicd/platform) | `./cicd/platform/root` | 16 | argo-cd, argo-rollouts, kargo, tekton, crossplane (+ profiles, capabilities), kro, dapr, claim-machinery-api, machinery-registry-api, komoplane, clusterbook-operator |

Worth knowing before selecting anything:

- **Dependencies cross bundles.** Many components `dependsOn` something in
  another bundle (most routes need `cilium-gateway`). A missing dependency is
  not an error: the component waits on "dependency not ready" forever.
- **Some components need a Secret you supply.** They use `substituteFrom` with
  `optional: false`, and the required keys are listed in each component's
  `# substituteFrom-keys:` comment.
- **Placeholders are loud on purpose.** Values that have no sensible default
  (StorageClass, domain) default to `set-<VAR>` / `*.invalid`, so a forgotten
  one fails visibly instead of half-working.

Each bundle README lists every component, what it requires and its
per-component gotchas.

## Using a single component

Without a bundle, point a Kustomization straight at a component and fill its
variables yourself. Each component's README lists them, and `task get-variables`
extracts them from any folder.

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: redis-stack
  namespace: flux-system
spec:
  interval: 1h
  prune: true
  wait: true
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/redis-stack
  postBuild:
    substitute:
      REDIS_STACK_STORAGE_CLASS: openebs-hostpath
    substituteFrom:
      - kind: Secret
        name: redis-stack-secrets   # REDIS_STACK_PASSWORD
```

## Releases and OCI artifacts

Every merge to `main` runs the [`Release`](.github/workflows/release.yaml)
workflow:

1. **semantic-release** cuts a `vX.Y.Z` tag and a GitHub Release from the
   commit messages (`feat:` → minor, `fix:` → patch). Release notes live on the
   [Releases page](https://github.com/stuttgart-things/flux/releases);
   `CHANGELOG.md` is frozen at v1.89.0.
2. Each **changed** `apps/*`, `infra/*` and `cicd/*` component is pushed as a
   Flux OCI artifact to `oci://ghcr.io/stuttgart-things/flux/<layer>/<name>`,
   tagged with the release version and `latest`. Unchanged components keep
   their older tags, so a component's newest version tag is the release that
   last touched it, not necessarily the repo's newest release.
3. The **whole repo** is pushed as one artifact,
   `oci://ghcr.io/stuttgart-things/flux/repo`, tagged with the release version
   and `latest`. It is pushed on every release, whether or not a component
   changed. A push to `main` that cuts no release (only `chore:`/`docs:`
   commits) does not re-push it, so a pinned `repo:vX.Y.Z` never changes
   under a cluster. Left out: `.git`, `.github/`, `.claude/`, `docs/`,
   `tests/`, `hack/`, `memory/` and every `*.md`. Nothing a kustomization
   reads is in that list.

Consume an artifact instead of the Git repo:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: vault
  namespace: flux-system
spec:
  interval: 1h
  url: oci://ghcr.io/stuttgart-things/flux/apps/vault
  ref:
    tag: latest   # or a version this component was published at:
                  # skopeo list-tags docker://ghcr.io/stuttgart-things/flux/apps/vault
```

### Consuming a bundle from `flux/repo`

A per-component artifact cannot serve the platform bundles. Each child
Kustomization a bundle renders uses a path from the repo root
(`./infra/cert-manager/components/install`), and some cross layers
(`infra-platform` → `./apps/cnpg-operator`). `flux/repo` holds the whole
tree, so a bundle reads from it the same way it reads from Git:

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: flux-repo
  namespace: flux-system
spec:
  interval: 1h
  url: oci://ghcr.io/stuttgart-things/flux/repo
  ref:
    tag: vX.Y.Z   # pin a release; `latest` follows main
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infra-platform
  namespace: flux-system
spec:
  interval: 1h
  prune: true
  wait: true
  sourceRef:
    kind: OCIRepository
    name: flux-repo
  path: ./infra/platform/root
  components:
    - ../components/cilium-lb
    - ../components/cert-manager-install
  postBuild:
    substitute:
      FLUX_SOURCE: flux-repo        # APPS_SOURCE for apps/ and cicd/platform
  # The children name their source with ${FLUX_SOURCE}, but their kind is
  # GitRepository. Switch it for every child the bundle renders:
  patches:
    - target:
        group: kustomize.toolkit.fluxcd.io
        kind: Kustomization
      patch: |
        - op: replace
          path: /spec/sourceRef/kind
          value: OCIRepository
```

The patch is applied to the bundle's rendered output, before Flux creates
the children, so it reaches each child's `sourceRef`. The children then read
the same artifact as the bundle, and infra and apps can be pinned to one
version. `apps/platform` and `cicd/platform` work the same way with
`path: ./apps/platform/root` / `./cicd/platform/root` and `APPS_SOURCE`.

`cicd/platform`'s `argocd-platform` component also creates its own
`GitRepository` for the Argo CD catalog. The patch above does not change it,
so that component still needs Git access.

To list the published versions, run
`skopeo list-tags docker://ghcr.io/stuttgart-things/flux/repo`.

Re-publish everything, including `flux/repo` (for example to seed the
registry or backfill a tag):
`gh workflow run release.yaml --ref main -f push-all=true`.

## Bootstrapping Flux

The cluster needs Flux, a Git credential and, for SOPS, the age key. Three
documented ways:

| Method | When | Guide |
|---|---|---|
| Flux Operator + `FluxInstance` | the default for our clusters | [docs/bootstrap/flux-operator.md](docs/bootstrap/flux-operator.md) |
| `flux bootstrap github` | quick tests | [docs/bootstrap/flux-cli.md](docs/bootstrap/flux-cli.md) |
| Dagger + KCL blueprint | automated provisioning | [docs/bootstrap/blueprints.md](docs/bootstrap/blueprints.md) |

SOPS decryption is enabled by a kustomize-controller patch on the
`FluxInstance` that points every Kustomization at the `sops-age` Secret in
`flux-system`. See [docs/bootstrap/sops-secrets.md](docs/bootstrap/sops-secrets.md).

## Secrets (SOPS)

Encrypt and decrypt with the Dagger SOPS module and an age key:

```bash
# encrypt
export AGE_PUBLIC_KEY="age1..."
dagger call -m github.com/stuttgart-things/dagger/sops encrypt \
  --age-key="env:AGE_PUBLIC_KEY" --plaintext-file="./secret.yaml" \
  --file-extension="yaml" export --path="./secret.enc.yaml"

# decrypt
export SOPS_AGE_KEY="AGE-SECRET-KEY-1..."
dagger call -m github.com/stuttgart-things/dagger/sops decrypt \
  --age-key="env:SOPS_AGE_KEY" --encrypted-file="./secret.enc.yaml" contents
```

In-cluster alternatives are also bundle components: `external-secrets` (Vault)
and `sops-secrets-operator` (`SopsSecret` resources).

## Contributing

- **Adding a component:** see [docs/development/adding-components.md](docs/development/adding-components.md)
  and [conventions.md](docs/development/conventions.md). Prefer Gateway API
  `HTTPRoute` over Ingress.
- **Chart versions** that use `${VAR:-x}` need a `# renovate:` annotation on the
  line above, otherwise Renovate silently never updates them.
- **Commits** follow the Angular convention (`feat:`, `fix:`, `docs:`, ...);
  they decide the next version.
- **Pull requests** must pass `Chart version annotations`, `Image tags resolve`
  and `Renovate config` (enforced on `main`). `Bundle components` runs the
  bundle checks under [`hack/`](hack) as well.

Useful tasks ([go-task](https://taskfile.dev), `task -l` for all):

```bash
task get-variables       # list ${VAR:-default} variables of a component
task check-renovate      # every substituted chart version is annotated
task verify-image-tags   # every substituted image tag exists
task preview-renovate    # dry-run Renovate against the working tree
pre-commit run --files <changed files>
```

`CLAUDE.md` holds the longer background on CI, releases and Renovate.

## License

Apache 2.0, see [LICENSE](LICENSE). © 2023 Patrick Hermann, stuttgart-things.
