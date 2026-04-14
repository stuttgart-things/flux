# components/ci-namespace

Opt-in component that manages a CI namespace for Crossplane-rendered PipelineRuns (e.g. from `AnsibleRun` / `VMProvision` XRs in `stage-time`) and annotates it so the Tekton operator's pruner **skips** it.

## Why

The operator pruner is cluster-wide. When it deletes PipelineRuns in the CI namespace, Crossplane's `provider-kubernetes` Objects reconcile and recreate them — producing a daily re-trigger loop. See the root `README.md` ("Caveat: Pruner + Crossplane-managed PipelineRuns") for the full story.

## Usage

Enable by adding to `cicd/tekton/kustomization.yaml`:

```yaml
components:
  - components/operator
  - components/config
  - components/ci-namespace
```

Override the namespace name via Flux `postBuild.substitute`:

```yaml
TEKTON_CI_NAMESPACE: tekton-ci
```
