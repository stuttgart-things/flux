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
    branch: fix/argocd-cm
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>SECRET</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: v1
data:
  ARGO_CD_SERVER_ADMIN_PASSWORD: <ADD-B64-VALUE> # htpasswd format!
  AVP_ROLE_ID: <ADD-B64-VALUE>
  AVP_SECRET_ID: <ADD-B64-VALUE>
  AVP_VAULT_ADDR: <ADD-B64-VALUE>
  VAULT_NAMESPACE: <ADD-B64-VALUE>
  VAULT_ADDR: <ADD-B64-VALUE>
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
      ARGO_CD_NAMESPACE: argo-cd
      SERVICE_TYPE: ClusterIP
      IMAGE_AVP: ghcr.io/stuttgart-things/sthings-avp:1.18.1
      INGRESS_HOSTNAME: argo-cd
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

## VERIFY PLUGINS

```yaml
apiVersion: v1
data:
  argocd-vault-plugin-helm.yaml: |
    apiVersion: argoproj.io/v1alpha1
    kind: ConfigManagementPlugin
    metadata:
      name: argocd-vault-plugin-helm
    spec:
      allowConcurrency: true
      discover:
        find:
          command:
          - sh
          - -c
          - find . -name 'Chart.yaml' && find . -name 'values.yaml'
      generate:
        command:
        - sh
        - -c
        - helm template "${ARGOCD_APP_NAME}" -f <(echo "${ARGOCD_ENV_HELM_VALUES}") --include-crds . -n "${ARGOCD_APP_NAMESPACE}" | argocd-vault-plugin generate -
      init:
        command:
        - sh
        - -c
        - helm dependency update
      lockRepo: false
  argocd-vault-plugin-kustomize.yaml: |
    apiVersion: argoproj.io/v1alpha1
    kind: ConfigManagementPlugin
    metadata:
      name: argocd-vault-plugin-kustomize
    spec:
      allowConcurrency: true
      discover:
        find:
          command:
          - find
          - .
          - -name
          - kustomization.yaml
      generate:
        command:
        - sh
        - -c
        - kustomize build . | argocd-vault-plugin generate -
      lockRepo: false
  argocd-vault-plugin.yaml: |
    apiVersion: argoproj.io/v1alpha1
    kind: ConfigManagementPlugin
    metadata:
      name: argocd-vault-plugin
    spec:
      allowConcurrency: true
      discover:
        find:
          command:
          - sh
          - -c
          - find . -name '*.yaml' | xargs -I {} grep "<path\|avp\.kubernetes\.io" {}
      generate:
        command:
        - argocd-vault-plugin
        - generate
        - .
      lockRepo: false
kind: ConfigMap
metadata:
  annotations:
    meta.helm.sh/release-name: argocd-deployment
    meta.helm.sh/release-namespace: argo-cd
  labels:
    app.kubernetes.io/component: repo-server
    app.kubernetes.io/instance: argocd-deployment
    app.kubernetes.io/managed-by: Helm
    app.kubernetes.io/name: argocd-cmp-cm
    app.kubernetes.io/part-of: argocd
    app.kubernetes.io/version: v2.13.3
    helm.sh/chart: argo-cd-7.7.14
    helm.toolkit.fluxcd.io/name: argocd-deployment
    helm.toolkit.fluxcd.io/namespace: argo-cd
  name: argocd-cmp-cm
  namespace: argo-cd
```
