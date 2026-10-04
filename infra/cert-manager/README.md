# stuttgart-things/flux/infra/cert-manager

The **base** overlay installs only the cert-manager **controller** (namespace +
jetstack `HelmRepository` + cert-manager `HelmRelease`). The legacy Vault
**AppRole** `ClusterIssuer` is an **opt-in component** (`components/approle-issuer`)
— new clusters use a tokenless Kubernetes-auth `ClusterIssuer` provisioned
out-of-band (VaultK8sAuth) and should NOT enable it.

## REQUIREMENTS

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    tag: v1.0.0
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>SECRET (only for the <code>approle-issuer</code> component)</summary>

The base controller install needs **no** Vault secret. These vars are consumed
only by the opt-in `components/approle-issuer` overlay.

```bash
kubectl apply -f - <<EOF
apiVersion: v1
data:
  VAULT_ADDR: <ADD-B64-VALUE>
  VAULT_CA_BUNDLE: <ADD-B64-VALUE>
  VAULT_NAMESPACE: <ADD-B64-VALUE>
  VAULT_PKI_PATH: <ADD-B64-VALUE>
  VAULT_ROLE_ID: <ADD-B64-VALUE>
  VAULT_SECRET_ID: <ADD-B64-VALUE>
  VAULT_TOKEN: <ADD-B64-VALUE>
kind: Secret
metadata:
  labels:
    kustomize.toolkit.fluxcd.io/name: flux-system
    kustomize.toolkit.fluxcd.io/namespace: flux-system
  name: cert-manager-secret
  namespace: flux-system
type: Opaque
EOF
```

</details>


## KUSTOMIZATION (controller only — the default)

No Vault secret required.

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: cert-manager
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/cert-manager
  prune: true
  wait: true
  postBuild:
    substitute:
      CERT_MANAGER_VERSION: v1.19.2
      CERT_MANAGER_NAMESPACE: cert-manager
      CERT_MANAGER_INSTALL_CRDS: "true"
EOF
```

## KUSTOMIZATION (with the legacy AppRole issuer — opt-in)

Adds the `components/approle-issuer` component; needs the `cert-manager-secret`
above.

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: cert-manager
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/cert-manager
  components:
    - ./infra/cert-manager/components/approle-issuer
  prune: true
  wait: true
  postBuild:
    substitute:
      CERT_MANAGER_VERSION: v1.19.2
      CERT_MANAGER_NAMESPACE: cert-manager
      CERT_MANAGER_INSTALL_CRDS: "true"
    substituteFrom:
      - kind: Secret
        name: cert-manager-secret
EOF
```

## COMPONENT `ca-from-secret`: a CA issuer from a CA the cluster provides

`components/ca-from-secret` renders one `ClusterIssuer` with
`spec.ca.secretName`. The CA itself (a `kubernetes.io/tls` Secret with
`tls.crt` and `tls.key`, typically an intermediate) is the cluster's, usually
SOPS-encrypted in the cluster repo, and never in this repo. Certificates then
chain to a root that survives a reinstall. `components/selfsigned`'s
`cluster-ca` does not: it is regenerated with the cluster.

| Variable | Default | Purpose |
|---|---|---|
| `CERT_MANAGER_CA_FROM_SECRET_ISSUER` | `ca-from-secret` | the ClusterIssuer's name |
| `CERT_MANAGER_CA_FROM_SECRET_NAME` | `ca-from-secret` | the CA Secret's name |

The Secret's **namespace is fixed by cert-manager**, not by a variable. A
ClusterIssuer reads it from the cluster resource namespace, which is
cert-manager's own namespace (`CERT_MANAGER_NAMESPACE`, default
`cert-manager`). Until the Secret is there, the issuer stays not-Ready.

In the infra bundle it is the component `cert-manager-ca-from-secret`. To issue
the **gateway wildcard** from that CA, combine it with
`cert-manager-selfsigned`, which already renders the wildcard Certificate, and
point that Certificate at this issuer:

```yaml
  components:
    - ../components/cert-manager-install
    - ../components/cert-manager-selfsigned
    - ../components/cert-manager-ca-from-secret
  postBuild:
    substitute:
      CERT_MANAGER_CA_FROM_SECRET_ISSUER: edge-ca
      CERT_MANAGER_CA_FROM_SECRET_NAME: edge-ca
      CERT_MANAGER_SELFSIGNED_ISSUER: edge-ca   # the wildcard comes from it
```

The selfsigned → `cluster-ca` chain is still created alongside it. A second
wildcard for another domain is `components/extra-certificate` with
`EXTRA_CERT_ISSUER` set to the same issuer.

The Secret comes from a Kustomization of the cluster's own. It has to
`dependsOn: cert-manager-install` (the namespace) and carry the SOPS
`decryption` block. Nothing in the bundle waits on it except this child.

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-cert-manager-install \
-o ./infra/ \
--filename-pattern "{{.name}}.yaml"
```

See also: [claims CLI](https://github.com/stuttgart-things/claims) | [claim-machinery-api](https://github.com/stuttgart-things/claim-machinery-api)
