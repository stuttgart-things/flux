# stuttgart-things/flux

flux infra & app kustomizations

## FLUX BOOSTRAP

<details><summary>CLI-GITHUB</summary>

```bash
# BOOTSTRAP GITHUB
export KUBECONFIG=<KUBECONFIG>
export GITHUB_TOKEN=<TOKEN>
flux bootstrap github --owner=stuttgart-things --repository=stuttgart-things --path=clusters/dev-cluster
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
    branch: feature/add-cert-manager
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

## ADD KUSTOMIZATION

<details><summary>ADD w/ KUBECTL</summary>

```bash
# BOOTSTRAP GITHUB
export KUBECONFIG=<KUBECONFIG>
export GITHUB_TOKEN=<TOKEN>
flux bootstrap github --owner=stuttgart-things --repository=stuttgart-things --path=clusters/dev-cluster
```

</details>

<details><summary>ADD w/ GIT</summary>


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
