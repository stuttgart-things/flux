# Tekton on Argo CD

ArgoCD equivalent of [`cicd/tekton`](../../../cicd/tekton) (Flux). Splits the
vendored Tekton Operator manifests, the `TektonConfig` CR, the optional CI
namespace, and the dashboard `HTTPRoute` into four `Application`s
(App-of-Apps), with a per-cluster `ApplicationSet` for fan-out.

## Layout

```
tests/argocd/tekton/
├── apps/                              # App-of-Apps (static defaults)
│   ├── tekton-operator.yaml           #   → vendored operator manifests (wave -10)
│   ├── tekton-config.yaml             #   → TektonConfig CR (wave 0)
│   ├── tekton-ci-namespace.yaml       #   → opt-in CI namespace (wave 0)
│   └── tekton-dashboard-httproute.yaml#   → Gateway API HTTPRoute (wave 10)
├── manifests/
│   ├── config/                        # TektonConfig CR (patchable per cluster)
│   ├── ci-namespace/                  # CI namespace with prune.skip annotation
│   └── dashboard-httproute/           # HTTPRoute for the Tekton Dashboard
├── clusters/
│   └── example/
│       └── cluster.yaml               # per-cluster params for the ApplicationSets
├── root-app.yaml                      # (Option A) static App-of-Apps root
└── appset.yaml                        # (Option B) ApplicationSets, per-cluster fan-out
```

The `tekton-operator` Application does **not** duplicate the ~1500 lines of
vendored operator YAML. It points directly at
[`cicd/tekton/components/operator`](../../../cicd/tekton/components/operator)
using Argo CD's `directory:` source, excluding the Kustomize `Component`
file so Argo CD loads the raw resources.

## Mapping from Flux

| Flux                                      | ArgoCD                                                |
|-------------------------------------------|-------------------------------------------------------|
| `components/operator` (Component)         | `apps/tekton-operator.yaml` — directory source pointing at `cicd/tekton/components/operator`, excluding `kustomization.yaml` |
| `components/config/tekton-config.yaml`    | `manifests/config/` + `apps/tekton-config.yaml`        |
| `components/ci-namespace/namespace.yaml`  | `manifests/ci-namespace/` + `apps/tekton-ci-namespace.yaml` |
| `components/dashboard-httproute/httproute.yaml` | `manifests/dashboard-httproute/` + `apps/tekton-dashboard-httproute.yaml` |
| Flux root `kustomization.yaml` includes only operator + config; dashboard-httproute and ci-namespace are opt-in | Argo CD App-of-Apps includes all four; delete the unwanted files from `apps/kustomization.yaml` (or the ApplicationSet) to opt out |
| `dependsOn` / implicit ordering           | `argocd.argoproj.io/sync-wave`                        |
| `${VAR:-default}` (`postBuild.substitute`)| Kustomize `patches` driven by ApplicationSet `goTemplate` |

The `tekton-config` Application has retry enabled so the TektonConfig CR keeps
retrying until the operator (wave `-10`) has registered the
`operator.tekton.dev/v1alpha1` CRD.

## Deployment — Option A: static App-of-Apps

```bash
kubectl apply -f root-app.yaml
```

Applies all four child Applications with the concrete defaults in `manifests/`
and `apps/`. Remove entries from `apps/kustomization.yaml` (or from the
Application files themselves) to skip the opt-in pieces (ci-namespace,
dashboard-httproute).

## Deployment — Option B: ApplicationSet (multi-cluster)

1. Add a directory under `clusters/` with `cluster.yaml`. Use
   `clusters/example/` as a template.
2. Apply:

   ```bash
   kubectl apply -f appset.yaml
   ```

Four ApplicationSets (one per component) use a git-files generator to
discover every `clusters/*/cluster.yaml` and template one Application per
cluster with Kustomize patches driven by `goTemplate`.

### `cluster.yaml` schema

```yaml
cluster:
  name: <short name used in Application names>
  server: <Kubernetes API URL or in-cluster URL>
tekton:
  operatorNamespace: <namespace for the Tekton Operator; typically tekton-operator>
  targetNamespace:   <TektonConfig.spec.targetNamespace; typically tekton-pipelines>
  profile:           <install profile: all | basic | lite>
  enableApiFields:   <stable | beta | alpha>
  disableInlineSpec: <"" | pipeline,pipelinerun,taskrun>
  prunerDisabled:    <true | false>
  prunerSchedule:    <cron>
  prunerKeepSince:   <minutes>
ciNamespace:
  name:              <CI namespace name; annotated with prune.skip=true>
dashboard:
  namespace:         <HTTPRoute namespace; typically the tekton-pipelines ns>
  hostname:          <dashboard subdomain>
  domain:            <DNS zone>
  gatewayName:       <parent Gateway name; typically cilium-gateway>
  gatewayNamespace:  <parent Gateway namespace>
```

## Pruner caveat

The operator's pruner is a single cluster-wide CronJob (see
[the Flux README](../../../cicd/tekton/README.md#caveat-pruner--crossplane-managed-pipelineruns)).
If PipelineRuns are managed by Crossplane's `provider-kubernetes`, deletions
trigger recreates. The `tekton-ci-namespace` Application manages a namespace
annotated with `operator.tekton.dev/prune.skip: "true"` to bypass the pruner
for that namespace while keeping global pruning intact.

## Prerequisites

- Argo CD installed in the `argocd` namespace.
- For the dashboard HTTPRoute: Gateway API CRDs + a parent `Gateway` (e.g.
  from [`tests/argocd/cilium`](../cilium)).
- Argo CD must be able to read this git repo (the operator Application uses
  a `directory:` source pointing at `cicd/tekton/components/operator`).
