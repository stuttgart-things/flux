# stuttgart-things/flux/headlamp

## Deployment

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: headlamp
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/headlamp
  prune: true
  wait: true
  postBuild:
    substitute:
      HEADLAMP_NAMESPACE: headlamp
      HEADLAMP_VERSION: "0.40.0"
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: headlamp
      DOMAIN: example.sthings-vsphere.labul.sva.de
EOF
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `HEADLAMP_NAMESPACE` | `headlamp` | Target namespace |
| `HEADLAMP_VERSION` | `0.40.0` | Helm chart version |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Authentication

Headlamp requires a ServiceAccount token for login. A `ClusterRoleBinding` granting `cluster-admin` to the `headlamp` ServiceAccount is included in this app (rbac.yaml).

Generate a token:

```bash
kubectl create token headlamp -n headlamp --duration=8760h
```

Paste the token into the headlamp login screen.

## OIDC login (optional)

The `headlamp-oidc` component of `infra/platform` renders this path with a
HelmRelease patch for OIDC login (issuer, client ID, scopes and callback as
env, the client secret from an existing Secret, the issuer's CA from a
ConfigMap); variables in `infra/platform/README.md`. Without it nothing
changes. The settings go through `.Values.env`, not `config.oidc.*`: chart
0.46.0 renders `config.oidc.clientID` unquoted, which breaks digits-only
client IDs.

```bash
kubectl -n headlamp create secret generic headlamp-oidc \
  --from-literal=client-secret=<client secret> --dry-run=client -o yaml
# -> SOPS-encrypt it in the cluster repository
```

Headlamp forwards the user's ID token to the kube-apiserver. The apiserver has
to trust the issuer with the client ID as audience (structured authentication,
`--authentication-config`) and RBAC has to bind the mapped users / groups.

## Components

- **release.yaml** - HelmRelease from `https://kubernetes-sigs.github.io/headlamp/` with chart-native Gateway API HTTPRoute support
- **rbac.yaml** - ClusterRoleBinding granting `cluster-admin` to the headlamp ServiceAccount
- **requirements.yaml** - Namespace and HelmRepository

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-headlamp \
-p headlampGatewayName=my-gateway \
-p headlampDomain=example.sthings-vsphere.labul.sva.de \
-o ./apps/ \
--filename-pattern "{{.name}}.yaml"
```

See also: [claims CLI](https://github.com/stuttgart-things/claims) | [claim-machinery-api](https://github.com/stuttgart-things/claim-machinery-api)
