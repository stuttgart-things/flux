# cicd/platform

The delivery layer, selected exactly like [`infra/platform`](../../infra/platform)
and [`apps/platform`](../../apps/platform): one kustomize Component per tool,
all opt-in, chosen with `spec.components` on the consumer's own Flux
Kustomization.

```
cicd/platform/
├── root/          empty kustomization — the consumer's spec.path
└── components/
    ├── argo-cd/              → ./cicd/argo-cd        (needs cilium-gateway + a Secret)
    ├── argocd-platform/      → ./cicd/argocd-platform/overlays/…  (an ArgoCD control plane)
    ├── argo-rollouts/        → ./cicd/argo-rollouts
    ├── crossplane/           → ./cicd/crossplane/profiles/${CROSSPLANE_PROFILE}/…
    ├── crossplane-capabilities/ → …/capabilities/sets/${CROSSPLANE_CAPABILITY_SET}  (needs crossplane + sops-git)
    ├── crossplane-runtime-defaults/ → ./cicd/crossplane/runtime-defaults  (machinery profile WITHOUT fleet state only)
    ├── kro/                  → ./cicd/kro
    ├── machinery/            → ./cicd/machinery       (needs crossplane-configs)
    ├── machinery-auth/       → ./cicd/machinery + auth (alternative of machinery: gRPC bearer-token auth ON)
    ├── tekton/               → ./cicd/tekton          (needs cilium-gateway)
    ├── kargo/                → ./apps/kargo/…         (needs the ESO vault store + a Secret)
    ├── dapr/                 → ./apps/dapr/root       (control plane only)
    ├── dapr-workflows/       → ./apps/dapr/workflow-secrets  (needs dapr + external-secrets; brings its own Redis)
    ├── dapr-workflows-trigger/ → ./apps/dapr/root     (the BackstageTemplateRun RGD; needs kro + dapr-workflows)
    ├── komoplane/            → ./cicd/komoplane       (needs crossplane + cilium-gateway)
    ├── claim-machinery-api/  → ./apps/claim-machinery-api    (needs cilium-gateway)
    ├── machinery-registry-api/ → ./apps/machinery-registry-api (needs cilium-gateway)
    └── clusterbook-operator/ → ./apps/clusterbook-operator
```

Several of those paths are under `apps/` and that is not an inconsistency: the
bundle a component belongs to is decided by the layer it serves, not by the
directory its base happens to sit in. `kargo`, `dapr`, `claim-machinery-api`,
`machinery-registry-api` and `clusterbook-operator` are delivery-layer tools;
most of their bases were written before this bundle existed. `infra/platform` does the same with `flux-web` and
`headlamp`.

## Why a third bundle rather than more apps

`argo-cd` used to sit in `apps/platform`, and its child Kustomization already
pointed at `./cicd/argo-cd` — only the wrapper was in the app layer. ArgoCD,
Tekton and Crossplane are not apps a platform happens to run; they are how a
platform delivers things. Keeping them apart lets a cluster take the delivery
layer without the app layer, which is the whole point of a CI/CD cluster.

No cluster had selected `argo-cd` from `apps/platform`, so the move cost
nothing. Anything that had would need its `components:` line repointed here.

## Same variables as the other two bundles

`INFRA_DOMAIN`, `INFRA_GATEWAY_NAME` and `INFRA_GATEWAY_NAMESPACE` are read
here under the same names, so a cluster defines its domain once in a ConfigMap
and `substituteFrom`s it into all three rather than writing it three times in
files that will eventually disagree.

`dependsOn` crosses bundles freely: `argo-cd` and `tekton` depend on
`cilium-gateway`, which `infra-platform` provides. Flux does not care which
Kustomization owns a name, only that it exists and is ready. Selecting one of
them on a cluster whose infra bundle has no gateway gives no error — it waits
on "dependency not ready" forever, which reads like slowness.

## The two that need a Secret

`argo-cd` and `dapr-workflows` use `substituteFrom` with `optional: false`.
Left optional, Flux substitutes empty strings and installs an ArgoCD nobody can
log into, or a workflow runtime holding a GitHub token that is present, empty
and silently unauthorized — reporting success either way.

