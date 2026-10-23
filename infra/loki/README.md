# stuttgart-things/flux/loki

Central log store: [Loki](https://grafana.com/oss/loki/) in monolithic mode,
TSDB index and chunks on one PVC, one tenant (`auth_enabled: false`). Fed by
[`infra/fluent-bit`](../fluent-bit) on this cluster and on the others.

The chart is the **OSS** `loki` chart from `oci://ghcr.io/grafana-community/helm-charts`.
`grafana/helm-charts`' `loki` is Grafana Enterprise Logs only since 7.0.0; the
OSS chart moved on 2026-03-16 ([grafana/loki#20705](https://github.com/grafana/loki/issues/20705)).

## Layout

```
infra/loki/
├── requirements.yaml      Namespace + HelmRepository (OCI)
├── release.yaml           HelmRelease loki (Monolithic, filesystem)
└── components/
    ├── httproute/          loki.<DOMAIN> on the cluster Gateway -- push from other clusters
    └── grafana-datasource/ Loki datasource for the kube-prometheus-stack Grafana of this cluster
```

Push and query both go through the chart's nginx gateway: in-cluster
`http://loki-gateway.<LOKI_NAMESPACE>.svc.cluster.local`, from outside
`https://<LOKI_HOSTNAME>.<DOMAIN>` (with `components/httproute`). The push
endpoint has no authentication, so keep the route on a lab Gateway.

## Deployment

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: loki
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 15m
  dependsOn:
    - name: cilium-gateway
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/loki
  components:
    - components/httproute
    - components/grafana-datasource
  prune: true
  wait: true
  postBuild:
    substitute:
      LOKI_STORAGE_CLASS: local-path
      LOKI_STORAGE_SIZE: 20Gi
      GATEWAY_NAME: platform-sthings-gateway
      DOMAIN: platform.sthings.lab
```

In a bundle: the `loki` component of [`infra/platform`](../platform) (with
`components/httproute`, without the datasource).

## Variables

| Variable | Default | Description |
|---|---|---|
| `LOKI_NAMESPACE` | `loki` | Target namespace |
| `LOKI_VERSION` | `19.1.0` | Chart version (Loki 3.7.9) |
| `LOKI_STORAGE_CLASS` | `local-path` | StorageClass of the PVC |
| `LOKI_STORAGE_SIZE` | `20Gi` | PVC size |
| `LOKI_RETENTION` | `168h` | Retention, enforced by the compactor |
| `LOKI_HOSTNAME` | `loki` | httproute: hostname |
| `GATEWAY_NAME` | *(required for httproute)* | httproute: Gateway |
| `GATEWAY_NAMESPACE` | `default` | httproute: Gateway namespace |
| `DOMAIN` | *(required for httproute)* | httproute: domain |
| `LOKI_GRAFANA_NAMESPACE` | `monitoring` | grafana-datasource: namespace of the Grafana (its datasource sidecar reads only its own namespace) |

## Querying

```bash
kubectl -n loki port-forward svc/loki-gateway 3100:80
curl -sG localhost:3100/loki/api/v1/label/cluster/values
curl -sG localhost:3100/loki/api/v1/query_range --data-urlencode 'query={cluster="platform"}' | jq '.data.result | length'
```
