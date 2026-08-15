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
      MACHINERY_VERSION: v1.13.4
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
| `MACHINERY_VERSION` | `v1.13.4` | Image + kustomize OCI tag — **keep the `v`** |
| `MACHINERY_HOSTNAME` | `machinery` | HTTPRoute hostname prefix |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute hostname |

Both `ghcr.io/stuttgart-things/machinery` and `ghcr.io/stuttgart-things/machinery-kustomize` publish `v`-prefixed tags, so one variable serves both — but only in that form. A bare `1.13.4` leaves the `OCIRepository` unresolvable, and the resulting error does not mention the version, so the app simply never deploys.

## What the dashboard watches

The kinds and fields come from `config.json` in the `machinery-watch-config` ConfigMap ([`watch-config.yaml`](watch-config.yaml)), mounted at `/etc/machinery` and pointed to by `MACHINERY_CONFIG`. It ships this fleet's XRs:

| kind | shown |
|---|---|
| `ClusterStack` | `status.stage` — the one field to look at when a build is stuck — plus endpoint, domain and IP |
| `Platform` | `readyComponents` / `componentCount`, so `3 / 4` is visible without opening the YAML |
| `XIPReservation` | reservation status, FQDN, addresses |
| `VaultK8sAuth` | Vault address and cluster (its status is empty today, so Ready comes from conditions) |

The file is deliberately **not** a substitution variable: it is one document, identical on every cluster here, and threading ~60 lines of JSON through `postBuild.substitute` would mean escaping it across newlines for nothing. To watch something else, patch the ConfigMap.

It is also deliberately **not** called `machinery-config`. That name belongs to the Kustomize base, which feeds it to the container through `envFrom` — a `config.json` key there would additionally be offered as an environment variable, and `config.json` is not a valid environment variable name.

Field paths are verified against a live cluster rather than read off the XRD schemas. Note that the renderer does not support array indexing (`spec.parentRefs[0].name`); point at the parent path and let it flatten.

## Endpoints

| Endpoint | Description |
|---|---|
| `https://<hostname>.<domain>/` | HTMX dashboard |
| `<hostname>.<domain>:50051` | gRPC API |

## Note: PipelineRuns re-appearing daily

Machinery only **watches** Crossplane XRs (`AnsibleRun`, `VMProvision`, …) and surfaces their status — it does not create PipelineRuns itself. PipelineRuns shown in its dashboard are rendered by the `stage-time` compositions via Crossplane's `provider-kubernetes` `Object`s (`managementPolicies: ["*"]`).

If runs in the CI namespace appear to re-trigger every morning, the cause is the cluster-wide Tekton operator pruner deleting them, followed by Crossplane recreating them on the next reconcile. The fix lives in `cicd/tekton` — see that app's README section *Caveat: Pruner + Crossplane-managed PipelineRuns* and the opt-in `components/ci-namespace` component that annotates the namespace with `operator.tekton.dev/prune.skip=true`.
