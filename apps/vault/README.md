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
    name: flux-apps
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
      PULL_POLICY: Always
      INGRESS_ENABLED: "true"
      INGRESS_CLASS_NAME: nginx
      STORAGE_CLASS: openebs-hostpath
      INJECTOR_ENABLED: "true"
      INJECTOR_REPOSITORY: stuttgart-things/vault-k8s
      INJECTOR_TAG: 1.7.0-debian-12-r4
      INJECTOR_PULL_POLICY: Always
      ENABLE_VOLUME_PERMISSIONS: "true"
      OS_SHELL_REPOSITORY: stuttgart-things/os-shell
      OS_SHELL_TAG: 12-debian-12-r50
      OS_SHELL_PULL_POLICY: Always
      VAULT_INGRESS_HOSTNAME: vault
      VAULT_INGRESS_DOMAIN: demo-infra.sthings-vsphere.example.com
      ISSUER_NAME: cluster-issuer-approle
      ISSUER_KIND: ClusterIssuer
EOF
```



helm upgrade --install vault-autounseal unseal/vault-autounseal --set=settings.vault_url=http://vault-server.vault.svc:8200 --set="settings.vault_label_selector=app.kubernetes.io/component=server" --version 0.5.3 -n vault