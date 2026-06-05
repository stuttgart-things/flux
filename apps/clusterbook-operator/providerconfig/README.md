# clusterbook-operator / providerconfig

Parameterized base for a cluster-scoped `ClusterbookProviderConfig`. Point a
Flux `Kustomization` at `./apps/clusterbook-operator/providerconfig` and supply
the backend via `postBuild.substitute`:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: clusterbook-providerconfig
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  dependsOn:
    - name: clusterbook-operator   # ensure the CRD exists first
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/clusterbook-operator/providerconfig
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTERBOOK_PROVIDERCONFIG_NAME: default
      CLUSTERBOOK_API_URL: https://clusterbook.infra.example.com
      CLUSTERBOOK_INSECURE_SKIP_VERIFY: "false"
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTERBOOK_PROVIDERCONFIG_NAME` | `default` | Name of the ProviderConfig (referenced by `ClusterbookCluster.spec.providerConfigRef`) |
| `CLUSTERBOOK_API_URL` | *(required)* | Clusterbook backend URL (e.g. `https://clusterbook.infra.sthings.lab`) |
| `CLUSTERBOOK_INSECURE_SKIP_VERIFY` | `false` | Skip TLS verification of the backend. Keep `false` and ensure the backend CA is in the operator's trust bundle; set `true` only if that CA can't be trusted. |

> TLS: with `insecureSkipVerify: false` the operator verifies the backend cert
> against the mounted `cluster-trust-bundle` (trust-manager). If the backend's
> CA isn't in that bundle, either add it or set `CLUSTERBOOK_INSECURE_SKIP_VERIFY: "true"`.