## dapr-workflows brings its own Redis

The same Kustomization selects `apps/dapr`'s `redis-stack` and `redis-auth`
components, and `DAPR_WORKFLOWS_REDIS_HOST` defaults to that Redis
(`redis-stack.dapr-redis:6379`). Its password is the `redis_password` field of
the same Vault entry as the two API tokens, so the chart's copy and the Dapr
component's copy cannot drift apart.

The chart's start scripts leave some shell variables bare (`$HOSTNAME`,
`$REDISPORT`). That is fine: Flux's substitution only ever touches the braced
`${VAR}` form, and a bare `$VAR` passes through to the pod untouched (#325).
`flux envsubst` shows it:

```console
$ echo '$HOSTNAME ${HOSTNAME} $${HOSTNAME}' | HOSTNAME=foo flux envsubst
$HOSTNAME foo ${HOSTNAME}
```

## Tekton's profile and its dashboard travel together

`TEKTON_PROFILE` defaults to `all` — pipelines, triggers and dashboard. The
component also renders the dashboard HTTPRoute. Narrowing the profile to
`basic` without dropping this component leaves a route pointing at a Service
that is never created: a Gateway that answers 404 for a hostname the cluster
publishes.

Tekton **Results** is off (`TEKTON_RESULT_DISABLED: true`). It needs its own
database and object storage, and a half-configured Results routes every TaskRun
log through a watcher that cannot store anything.

## The three newest components

**`komoplane`** is a read-only browser for Crossplane claims, composites and
managed resources. It depends on `crossplane` as well as `cilium-gateway`,
because without Crossplane CRs it starts, serves and shows an empty tree while
every object reports healthy — "waiting for crossplane" is a question somebody
can answer, "the dashboard is empty" is not. It ships **no authentication of
any kind**, so whatever the Gateway exposes is world-readable.

**`claim-machinery-api`** renders Crossplane claims from a profile. It does
*not* depend on `crossplane`: it returns manifests, and a cluster can run it as
a rendering service against a control plane somewhere else.

Its profile is **fetched at runtime over the network**, from a raw
githubusercontent URL pinned to a git ref — not from this repo and not from the
OCI artifact. The deployed behaviour can therefore change with no commit here,
whenever that ref moves. `CLAIM_MACHINERY_PROFILE_REF` defaults to `main`; pin
it to a tag where that matters.

**`machinery-registry-api`** serves the claim inventory (`registry.yaml` in a
GitHub repo) that Backstage's `RegistryClaimPicker` reads through its
`/machinery-registry` proxy. Like `claim-machinery-api` it reads its data **at
runtime** from GitHub (`MACHINERY_REGISTRY_REPO`, default
`stuttgart-things/harvester`), which must be public. Its host defaults to what
`apps/platform`'s `backstage` points the proxy at, so the two wire up with no
override.

**`clusterbook-operator`** reconciles the Clusterbook CRs. It carries no
`dependsOn`, unlike the `argocd-platform` wiring of the same path — there it
waits for `argo-cd` because it writes Argo CD cluster-secrets; here it is a
standalone operator that brings its own CRDs, namespace and RBAC.

It needs a `ClusterbookProviderConfig`, and this component does not ship one:
that CR names the kubeconfig Secret of the cluster hosting the backend, which
is environment data belonging in the cluster repo. Seed it with
`kustomize.toolkit.fluxcd.io/{prune,reconcile}: disabled`. Without it the
operator runs, reconciles nothing, and reports healthy.

`./apps/clusterbook-operator` is now rendered by **two** Kustomizations — this
component and `cicd/argocd-platform/base`. `hack/check-shared-path-wiring.py`
holds them in step: thread a variable in one and CI fails until it is threaded
in the other, because Flux does not inherit `postBuild.substitute` and a
cluster setting a value only one of them names silently gets the other's
default.

## Upgrading a Crossplane Configuration is not a version bump

A short-named `Configuration` that is also the `dependsOn` target of another
package spawns a long-named duplicate on upgrade and takes **every** package to
`Healthy=False`. Change one version at a time and watch `kubectl get pkg`
before the next one.
