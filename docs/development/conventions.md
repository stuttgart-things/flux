# Conventions

Patterns and standards used across this repository.

## Variable Substitution

All configurable values use Flux's `postBuild.substitute` pattern:

```yaml
spec:
  postBuild:
    substitute:
      MY_VAR: my-value
    substituteFrom:
      - kind: Secret
        name: my-secret
```

Variables in YAML files use the syntax `${VAR_NAME:-default_value}`:

- `VAR_NAME` — UPPERCASE with underscores
- `default_value` — fallback if not provided by the consumer
- Variables without defaults are required

Run `task get-variables` to extract all variables from a component folder.

## API Versions

Use current stable API versions:

| Resource | API Version |
|---|---|
| GitRepository | `source.toolkit.fluxcd.io/v1` |
| HelmRepository | `source.toolkit.fluxcd.io/v1` |
| OCIRepository | `source.toolkit.fluxcd.io/v1beta2` |
| HelmRelease | `helm.toolkit.fluxcd.io/v2` |
| Kustomization (Flux) | `kustomize.toolkit.fluxcd.io/v1` |
| Kustomization (Kustomize) | `kustomize.config.k8s.io/v1beta1` |

## Two Source Patterns

### HelmRepository

For Helm charts published to OCI or HTTPS registries:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
spec:
  type: oci
  url: oci://ghcr.io/stuttgart-things
```

The `release.yaml` contains a `HelmRelease`.

### OCIRepository

For apps shipping their own kustomize manifests as OCI artifacts:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
spec:
  url: oci://ghcr.io/stuttgart-things/<app>-kustomize
  ref:
    tag: ${APP_VERSION:-v0.0.0}
```

The `release.yaml` contains a Flux `Kustomization` (not HelmRelease) and uses `patches:` to override images, remove Ingress, etc.

## Release Ordering

Use `spec.dependsOn` for resources that must be deployed after the main release:

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: my-app-post-config
spec:
  dependsOn:
    - name: my-app
  # ...
```

Examples: cert-manager's ClusterIssuer, MetalLB's IPAddressPool, NFS CSI's StorageClasses.

## Gateway API over Ingress

New components use Gateway API `HTTPRoute` instead of Helm chart ingress fields:

1. Set `INGRESS_ENABLED: "false"` in the HelmRelease values
2. Add a separate `httproute.yaml` with Gateway API resources
3. Use `GATEWAY_NAME`, `GATEWAY_NAMESPACE`, `HOSTNAME`, and `DOMAIN` variables

## Namespace Labels

All namespaces include the Flux tenant label:

```yaml
metadata:
  labels:
    toolkit.fluxcd.io/tenant: sthings-team
```

## Commit Convention

Uses Angular commit convention for semantic-release:

| Prefix | Effect |
|---|---|
| `feat:` | Minor version bump |
| `fix:` | Patch version bump |
| `BREAKING CHANGE` in footer | Major version bump |
| `chore:`, `docs:`, `refactor:` | No version bump |

Tags follow `v${version}` format (e.g., `v1.3.0`).
