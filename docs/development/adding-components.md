# Adding Components

How to create a new component in this repository.

## Directory Structure

Create a new directory under `apps/`, `infra/`, or `cicd/`:

```
apps/my-app/
  kustomization.yaml   # Required: composes all other files
  requirements.yaml    # Required: Namespace + HelmRepository/OCIRepository
  release.yaml         # Required: HelmRelease or Flux Kustomization
  pre-release.yaml     # Optional: resources needed before the release
  post-release.yaml    # Optional: resources with dependsOn on the release
  certificate.yaml     # Optional: cert-manager Certificate
  httproute.yaml       # Optional: Gateway API HTTPRoute
```

## Step 1: Create requirements.yaml

Define the namespace and source:

```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: ${MY_APP_NAMESPACE:-my-app}
  labels:
    toolkit.fluxcd.io/tenant: sthings-team
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: my-app
  namespace: ${MY_APP_NAMESPACE:-my-app}
spec:
  type: oci
  interval: 5m0s
  url: oci://ghcr.io/my-org
```

## Step 2: Create release.yaml

For a HelmRelease:

```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: my-app
  namespace: ${MY_APP_NAMESPACE:-my-app}
spec:
  interval: 1h
  chart:
    spec:
      chart: my-app
      version: ${MY_APP_VERSION:-1.0.0}
      sourceRef:
        kind: HelmRepository
        name: my-app
  values:
    # Chart values here
```

For an OCIRepository + Flux Kustomization (see [Conventions](conventions.md#two-source-patterns)).

## Step 3: Create kustomization.yaml

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - requirements.yaml
  - release.yaml
```

Add `pre-release.yaml`, `post-release.yaml`, `httproute.yaml`, etc. as needed.

## Step 4: Add Gateway API HTTPRoute (Recommended)

Prefer Gateway API over Ingress. Set `INGRESS_ENABLED: "false"` in the HelmRelease and add an `httproute.yaml`:

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
  namespace: ${MY_APP_NAMESPACE:-my-app}
spec:
  parentRefs:
    - name: ${GATEWAY_NAME}
      namespace: ${GATEWAY_NAMESPACE:-default}
  hostnames:
    - ${HOSTNAME}.${DOMAIN}
  rules:
    - backendRefs:
        - name: my-app
          port: 80
```

## Step 5: Add a README.md

Include a deployment example with all variables and their defaults. See existing components for reference.

## Step 6: Variable Naming

- Use UPPERCASE with underscores: `MY_APP_VERSION`, `MY_APP_NAMESPACE`
- Always provide defaults where sensible: `${MY_APP_VERSION:-1.0.0}`
- Use the Flux `postBuild.substitute` pattern
- Run `task get-variables` to verify your variables are extractable

## Using the sthings-cluster Helper Chart

For creating arbitrary Kubernetes CRs (Certificates, ClusterIssuers, Secrets), use the `sthings-cluster` chart from `oci://ghcr.io/stuttgart-things`:

```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: my-app-certificate-configuration
  namespace: ${MY_APP_NAMESPACE:-my-app}
spec:
  chart:
    spec:
      chart: sthings-cluster
      version: 0.4.1
      sourceRef:
        kind: HelmRepository
        name: stuttgart-things
  values:
    customresources:
      certificate:
        apiVersion: cert-manager.io/v1
        kind: Certificate
        # ... certificate spec
```
