# stuttgart-things/flux/apps/argo-cd

## REQUIREMENTS

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: add-argocd-app
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    tag: v1.0.0
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>SECRET</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: v1
data:
  ARGO_CD_SERVER_ADMIN_PASSWORD: JDJhJDEwJFRXSHNhY05Bc1dkUXh3N0xjTFZWb09VTjRVd2lIQVFYY2Y1SFAxd2RUc3NSelZ4MlZJMGQ2
kind: Secret
metadata:
  labels:
    kustomize.toolkit.fluxcd.io/name: flux-system
    kustomize.toolkit.fluxcd.io/namespace: flux-system
  name: argocd-secrets
  namespace: flux-system
type: Opaque
EOF
```

</details>

## KUSTOMIZATION

```bash
kubectl apply -f - <<EOF
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: argo-cd
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: add-argocd-app
  path: ./apps/argo-cd
  prune: true
  wait: true
  postBuild:
    substitute:
      ARGO_CD_VERSION: 7.7.14
      ARGO_CD_NAMESPACE: argocd
      SERVICE_TYPE: ClusterIP
      IMAGE_AVP: ghcr.io/stuttgart-things/sthings-avp:1.18.1
      INGRESS_HOSTNAME: argocd
      INGRESS_DOMAIN: homerun-int.sthings-vsphere.labul.sva.de
      INGRESS_SECRET_NAME: argocd-server-tls
      ISSUER_NAME: cluster-issuer-approle
      ISSUER_KIND: ClusterIssuer
      ARGO_CD_PASSWORD_MTIME: 2024-09-16T12:51:06UTC
    substituteFrom:
      - kind: Secret
        name: argocd-secrets
EOF
```
