# stuttgart-things/flux/claim-machinery-api

OCI kustomize-based app using `OCIRepository` + Flux `Kustomization` with Gateway API `HTTPRoute`.

## SUBSTITUTION VARIABLES

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `CLAIM_MACHINERY_API_NAMESPACE` | `claim-machinery` | no | Target namespace |
| `CLAIM_MACHINERY_API_VERSION` | `v0.10.0` | no | OCI tag + container image tag |
| `GATEWAY_NAME` | - | yes | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | no | Gateway parentRef namespace |
| `HOSTNAME` | - | yes | HTTPRoute hostname prefix |
| `DOMAIN` | - | yes | HTTPRoute domain suffix |
| `CLAIM_MACHINERY_PROFILE_PATH` | `/app/config/profile.yaml` | no | Override to HTTP URL serving profile.yaml |
| `CLAIM_MACHINERY_ENABLE_HOMERUN` | `false` | no | Enable homerun2 notifications (`true`/`1`/`yes`) |
| `CLAIM_MACHINERY_HOMERUN_URL` | - | no | Omni-pitcher base URL (required when homerun enabled) |
| `CLAIM_MACHINERY_HOMERUN_AUTH_TOKEN` | - | no | Bearer token for pitcher `/pitch` endpoint |
| `CLAIM_MACHINERY_CA_SECRET_NAME` | `cluster-ca-secret` | no | Secret containing the CA certificate for TLS trust |
| `CLAIM_MACHINERY_CA_SECRET_KEY` | `ca.crt` | no | Key within the CA secret |
| `CLAIM_MACHINERY_SSL_CERT_DIR` | `/etc/ssl/custom` | no | Directory to mount the CA cert into (sets `SSL_CERT_DIR`) |
| `CLAIM_MACHINERY_CA_ISSUER_NAME` | `vault-pki` | no | cert-manager ClusterIssuer for the CA certificate |
| `CLAIM_MACHINERY_CA_ISSUER_KIND` | `ClusterIssuer` | no | Issuer kind (`ClusterIssuer` or `Issuer`) |

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
  name: claim-machinery-api
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./apps/claim-machinery-api
  prune: true
  wait: true
  postBuild:
    substitute:
      CLAIM_MACHINERY_API_NAMESPACE: claim-machinery
      CLAIM_MACHINERY_API_VERSION: v0.10.0
      GATEWAY_NAME: whatever-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: claim-api
      DOMAIN: whatever.sthings-vsphere.labul.sva.de
      CLAIM_MACHINERY_PROFILE_PATH: https://raw.githubusercontent.com/stuttgart-things/claim-machinery-api/refs/heads/main/profiles/labul-vsphere.yaml
      # Optional: homerun2 notifications
      CLAIM_MACHINERY_ENABLE_HOMERUN: "true"
      CLAIM_MACHINERY_HOMERUN_URL: https://pitcher.example.sthings-vsphere.labul.sva.de
      # CLAIM_MACHINERY_HOMERUN_AUTH_TOKEN: "<from substituteFrom secret>"
      # Optional: TLS trust for internal Vault PKI CA
      # A cert-manager Certificate is created via pre-release to provide the CA cert
      CLAIM_MACHINERY_CA_SECRET_NAME: cluster-ca-secret
      CLAIM_MACHINERY_CA_SECRET_KEY: ca.crt
      CLAIM_MACHINERY_SSL_CERT_DIR: /etc/ssl/custom
EOF
```

> **Note:** When the homerun pitcher is reachable via a cluster-internal service URL
> (e.g. `http://homerun2-omni-pitcher.homerun2.svc.cluster.local`), no CA certificate
> is needed and the `CLAIM_MACHINERY_CA_*` variables can be omitted. The CA volume mount
> is configured with `optional: true` so the pod starts fine without the secret.

## HOW IT WORKS

Two-layer Flux reconciliation:

1. **Outer Kustomization** (above) reads `./apps/claim-machinery-api` from the GitRepository, substitutes variables, and creates the Namespace + HelmRepository + OCIRepository + pre-release HelmRelease + inner Kustomization + HTTPRoute on the cluster
2. **Pre-release HelmRelease** (`pre-release.yaml`) uses `sthings-cluster` to create a cert-manager Certificate in the target namespace, issued by the configured ClusterIssuer (default: `vault-pki`). The resulting secret contains the CA certificate needed for TLS trust
3. **Inner Kustomization** (`release.yaml`) reconciles the OCI kustomize base from `ghcr.io/stuttgart-things/claim-machinery-api-kustomize`, patches out the Ingress (replaced by HTTPRoute), overrides the container image tag, mounts the CA certificate volume, and applies the resulting manifests
