# stuttgart-things/flux/clusterbook

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
  name: clusterbook
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: clusterbook
      namespace: clusterbook
  path: ./apps/clusterbook
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTERBOOK_NAMESPACE: clusterbook
      CLUSTERBOOK_VERSION: v1.3.1-chart
      HOSTNAME: clusterbook
      DOMAIN: fluxdev-3.sthings-vsphere.labul.example.com
      ISSUER_TYPE: ClusterIssuer
      ISSUER_NAME: cluster-issuer-approle
      TLS_SECRET_NAME: homerun-generic-pitcher-ingress-tls
EOF
```

## EXMAPLE CONFIG

```bash
kubectl apply -f - <<EOF
---
apiVersion: github.stuttgart-things.com/v1
kind: NetworkConfig
metadata:
  name: networks-labul
  namespace: clusterbook
spec:
  networks:
    10.31.101:
    - 5:ASSIGNED:rancher-mgmt
    - "6"
    - "7"
    - 8:ASSIGNED:tockeck
    - "9"
    10.31.103:
    - "4"
    - "5"
    - 8:ASSIGNED:fluxdev-3
    - 9:ASSIGNED:fluxdev-3
EOF
```

homerun-dev:
10.31.103.19
10.31.103.15
10.31.103.16
10.31.103.17
10.31.103.18

fluxdev-3:
10.31.101.8
10.31.101.9

rancher-mgmt:
10.31.101.5
