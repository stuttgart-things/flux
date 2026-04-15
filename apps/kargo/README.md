# stuttgart-things/flux/kargo

Deploys [Kargo](https://github.com/akuity/kargo) from the Akuity OCI Helm registry
(`oci://ghcr.io/akuity/kargo-charts/kargo`) via Flux.

Equivalent of:

```bash
helm install kargo \
  oci://ghcr.io/akuity/kargo-charts/kargo \
  --namespace kargo \
  --create-namespace \
  --set api.adminAccount.passwordHash=$hashed_pass \
  --set api.adminAccount.tokenSigningKey=$signing_key \
  --wait
```

## Requirements

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
    branch: main
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>CREATE SECRET</summary>

The admin credentials contain `$` characters (bcrypt hashes) that collide with
Flux's `postBuild.substitute` envsubst-style expansion. Pass them through a
Kubernetes `Secret` and `substituteFrom` instead of inlining them — Flux reads
secret values literally, no escaping required.

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: kargo-secrets
  namespace: flux-system
type: Opaque
stringData:
  KARGO_ADMIN_PASSWORD_HASH: '<bcrypt-hash>' # pragma: allowlist secret
  KARGO_ADMIN_TOKEN_SIGNING_KEY: '<random-signing-key>' # pragma: allowlist secret
EOF
```

Generate the values:

```bash
# Password hash (bcrypt, $2a$ variant)
htpasswd -bnBC 10 "" '<your-password>' | tr -d ':\n' | sed 's/$2y/$2a/'

# Token signing key
openssl rand -base64 29 | tr -d "=+/" | head -c 32
```

</details>

## Main Kargo Deployment

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: kargo
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/kargo
  prune: true
  wait: true
  postBuild:
    substitute:
      KARGO_NAMESPACE: kargo
      KARGO_VERSION: "1.9.6"
      KARGO_HOSTNAME: kargo
      KARGO_DOMAIN: example.sthings-vsphere.example.com
      KARGO_ADMIN_TOKEN_TTL: 24h
      KARGO_SERVICE_TYPE: ClusterIP
      KARGO_API_TLS_ENABLED: "false"
      KARGO_INGRESS_TLS_ENABLED: "true"
      KARGO_LOG_LEVEL: INFO
      KARGO_WEBHOOKS_SELF_SIGNED_CERT: "true"
      INGRESS_ENABLED: "false"
      INGRESS_CLASS_NAME: nginx
      ISSUER_NAME: cluster-issuer-approle
      ISSUER_KIND: ClusterIssuer
    substituteFrom:
      - kind: Secret
        name: kargo-secrets
EOF
```

`KARGO_ADMIN_PASSWORD_HASH` and `KARGO_ADMIN_TOKEN_SIGNING_KEY` come from the
`kargo-secrets` Secret via `substituteFrom` — do **not** inline them under
`substitute:`, as the `$` characters in the bcrypt hash would be mangled by
envsubst.

## Optional: HTTPRoute (Gateway API)

Deploys a Gateway API `HTTPRoute` for kargo instead of using the Helm chart's
built-in ingress. Keep `INGRESS_ENABLED: "false"` in the main Kustomization and
add a second one for the HTTPRoute.

| Variable | Default | Description |
|---|---|---|
| `KARGO_NAMESPACE` | `kargo` | Target namespace |
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `KARGO_HOSTNAME` | `kargo` | Hostname prefix |
| `KARGO_DOMAIN` | *(required)* | Domain suffix |

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: kargo-httproute
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/kargo/httproute
  prune: true
  wait: true
  postBuild:
    substitute:
      KARGO_NAMESPACE: kargo
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      KARGO_HOSTNAME: kargo
      KARGO_DOMAIN: example.com
EOF
```
