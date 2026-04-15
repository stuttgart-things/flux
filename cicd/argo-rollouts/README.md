# stuttgart-things/flux/cicd/argo-rollouts

Deploys [Argo Rollouts](https://argo-rollouts.readthedocs.io/) from the
`argo-helm` repository (`https://argoproj.github.io/argo-helm`, chart
`argo-rollouts`) via Flux, including the dashboard exposed through a Gateway
API `HTTPRoute`.

Equivalent of:

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm install argo-rollouts argo/argo-rollouts \
  --version 2.40.9 \
  --create-namespace \
  --namespace argo-rollouts \
  --wait
```

## REQUIREMENTS

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

## KUSTOMIZATION

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: argo-rollouts
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/argo-rollouts
  prune: true
  wait: true
  postBuild:
    substitute:
      ARGO_ROLLOUTS_NAMESPACE: argo-rollouts
      ARGO_ROLLOUTS_VERSION: "2.40.9"
      ARGO_ROLLOUTS_INSTALL_CRDS: "true"
      ARGO_ROLLOUTS_KEEP_CRDS: "true"
      ARGO_ROLLOUTS_CLUSTER_INSTALL: "true"
      ARGO_ROLLOUTS_CREATE_CLUSTER_AGGREGATE_ROLES: "true"
      ARGO_ROLLOUTS_CONTROLLER_REPLICAS: "2"
      ARGO_ROLLOUTS_LOG_LEVEL: info
      ARGO_ROLLOUTS_LOG_FORMAT: text
      ARGO_ROLLOUTS_METRICS_ENABLED: "false"
      ARGO_ROLLOUTS_SERVICEMONITOR_ENABLED: "false"
      ARGO_ROLLOUTS_DASHBOARD_ENABLED: "true"
      ARGO_ROLLOUTS_DASHBOARD_READONLY: "false"
      ARGO_ROLLOUTS_DASHBOARD_REPLICAS: "1"
      ARGO_ROLLOUTS_HOSTNAME: argo-rollouts
      DOMAIN: example.com
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
EOF
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `ARGO_ROLLOUTS_NAMESPACE` | `argo-rollouts` | Target namespace |
| `ARGO_ROLLOUTS_VERSION` | `2.40.9` | Chart version |
| `ARGO_ROLLOUTS_INSTALL_CRDS` | `true` | Install and upgrade CRDs |
| `ARGO_ROLLOUTS_KEEP_CRDS` | `true` | Keep CRDs on helm uninstall |
| `ARGO_ROLLOUTS_CLUSTER_INSTALL` | `true` | Cluster-wide controller (requires cluster RBAC) |
| `ARGO_ROLLOUTS_CREATE_CLUSTER_AGGREGATE_ROLES` | `true` | Create cluster aggregate roles |
| `ARGO_ROLLOUTS_CONTROLLER_REPLICAS` | `2` | Number of controller pods |
| `ARGO_ROLLOUTS_LOG_LEVEL` | `info` | Controller log level |
| `ARGO_ROLLOUTS_LOG_FORMAT` | `text` | Controller log format (`text` or `json`) |
| `ARGO_ROLLOUTS_METRICS_ENABLED` | `false` | Expose Prometheus metrics service |
| `ARGO_ROLLOUTS_SERVICEMONITOR_ENABLED` | `false` | Deploy a Prometheus `ServiceMonitor` |
| `ARGO_ROLLOUTS_DASHBOARD_ENABLED` | `true` | Deploy the Argo Rollouts dashboard |
| `ARGO_ROLLOUTS_DASHBOARD_READONLY` | `false` | Read-only dashboard cluster role |
| `ARGO_ROLLOUTS_DASHBOARD_REPLICAS` | `1` | Number of dashboard pods |
| `ARGO_ROLLOUTS_HOSTNAME` | `argo-rollouts` | Hostname prefix for the dashboard HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for the dashboard HTTPRoute |
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |

The dashboard is exposed via a Gateway API `HTTPRoute` (`httproute.yaml`) instead
of the chart's built-in ingress, consistent with other apps in this repository.
