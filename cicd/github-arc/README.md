# cicd/github-arc

GitHub Actions self-hosted runners (Actions Runner Controller, ARC) through our
Crossplane v2 packages from
[stuttgart-things/crossplane-configurations](https://github.com/stuttgart-things/crossplane-configurations)
(`cicd/github-arc-controller`, `cicd/github-runner-set`), selected with
`../components/github-arc` in a cluster's `cicd-platform` bundle. The Flux twin
of `cicd/github-arc` in stuttgart-things/argocd.

| Child Kustomization | Path | Renders |
|---|---|---|
| `github-arc` | `configurations/` | Configurations `github-arc-controller`, `github-runner-set` (`skipDependencyResolution`, see the file); Ready when both are Healthy |
| `github-arc-controller` | `controller/` | one `GithubArcController` XR: chart `gha-runner-scale-set-controller` in `arc-systems`, release `github-controller` |

Needs the `crossplane` component: provider-helm v1, function-go-templating,
function-auto-ready and the helm `ClusterProviderConfig` `in-cluster`.

## Runner sets: the cluster's own files

One `GithubRunnerSet` XR per repository. Flux cannot loop over a list, so the
cluster declares them itself, in a Kustomization that `dependsOn`
`github-arc-controller`. The XR's name is the scale set name and the `runs-on:`
label, `ghr-<repository>-<clusterName>` by convention:

```yaml
apiVersion: resources.stuttgart-things.com/v1alpha1
kind: GithubRunnerSet
metadata:
  name: ghr-ansible-in-cluster        # runs-on: ghr-ansible-in-cluster
  namespace: crossplane-system
spec:
  clusterName: in-cluster
  helmProviderConfigRef: in-cluster
  runnerScaleSetName: ghr-ansible-in-cluster
  namespace: arc-runners
  version: "0.15.0"                   # = the controller's
  organization: stuttgart-things
  repository: ansible
  githubConfigSecret: github-arc      # Secret in arc-runners, key github_token
  controllerServiceAccount:           # named: the chart's lookup fails while the controller installs
    namespace: arc-systems
    name: github-controller-gha-rs-controller
  minRunners: 0
  maxRunners: 3
  runnerImage:
    tag: "2.338.0"
  containerMode:
    type: kubernetes
    requireJobContainer: false
    storageClassName: openebs-hostpath
    storage: 1Gi
```

The credential Secret (`github-arc` in `arc-runners`, key `github_token`) is
the cluster's too -- SOPS or an ExternalSecret; the XR carries only its name.

## Substitutes

| Variable | Default |
|---|---|
| `GITHUB_ARC_CONTROLLER_CONFIG_VERSION` / `GITHUB_RUNNER_SET_CONFIG_VERSION` | `v0.1.0` |
| `GITHUB_ARC_VERSION` | `0.15.0` (chart; runner sets must match) |
| `GITHUB_ARC_CLUSTER_NAME` | `in-cluster` |
| `GITHUB_ARC_HELM_PROVIDER_CONFIG` | `in-cluster` |
| `GITHUB_ARC_CONTROLLER_NAMESPACE` / `GITHUB_ARC_CONTROLLER_RELEASE` | `arc-systems` / `github-controller` |
| `GITHUB_ARC_XR_NAMESPACE` | `crossplane-system` |
| `GITHUB_ARC_SUSPEND` | `false` |

## Upgrading ARC

Helm installs `crds/` only on the first install. After a `GITHUB_ARC_VERSION`
bump apply the matching CRDs by hand (see the github-arc-controller README in
crossplane-configurations) -- an old CRD set silently prunes status fields and
floods the cluster with orphaned EphemeralRunners.
