# stuttgart-things/flux/vault

## Main Vault Deployment

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
      INGRESS_ENABLED: "false"
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

## Optional: Autounseal

Deploys `vault-autounseal` from the `unseal` Helm repository into the same vault namespace.
Add a second Kustomization pointing to `./apps/vault/autounseal`.

| Variable | Default | Description |
|---|---|---|
| `VAULT_NAMESPACE` | `vault` | Target namespace |
| `UNSEAL_HELM_REPO_URL` | `https://pytoshka.github.io/vault-autounseal` | URL of the `unseal` Helm repository |
| `VAULT_AUTOUNSEAL_VERSION` | `0.5.3` | Chart version |
| `VAULT_AUTOUNSEAL_URL` | `http://vault-server.vault.svc:8200` | Vault server URL |
| `VAULT_AUTOUNSEAL_LABEL_SELECTOR` | `app.kubernetes.io/component=server` | Label selector for vault pods |

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: vault-autounseal
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/vault/autounseal
  prune: true
  wait: true
  postBuild:
    substitute:
      VAULT_NAMESPACE: vault
      UNSEAL_HELM_REPO_URL: https://pytoshka.github.io/vault-autounseal
      VAULT_AUTOUNSEAL_VERSION: "0.5.3"
      VAULT_AUTOUNSEAL_URL: http://vault-server.vault.svc:8200
      VAULT_AUTOUNSEAL_LABEL_SELECTOR: app.kubernetes.io/component=server
EOF
```

## Optional: HTTPRoute (Gateway API)

Deploys a Gateway API `HTTPRoute` for vault instead of using the Helm chart's built-in ingress.
Keep `INGRESS_ENABLED: "false"` in the main Kustomization and add a second one for the HTTPRoute.

| Variable | Default | Description |
|---|---|---|
| `VAULT_NAMESPACE` | `vault` | Target namespace |
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `VAULT_HOSTNAME` | *(required)* | Hostname prefix |
| `VAULT_DOMAIN` | *(required)* | Domain suffix |

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: vault-httproute
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/vault/httproute
  prune: true
  wait: true
  postBuild:
    substitute:
      VAULT_NAMESPACE: vault
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      VAULT_HOSTNAME: vault
      VAULT_DOMAIN: example.com
EOF
```

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-vault \
-p vaultIngressDomain=example.sthings-vsphere.labul.sva.de \
-p vaultStorageClass=openebs-hostpath \
-p vaultIssuerName=selfsigned \
-o ./apps/ \
--filename-pattern "{{.name}}.yaml"

claims render --non-interactive \
-t flux-kustomization-vault-autounseal \
-o ./apps/ \
--filename-pattern "{{.name}}.yaml"

claims render --non-interactive \
-t flux-kustomization-vault-httproute \
-p vaultHttprouteGatewayName=my-gateway \
-p vaultHttprouteDomain=example.sthings-vsphere.labul.sva.de \
-o ./apps/ \
--filename-pattern "{{.name}}.yaml"
```
