# Skill: create-flux-app

Create a new Flux CD app/infra component following the repository's standard structure.

## Trigger

When the user asks to create/add a new Flux app, infra component, or cicd component.

## Gather Information

Ask the user (if not already provided):

1. **Component name** (e.g., `grafana`)
2. **Category**: `apps/`, `infra/`, or `cicd/`
3. **Source type**: HelmRepository (OCI or HTTPS) or OCIRepository
4. **Chart/OCI URL** and default version
5. **Namespace** name and variable prefix (e.g., `GRAFANA_NAMESPACE`)
6. **Optional files needed**: httproute, certificate/pre-release, post-release
7. **Helm values** to parameterize with variables

## File Generation

### Always create these files:

#### `README.md`
Always generate a README with:
1. Title: `# stuttgart-things/flux/<component-name>`
2. A **SECRETS MANIFEST (SOPS ENCRYPTED)** section (if the app uses secrets like passwords/tokens) showing the plaintext Secret YAML, the `sops --encrypt` command with age, and the equivalent `dagger call -m github.com/stuttgart-things/dagger/sops@v0.82.1 encrypt/decrypt` commands
3. A **GIT-REPOSITORY MANIFEST** section with a `kubectl apply` example creating the `flux-apps` GitRepository source in `flux-system` namespace (the Kustomization references this as `sourceRef`)
4. A **KUSTOMIZATION EXAMPLE** section with a `kubectl apply` example showing the full Kustomization manifest including all `postBuild.substitute` variables with sensible example values
5. If the app has optional sub-components, add separate sections for each

Follow the pattern from existing READMEs (e.g., `homerun-base-stack/README.md`, `vault/README.md`).

#### `kustomization.yaml`
```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - requirements.yaml
  - release.yaml
  # Only include files that actually exist:
  # - pre-release.yaml
  # - post-release.yaml
  # - certificate.yaml
  # - httproute.yaml
```

#### `requirements.yaml`
Always include a Namespace and a source. Use current API versions.

For **HelmRepository (OCI)**:
```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: ${<PREFIX>_NAMESPACE:-<default-ns>}
  labels:
    toolkit.fluxcd.io/tenant: sthings-team
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: <repo-name>
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  type: oci
  interval: 1h
  url: oci://<registry-url>
```

For **HelmRepository (HTTPS)**:
```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: ${<PREFIX>_NAMESPACE:-<default-ns>}
  labels:
    toolkit.fluxcd.io/tenant: sthings-team
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: <repo-name>
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  interval: 1h
  url: https://<chart-repo-url>
```

For **OCIRepository**:
```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: ${<PREFIX>_NAMESPACE:-<default-ns>}
  labels:
    toolkit.fluxcd.io/tenant: sthings-team
---
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: <app>-kustomize
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  interval: 1h
  url: oci://<registry>/<app>-kustomize
  ref:
    tag: ${<PREFIX>_VERSION:-v0.0.0}
```

#### `release.yaml`

For **HelmRelease** (when using HelmRepository):
```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <app-name>
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  interval: 30m
  chart:
    spec:
      chart: <chart-name>
      version: ${<PREFIX>_VERSION:-<default-version>}
      sourceRef:
        kind: HelmRepository
        name: <repo-name>
        namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
      interval: 12h
  values:
    # Chart-specific values with ${VAR:-default} substitution
```

For **Kustomization** (when using OCIRepository):
```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: <app-name>
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: OCIRepository
    name: <app>-kustomize
  prune: true
  wait: true
  targetNamespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
  patches: []
```

### Optional files (only create if requested):

#### `httproute.yaml` (Gateway API — preferred over Ingress)
```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: <app-name>
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  parentRefs:
    - name: ${GATEWAY_NAME}
      namespace: ${GATEWAY_NAMESPACE:-default}
  hostnames:
    - "${HOSTNAME}.${DOMAIN}"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: <service-name>
          port: <service-port>
```

#### `pre-release.yaml` (Certificates or pre-requisites via sthings-cluster)
```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <app>-certificate-configuration
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  interval: 30m
  chart:
    spec:
      chart: sthings-cluster
      version: 0.3.20
      sourceRef:
        kind: HelmRepository
        name: stuttgart-things
        namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
      interval: 12h
  values:
    customresources:
      ingress-certificate:
        apiVersion: cert-manager.io/v1
        kind: Certificate
        metadata:
          name: <app>-ingress
          namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
        spec:
          commonName: ${INGRESS_HOSTNAME}.${INGRESS_DOMAIN}
          dnsNames:
            - ${INGRESS_HOSTNAME}.${INGRESS_DOMAIN}
          issuerRef:
            name: ${CLUSTER_ISSUER}
            kind: ClusterIssuer
          secretName: ${INGRESS_HOSTNAME}-ingress-tls
```

When using `pre-release.yaml` with certificates, add `stuttgart-things` HelmRepository to `requirements.yaml` if not already present.

#### `post-release.yaml` (resources that depend on the main release)
```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <app>-configuration
  namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
spec:
  interval: 30m
  dependsOn:
    - name: <app>
      namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
  chart:
    spec:
      chart: sthings-cluster
      version: 0.3.20
      sourceRef:
        kind: HelmRepository
        name: stuttgart-things
        namespace: ${<PREFIX>_NAMESPACE:-<default-ns>}
      interval: 12h
  values:
    customresources: {}
```

## Rules

- **API versions**: Use `helm.toolkit.fluxcd.io/v2` (NOT v2beta1) and `source.toolkit.fluxcd.io/v1`
- **Variable syntax**: Always `${VAR_NAME:-default}` (colon-dash). NEVER use `${VAR:default}` or `${VAR:=default}`
- **Variable naming**: UPPERCASE with underscores, prefixed with app name (e.g., `GRAFANA_NAMESPACE`, `GRAFANA_VERSION`)
- **Namespace variable**: Must be consistent across ALL files in the component — same variable name everywhere
- **Tenant label**: Always `toolkit.fluxcd.io/tenant: sthings-team`
- **Ingress strategy**: Prefer Gateway API HTTPRoute (`httproute.yaml`) over Helm chart ingress fields. Set `ingress.enabled: false` in HelmRelease values when using HTTPRoute.
- **sthings-cluster chart**: Use for creating arbitrary CRs (Certificates, ClusterIssuers, Secrets) via HelmRelease values under `customresources:` or `secrets:`
- Only include files in `kustomization.yaml` that actually exist
- Keep the component self-contained — all resources in one directory
