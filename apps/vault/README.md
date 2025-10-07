# stuttgart-things/flux/vault

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: vault
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-vault
  path: ./apps/vault
  prune: true
  wait: true
  postBuild:
    substitute:
      VAULT_VERSION: "1.9.0"
      VAULT_NAMESPACE: vault
      REGISTRY: ghcr.io
      REPOSITORY: stuttgart-things/vault
      TAG: 1.20.2-debian-12-r2
      PULL_POLICY: IfNotPresent
      INGRESS_ENABLED: "false"
      INGRESS_CLASS_NAME: nginx
      HOSTNAME: vault
      DOMAIN: example.com
      STORAGE_CLASS: standard
      INJECTOR_ENABLED: "true"
      INJECTOR_REPOSITORY: stuttgart-things/vault-k8s
      INJECTOR_TAG: 1.7.0-debian-12-r4
      INJECTOR_PULL_POLICY: IfNotPresent
      ENABLE_VOLUME_PERMISSIONS: "true"
      OS_SHELL_REPOSITORY: stuttgart-things/os-shell
      OS_SHELL_TAG: 12-debian-12-r50
      OS_SHELL_PULL_POLICY: IfNotPresent
      VAULT_INGRESS_HOSTNAME: vault
      VAULT_INGRESS_DOMAIN: example.com
      ISSUER_NAME: letsencrypt-prod
      ISSUER_KIND: ClusterIssuer
    substituteFrom:
      - kind: Secret
        name: vault
EOF
```