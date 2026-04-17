# cert-manager on Argo CD

ArgoCD equivalent of [`infra/cert-manager`](../../../infra/cert-manager) (Flux).
Splits the install and the selfsigned bootstrap chain into two `Application`s
(App-of-Apps), with a per-cluster `ApplicationSet` for fan-out.

> Note: the Vault `ClusterIssuer` from the Flux `post-release.yaml` is not
> mirrored here — it's environment-specific (Vault address, AppRole, PKI
> path). See [Adding a Vault issuer](#adding-a-vault-issuer) for the pattern.

## Layout

```
tests/argocd/cert-manager/
├── apps/                          # App-of-Apps (static defaults)
│   ├── cert-manager.yaml          #   → Helm chart (sync-wave -10)
│   └── cert-manager-bootstrap.yaml#   → selfsigned + cluster-CA + wildcard cert (wave 0)
├── manifests/
│   └── bootstrap/                 # Kustomize base for the bootstrap CA chain
├── clusters/
│   └── example/
│       ├── cluster.yaml           # per-cluster params for the ApplicationSet
│       └── values.yaml            # cert-manager Helm values
├── root-app.yaml                  # (Option A) static App-of-Apps root
└── appset.yaml                    # (Option B) ApplicationSets, per-cluster fan-out
```

## Mapping from Flux

| Flux                                      | ArgoCD                                                |
|-------------------------------------------|-------------------------------------------------------|
| `requirements.yaml` (`Namespace` + `HelmRepository`) | `CreateNamespace=true` + Argo CD's built-in Helm source |
| `release.yaml` (HelmRelease)              | `apps/cert-manager.yaml`                              |
| `post-release.yaml` (Vault issuer)        | Not mirrored (see below)                              |
| `components/selfsigned/`                  | `apps/cert-manager-bootstrap.yaml` + `manifests/bootstrap/` |
| `dependsOn`                               | `argocd.argoproj.io/sync-wave`                        |
| `${VAR:-default}`                         | Helm `valuesObject` / Kustomize `patches` / ApplicationSet `goTemplate` |

The bootstrap Application waits one wave behind the Helm install so the
cert-manager webhook is available before any `Certificate`/`ClusterIssuer`
resources are submitted.

## Deployment — Option A: static App-of-Apps

```bash
kubectl apply -f root-app.yaml
```

Pulls in both child Applications with the defaults baked into `apps/`. Edit
those files (or fork) to change values.

## Deployment — Option B: ApplicationSet (multi-cluster)

1. Add a directory under `clusters/` with `cluster.yaml` + `values.yaml`. Use
   `clusters/example/` as a template.
2. Apply:

   ```bash
   kubectl apply -f appset.yaml
   ```

Each ApplicationSet uses a git-files generator to discover every
`clusters/*/cluster.yaml` and templates one Application per cluster.

### `cluster.yaml` schema

```yaml
cluster:
  name: <short name used in Application names>
  server: <Kubernetes API URL or in-cluster URL>
certManager:
  chartVersion: <Helm chart version, e.g. v1.19.2>
  namespace: <install namespace>
bootstrap:
  caName:             <name of bootstrap CA Certificate + ClusterIssuer>
  caSecret:           <Secret holding the CA keypair>
  wildcardCertName:   <name of wildcard Certificate>
  wildcardSecret:     <Secret name for the wildcard cert>
  wildcardNamespace:  <namespace for the wildcard cert (typically gateway ns)>
  domain:             <DNS zone; becomes *.DOMAIN>
```

## Adding a Vault issuer

To replicate `infra/cert-manager/post-release.yaml`, add a third Application
that points at a Kustomize base containing a `ClusterIssuer` with
`spec.vault`, plus a `Secret` for the AppRole `secret_id`. Patch values
(`vault.path`, `vault.server`, AppRole IDs) via ApplicationSet `kustomize.patches`
the same way `cert-manager-bootstrap` does.

## Prerequisites

- Argo CD installed in the `argocd` namespace.
- For Option B: target clusters registered as Argo CD cluster secrets, and Argo
  CD must be able to read this git repo.
