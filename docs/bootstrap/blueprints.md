# Bootstrap with Blueprints (Dagger + KCL)

Render a complete `FluxInstance` manifest using Dagger and KCL for automated cluster provisioning.

## Prerequisites

- `dagger` CLI installed
- `helmfile` CLI installed
- `GITHUB_TOKEN` and `SOPS_AGE_KEY` exported

## 1. Install the Flux Operator

```bash
helmfile init --force
helmfile apply -f git::https://github.com/stuttgart-things/helm.git@cicd/flux-operator.yaml.gotmpl \
  --state-values-set version=0.28.0
```

## 2. Render FluxInstance with Dagger

```bash
dagger call -m github.com/stuttgart-things/dagger/kcl@v0.76.0 run \
  --oci-source ghcr.io/stuttgart-things/kcl-flux-instance:0.3.3 \
  --parameters "\
name=flux, \
namespace=flux-system, \
gitUrl=https://github.com/stuttgart-things/stuttgart-things.git, \
gitRef=refs/heads/main, \
gitPath=clusters/labda/edge/xplane, \
pullSecret=git-token-auth, \
renderSecrets=true, \
gitUsername=<your-username>, \
gitPassword=$GITHUB_TOKEN, \
sopsAgeKey=$SOPS_AGE_KEY, \
version=2.4" \
  export --path ./flux-instance.yaml
```

## 3. Apply the Rendered Manifest

```bash
kubectl apply -f ./flux-instance.yaml
```

## Parameters

| Parameter | Description |
|---|---|
| `name` | FluxInstance name |
| `namespace` | Target namespace |
| `gitUrl` | Git repository URL |
| `gitRef` | Git reference (branch/tag) |
| `gitPath` | Path within the repo for cluster config |
| `pullSecret` | Name of the Git auth secret |
| `renderSecrets` | Set `true` to include Git + SOPS secrets |
| `gitUsername` | GitHub username |
| `gitPassword` | GitHub token |
| `sopsAgeKey` | SOPS Age private key |
| `version` | Flux distribution version |

## When to Use This

- Automated cluster provisioning pipelines
- Reproducible infrastructure-as-code workflows
- When you need secrets rendered alongside the FluxInstance
