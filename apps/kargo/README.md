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
      KARGO_VERSION: "1.3.0"
      KARGO_HOSTNAME: kargo
      KARGO_DOMAIN: example.sthings-vsphere.example.com
      KARGO_ADMIN_PASSWORD_HASH: "<bcrypt-hash>"
      KARGO_ADMIN_TOKEN_SIGNING_KEY: "<random-signing-key>"
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
EOF
```

## Generating admin credentials

```bash
# Password hash (bcrypt)
htpasswd -bnBC 10 "" <your-password> | tr -d ':\n' | sed 's/$2y/$2a/'

# Token signing key
openssl rand -base64 29 | tr -d "=+/" | head -c 32
```

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
