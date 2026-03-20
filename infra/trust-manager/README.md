# stuttgart-things/flux/trust-manager

Deploys [trust-manager](https://cert-manager.io/docs/trust/trust-manager/) via HelmRelease and creates a `Bundle` that merges default public CAs with the cluster's own CA certificate.

## SUBSTITUTION VARIABLES

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `TRUST_MANAGER_NAMESPACE` | `cert-manager` | no | Target namespace |
| `TRUST_MANAGER_VERSION` | `0.22.0` | no | Helm chart version |
| `TRUST_MANAGER_TRUST_NAMESPACE` | `cert-manager` | no | Namespace used as trust source |
| `TRUST_BUNDLE_NAME` | `cluster-trust-bundle` | no | Bundle resource name |
| `TRUST_BUNDLE_CA_SECRET` | `cluster-ca-secret` | no | Secret containing the cluster CA |
| `TRUST_BUNDLE_CA_KEY` | `ca.crt` | no | Key within the CA secret |
| `TRUST_BUNDLE_TARGET_KEY` | `trust-bundle.pem` | no | Key in the distributed ConfigMap |

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    tag: v1.1.0
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: trust-manager
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./infra/trust-manager
  prune: true
  wait: true
  postBuild:
    substitute:
      TRUST_MANAGER_NAMESPACE: cert-manager
      TRUST_MANAGER_VERSION: "0.22.0"
      TRUST_BUNDLE_CA_SECRET: cluster-ca-secret
      TRUST_BUNDLE_CA_KEY: ca.crt
      TRUST_BUNDLE_TARGET_KEY: trust-bundle.pem
EOF
```

## HOW IT WORKS

1. **Requirements** (`requirements.yaml`) creates the namespace and HelmRepository sources
2. **Release** (`release.yaml`) installs trust-manager via the jetstack Helm chart
3. **Post-release** (`post-release.yaml`) uses `sthings-cluster` to create a `Bundle` that merges the default public CA trust store with the cluster CA from `cluster-ca-secret`, distributing a combined `trust-bundle.pem` ConfigMap to all namespaces

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-trust-manager \
-p "dependsOnNames=cert-manager-install" \
-o ./infra/ \
--filename-pattern "{{.name}}.yaml"
```
