# stuttgart-things/flux/infisical

[Infisical](https://infisical.com/docs/self-hosting/helm-charts/overview) (secrets management), deployed from the
`infisical-standalone` Helm chart with its bundled PostgreSQL and Redis, exposed through a Gateway API HTTPRoute.

## Deployment

```bash
kubectl apply -f - <<EOF2
---
apiVersion: v1
kind: Secret
metadata:
  name: infisical-secrets
  namespace: flux-system
type: Opaque
stringData:
  INFISICAL_ENCRYPTION_KEY: "<openssl rand -hex 16>"    # pragma: allowlist secret
  INFISICAL_AUTH_SECRET: "<openssl rand -base64 32>"    # pragma: allowlist secret
  INFISICAL_DB_PASSWORD: "<alnum>"                      # pragma: allowlist secret
  INFISICAL_REDIS_PASSWORD: "<alnum>"                   # pragma: allowlist secret
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infisical
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 15m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/infisical
  prune: true
  wait: true
  postBuild:
    substitute:
      INFISICAL_NAMESPACE: infisical
      INFISICAL_VERSION: "1.11.0"
      INFISICAL_STORAGE_CLASS: nfs4-csi
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: infisical
      DOMAIN: example.sthings-vsphere.labul.sva.de
    substituteFrom:
      - kind: Secret
        name: infisical-secrets
EOF2
```

`INFISICAL_ENCRYPTION_KEY` encrypts every stored secret. Generate it once and keep it: a new key makes the
existing database unreadable. The DB and Redis passwords go into connection URLs the chart builds, so keep them
alphanumeric.

## Variables

| Variable | Default | Description |
|---|---|---|
| `INFISICAL_NAMESPACE` | `infisical` | Target namespace |
| `INFISICAL_VERSION` | `1.11.0` | Helm chart version (`infisical-standalone`) |
| `INFISICAL_IMAGE_TAG` | `v0.158.0` | `infisical/infisical` image tag |
| `INFISICAL_REPLICAS` | `2` | Infisical pod replicas |
| `INFISICAL_STORAGE_CLASS` | `nfs4-csi` | StorageClass for the PostgreSQL and Redis PVCs |
| `INFISICAL_DB_STORAGE_SIZE` | `8Gi` | PostgreSQL PVC size |
| `INFISICAL_REDIS_STORAGE_SIZE` | `2Gi` | Redis PVC size |
| `INFISICAL_ENCRYPTION_KEY` | *(required)* | 16 random bytes, hex |
| `INFISICAL_AUTH_SECRET` | *(required)* | 32 random bytes, base64 |
| `INFISICAL_DB_PASSWORD` | *(required)* | PostgreSQL password |
| `INFISICAL_REDIS_PASSWORD` | *(required)* | Redis password |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute and `SITE_URL` |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute and `SITE_URL` |

## Components

- **requirements.yaml** - Namespace + HelmRepository `https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/`
- **secret.yaml** - `infisical-secrets` (`ENCRYPTION_KEY`, `AUTH_SECRET`, `SITE_URL`), read by the chart via `envFrom`
- **release.yaml** - HelmRelease; chart Ingress and bundled ingress-nginx disabled, Service renamed to `infisical`
- **httproute.yaml** - Gateway API HTTPRoute → `infisical:8080`

The first user to sign up at `https://<HOSTNAME>.<DOMAIN>` becomes the instance admin.

## Bundle

In `apps-platform` select `../components/infisical` (requires `cilium-gateway`, a real
`INFISICAL_STORAGE_CLASS` and the `infisical-secrets` Secret in `flux-system`; an AppProfile generates it).
