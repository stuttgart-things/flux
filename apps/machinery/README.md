# stuttgart-things/flux/machinery

Flux app for machinery — gRPC + HTMX service for watching Crossplane-managed Kubernetes custom resources. Deploys via OCI kustomize base (built from KCL manifests) with Gateway API HTTPRoute.

## Kustomization Example

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: machinery
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./apps/machinery
  prune: true
  wait: true
  postBuild:
    substitute:
      MACHINERY_NAMESPACE: machinery
      MACHINERY_VERSION: latest
      MACHINERY_HOSTNAME: machinery
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `MACHINERY_NAMESPACE` | `machinery` | Target namespace |
| `MACHINERY_VERSION` | `latest` | Image + kustomize OCI tag |
| `MACHINERY_HOSTNAME` | `machinery` | HTTPRoute hostname prefix |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute hostname |

## Endpoints

| Endpoint | Description |
|---|---|
| `https://<hostname>.<domain>/` | HTMX dashboard |
| `<hostname>.<domain>:50051` | gRPC API |

## Note: PipelineRuns re-appearing daily

Machinery only **watches** Crossplane XRs (`AnsibleRun`, `VMProvision`, …) and surfaces their status — it does not create PipelineRuns itself. PipelineRuns shown in its dashboard are rendered by the `stage-time` compositions via Crossplane's `provider-kubernetes` `Object`s (`managementPolicies: ["*"]`).

If runs in the CI namespace appear to re-trigger every morning, the cause is the cluster-wide Tekton operator pruner deleting them, followed by Crossplane recreating them on the next reconcile. The fix lives in `cicd/tekton` — see that app's README section *Caveat: Pruner + Crossplane-managed PipelineRuns* and the opt-in `components/ci-namespace` component that annotates the namespace with `operator.tekton.dev/prune.skip=true`.
