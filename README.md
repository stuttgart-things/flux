# stuttgart-things/flux

flux infra & app kustomizations

## FLUX BOOSTRAP

<details><summary>GITHUB SCM + FLUX OPERATOR</summary>

```bash
#### INSTALL OPERATOR
helm upgrade --install flux-operator \
oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator \
--namespace flux-system \
--create-namespace \
--version 0.28.0
```

#### GH SECRET

```bash
## DEPLOY FLUX

```bash
helm upgrade --install flux-operator \
oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator \
--namespace flux-system \
--create-namespace \
--version 0.28.0
```

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: git-token-auth
  namespace: flux-system
type: Opaque
stringData:
  username: $GITHUB_USER
  password: $GITHUB_TOKEN
EOF
```

#### SOPS SECRET

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: sops-age
  namespace: flux-system
type: Opaque
stringData:
  age.agekey: AGE-SECRET-KEY-1QY#...
EOF
```

#### FLUX-INSTANCE

```bash
kubectl apply -f - <<EOF
---
apiVersion: fluxcd.controlplane.io/v1
kind: FluxInstance
metadata:
  name: flux
  namespace: flux-system
  annotations:
    fluxcd.controlplane.io/reconcileEvery: "1h"
    fluxcd.controlplane.io/reconcileTimeout: "5m"
spec:
  distribution:
    version: "2.x"
    registry: "ghcr.io/fluxcd"
    artifact: "oci://ghcr.io/controlplaneio-fluxcd/flux-operator-manifests"
  components:
    - source-controller
    - kustomize-controller
    - helm-controller
    - notification-controller
    - image-reflector-controller
    - image-automation-controller
  cluster:
    type: kubernetes
    multitenant: false
    networkPolicy: true
    domain: "cluster.local"
  kustomize:
    patches:
      - patch: |
          - op: add
            path: /spec/decryption
            value:
              provider: sops
              secretRef:
                name: sops-age
        target:
          kind: Kustomization
      - target:
          kind: Deployment
          name: "(kustomize-controller|helm-controller)"
        patch: |
          - op: add
            path: /spec/template/spec/containers/0/args/-
            value: --concurrent=10
          - op: add
            path: /spec/template/spec/containers/0/args/-
            value: --requeue-dependency=5s
  sync:
    kind: GitRepository
    url: https://github.com/stuttgart-things/stuttgart-things.git
    ref: refs/heads/main
    path: clusters/labda/vsphere/sthings-runner
    pullSecret: git-token-auth
EOF
```

</details>

<details><summary>GITHUB SCM + FLUX CLI</summary>

```bash
# BOOTSTRAP GITHUB
export KUBECONFIG=<KUBECONFIG>
export GITHUB_TOKEN=<TOKEN>

flux bootstrap github \
--owner=stuttgart-things \
--repository=stuttgart-things \
--path=clusters/dev-cluster
```

</details>

## ADD GITREPOSITORY

<details><summary>FLUX APPS REPO (KUBECTL)</summary>

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
    tag: v1.0.0
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

## ADD KUSTOMIZATIONS

<details><summary>ADD w/ KUBECTL (TESTING)</summary>

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
  path: ./apps/tekton
  prune: true
  wait: true
  postBuild:
    substitute:
      TEKTON_NAMESPACE: tekton-pipelines
      TEKTON_PIPELINE_NAMESPACE: tektoncd
      TEKTON_VERSION: v0.60.4
EOF
```

</details>

<details><summary>ADD w/ GIT</summary>

* Create (single or --- seperated) yaml-files on cluster Folder (e.g. clusters/dev-cluster)
* Examples:

```yaml
# cat clusters/dev-cluster/app-repo.yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    tag: v1.0.0
  url: https://github.com/stuttgart-things/flux.git
```

```yaml
# cat clusters/dev-cluster/apps.yaml
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
  path: ./apps/tekton
  prune: true
  wait: true
  postBuild:
    substitute:
      TEKTON_NAMESPACE: tekton-pipelines
      TEKTON_PIPELINE_NAMESPACE: tektoncd
      TEKTON_VERSION: v0.60.4
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane
  namespace: flux-system
#.....
```

</details>

## DEV

<details><summary>GENERATE KUST</summary>

```bash
k2n gen \
--examples-dirs "/home/sthings/projects/apps/flux/apps,/home/sthings/projects/apps/helm/cicd" \
--usecase flux \
--instruction "transfer helmfile from tekton to a flux tekton kustomization"
```

</details>

## LICENSE

<details><summary><b>APACHE 2.0</b></summary>

Copyright 2023 patrick hermann.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

</details>

Author Information
------------------
Patrick Hermann, stuttgart-things 11/2024
