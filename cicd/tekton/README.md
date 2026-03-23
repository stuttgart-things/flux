# stuttgart-things/flux/cicd/tekton

Deploys the [Tekton Operator](https://tekton.dev/docs/operator/) v0.79.0 via vendored manifests + TektonConfig CR.

## Components

| Component | Description |
|---|---|
| `components/operator` | Tekton Operator (CRDs, RBAC, Deployments, ConfigMaps) |
| `components/config` | TektonConfig CR (controls which Tekton sub-components get installed) |

## Requirements

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
    branch: main
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

## Kustomization

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: tekton
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/tekton
  prune: true
  wait: true
  postBuild:
    substitute:
      TEKTON_TARGET_NAMESPACE: tekton-pipelines
      TEKTON_PROFILE: all
      TEKTON_ENABLE_API_FIELDS: beta
      TEKTON_DISABLE_INLINE_SPEC: ""
      TEKTON_IMAGE_PULL_POLICY: Always
      TEKTON_PRUNER_DISABLED: "false"
      TEKTON_PRUNER_SCHEDULE: "0 8 * * *"
      TEKTON_PRUNER_KEEP: "100"
      TEKTON_PRUNER_KEEP_SINCE: "1440"
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: tekton-operator
      namespace: tekton-operator
    - apiVersion: apps/v1
      kind: Deployment
      name: tekton-operator-webhook
      namespace: tekton-operator
EOF
```

## TektonConfig Parameters

| Variable | Default | Description |
|---|---|---|
| `TEKTON_TARGET_NAMESPACE` | `tekton-pipelines` | Namespace for Tekton Pipelines components |
| `TEKTON_PROFILE` | `all` | Install profile: `all`, `basic`, or `lite` |
| `TEKTON_ENABLE_API_FIELDS` | `beta` | API fields stability level: `stable`, `beta`, `alpha` |
| `TEKTON_DISABLE_INLINE_SPEC` | `""` | Disable inline spec for: `pipeline`, `pipelinerun`, `taskrun` (comma-separated) |
| `TEKTON_IMAGE_PULL_POLICY` | `Always` | Default image pull policy for task steps |
| `TEKTON_PRUNER_DISABLED` | `false` | Disable automatic pruning of old runs |
| `TEKTON_PRUNER_SCHEDULE` | `0 8 * * *` | Cron schedule for pruner |
| `TEKTON_PRUNER_KEEP` | `100` | Number of runs to keep |
| `TEKTON_PRUNER_KEEP_SINCE` | `1440` | Keep runs newer than N minutes |

## Updating the Operator

To update to a new version, download and re-split the release manifest:

```bash
VERSION=v0.79.0
curl -sL "https://infra.tekton.dev/tekton-releases/operator/previous/${VERSION}/release.yaml" > /tmp/tekton-release.yaml
# Then split by kind into components/operator/*.yaml
```

## Profiles

The TektonConfig `profile` controls which components the operator installs:

| Profile | Components |
|---|---|
| `lite` | Pipelines only |
| `basic` | Pipelines + Triggers |
| `all` | Pipelines + Triggers + Dashboard |
