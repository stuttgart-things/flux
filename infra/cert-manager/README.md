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

## `letsencrypt-hetzner`: Let's Encrypt via DNS-01 at Hetzner DNS

`letsencrypt-hetzner/` is a path for a Kustomization of its own (it needs
cert-manager running). It renders:

- `HelmRepository` `hcloud` + `HelmRelease` `cert-manager-webhook-hetzner`
  (chart `cert-manager-webhook-hetzner` from `https://charts.hetzner.cloud`):
  the DNS-01 solver, groupName `acme.hetzner.com`, solverName `hetzner`;
- `ClusterIssuer`s `letsencrypt-staging-hetzner` and `letsencrypt-hetzner`
  (Let's Encrypt staging and production);
- `Secret` `hetzner-dns` (key `token`) in cert-manager's namespace, rendered
  from `HETZNER_DNS_TOKEN`, which the consuming Kustomization reads from a
  `substituteFrom` Secret (SOPS-encrypted in the cluster repo).

DNS-01 needs no inbound access: cert-manager writes the `_acme-challenge` TXT
record through the Hetzner Cloud API and Let's Encrypt checks it publicly, so
it also works for a cluster nobody can reach from outside. The token is a
Hetzner Cloud API token (Read & Write). A token is project-wide, so give the
zone a project of its own.

| Variable | Default | Purpose |
|---|---|---|
| `HETZNER_DNS_TOKEN` | *(required, none)* | the Hetzner Cloud API token |
| `LETSENCRYPT_HETZNER_TOKEN_SECRET` | `hetzner-dns` | the token Secret's name |
| `LETSENCRYPT_HETZNER_ISSUER` | `letsencrypt-hetzner` | production ClusterIssuer |
| `LETSENCRYPT_HETZNER_STAGING_ISSUER` | `letsencrypt-staging-hetzner` | staging ClusterIssuer |
| `LETSENCRYPT_HETZNER_WEBHOOK_VERSION` | `0.9.0` | the webhook chart |
| `LETSENCRYPT_HETZNER_ACME_EMAIL` | `none` | the ACME account email, read only with `components/acme-email-set` |
| `CERT_MANAGER_NAMESPACE` | `cert-manager` | where the release, the repository and the Secret go |

The ACME email is a slot rather than a variable that may be empty:
`components/acme-email-none` (no email, the default; Let's Encrypt no longer
sends expiry mails) or `components/acme-email-set`, which adds `spec.acme.email`
to both issuers. An empty substitution would render a YAML null, so the field
has to be added by a patch.

Start every new Certificate on the staging issuer (generous rate limits), then
switch it to production. In the infra bundle this is the component
`cert-manager-letsencrypt-hetzner`
([infra/platform README](../platform/README.md#cert-manager-letsencrypt-hetzner)).

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-cert-manager-install \
-o ./infra/ \
--filename-pattern "{{.name}}.yaml"
```

See also: [claims CLI](https://github.com/stuttgart-things/claims) | [claim-machinery-api](https://github.com/stuttgart-things/claim-machinery-api)
