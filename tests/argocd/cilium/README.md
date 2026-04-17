# Cilium on Argo CD

ArgoCD equivalent of [`infra/cilium`](../../../infra/cilium) (Flux). The Flux
HelmRelease + Kustomize components are split into three Argo CD `Application`s
(App-of-Apps) and deployed per cluster via an `ApplicationSet`.

## Layout

```
tests/argocd/cilium/
├── apps/                      # App-of-Apps: 3 child Applications (static defaults)
│   ├── cilium.yaml            #   → Cilium Helm chart (sync-wave -10)
│   ├── cilium-lb.yaml         #   → CiliumLoadBalancerIPPool + L2 policy (wave 0)
│   └── cilium-gateway.yaml    #   → Gateway API Gateway (wave 10)
├── manifests/
│   ├── lb/                    # Kustomize base for LB/L2 CRs
│   └── gateway/               # Kustomize base for Gateway
├── clusters/
│   └── example/
│       ├── cluster.yaml       # per-cluster params consumed by ApplicationSet
│       └── values.yaml        # Cilium Helm values
├── root-app.yaml              # (Option A) static App-of-Apps root
└── appset.yaml                # (Option B) 3 ApplicationSets, one per component
```

## Mapping from Flux

| Flux (`infra/cilium`)                 | ArgoCD (`tests/argocd/cilium`)                        |
|---------------------------------------|-------------------------------------------------------|
| `components/install/requirements.yaml`| Namespace auto-created via `CreateNamespace=true`; `HelmRepository` replaced by Argo CD's built-in Helm source |
| `components/install/release.yaml`     | `apps/cilium.yaml` — Helm `Application`               |
| `components/lb/cilium-config.yaml`    | `manifests/lb/` + `apps/cilium-lb.yaml` (wave 0)      |
| `components/gateway/gateway.yaml`     | `manifests/gateway/` + `apps/cilium-gateway.yaml` (wave 10) |
| `dependsOn`                           | `argocd.argoproj.io/sync-wave` annotations            |
| `${VAR:-default}` (`postBuild.substitute`) | Helm `valuesObject` / Kustomize patches / ApplicationSet `goTemplate` |

Ordering is enforced with sync-waves so the Cilium Helm release (and its CRDs)
reconciles before the LB/Gateway Applications try to apply Cilium-owned CRs.

## Deployment — Option A: static App-of-Apps

Single cluster, no templating:

```bash
kubectl apply -f root-app.yaml
```

`root-app.yaml` points at `apps/` and pulls in the three child Applications with
their default values. Edit values directly in `apps/cilium.yaml` or fork and
override.

## Deployment — Option B: ApplicationSet (multi-cluster)

1. Add a cluster directory under `clusters/` with a `cluster.yaml` describing
   the target and a `values.yaml` with Cilium Helm overrides. See
   `clusters/example/` for the schema.
2. Apply the ApplicationSets:

   ```bash
   kubectl apply -f appset.yaml
   ```

Each ApplicationSet uses a `git` files generator to discover every
`clusters/*/cluster.yaml`, then templates the matching Application per cluster.

### `cluster.yaml` schema

```yaml
cluster:
  name: <short name used in Application names>
  server: <Kubernetes API URL or in-cluster URL>
cilium:
  chartVersion: <Helm chart version>
  namespace: <install namespace, typically kube-system>
lb:
  ipStart: <first LB IP>
  ipStop:  <last LB IP>
gateway:
  namespace: <namespace for the Gateway resource>
  domain:    <DNS zone; becomes *.DOMAIN>
  tlsSecret: <Secret holding the wildcard cert>
```

## Prerequisites

- Argo CD installed in the `argocd` namespace.
- For Option B: the Argo CD instance must be able to reach the target clusters
  (registered as cluster secrets) and read this git repo.
- For the Gateway Application: a wildcard TLS secret matching `gateway.domain`
  must exist in `gateway.namespace` before the Gateway can bind its listener.
- Gateway API CRDs (`gateway.networking.k8s.io/v1`) installed on the target
  cluster. The Cilium chart does not ship them.
