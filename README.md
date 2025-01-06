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
