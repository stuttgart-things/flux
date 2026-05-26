# external-secrets

Two reusable Flux components for ESO on any cluster in this fleet:

| Component | What it ships |
|---|---|
| `components/install/` | `Namespace` + `HelmRepository` + `HelmRelease` for the upstream `external-secrets/external-secrets` chart |
| `components/cluster-store-vault/` | A Vault-backed `ClusterSecretStore` (Kubernetes auth, KV v2). Every field is parameterised via Flux substitution vars — point one or many `Kustomization`s at this component, each substituting a different `VAULT_CSS_NAME` / `VAULT_KV_PATH` / `VAULT_K8S_AUTH_MOUNT_PATH` to stand up multiple CSSes against different Vault mounts |

Component layout matches `infra/cert-manager/components/install/` and is consumed the same way: a per-cluster Flux `Kustomization` (e.g. `clusters/labul/vsphere/platform-sthings/infra/external-secrets-install.yaml` in `stuttgart-things/stuttgart-things`) points at `./infra/external-secrets/components/<name>` and supplies `postBuild.substitute` overrides.

## Prerequisites for `components/cluster-store-vault/`

- ESO controller installed on the target cluster (`components/install/` above)
- On Vault: KV mount + read policy created (`stuttgart-things/stuttgart-things: clusters/labul/vsphere/infra-sthings/vault-homerun2-secrets/`)
- On Vault: Kubernetes auth backend + role bound to that policy (`stuttgart-things/stuttgart-things: clusters/labul/vsphere/<cluster>/vault-k8s-auth/`)
- On target cluster: `vault-pki-ca` Secret in the `cert-manager` namespace holding the Vault server's CA (typical clusterbook output — present on both `homerun2-dev` and `platform-sthings`)

## Substitution variables

| Component | Var | Default | Notes |
|---|---|---|---|
| install | `EXTERNAL_SECRETS_NAMESPACE` | `external-secrets` | Namespace ESO runs in |
| install | `EXTERNAL_SECRETS_VERSION` | `0.20.3` | Chart version |
| install | `EXTERNAL_SECRETS_INSTALL_CRDS` | `true` | Chart's CRD install toggle |
| cluster-store-vault | `VAULT_CSS_NAME` | `vault-homerun2-cd` | `metadata.name` of the rendered CSS |
| cluster-store-vault | `VAULT_SERVER` | `https://vault.infra.sthings-vsphere.labul.sva.de` | Vault URL |
| cluster-store-vault | `VAULT_KV_PATH` | `homerun2-cd` | KV v2 mount path |
| cluster-store-vault | `VAULT_CA_SECRET_NAME` | `vault-pki-ca` | CA Secret name (in `cert-manager` ns) |
| cluster-store-vault | `VAULT_CA_SECRET_NAMESPACE` | `cert-manager` | CA Secret namespace |
| cluster-store-vault | `VAULT_CA_SECRET_KEY` | `ca.crt` | Key inside the CA Secret |
| cluster-store-vault | `VAULT_K8S_AUTH_MOUNT_PATH` | `platform-sthings-eso` | Vault k8s auth mount path |
| cluster-store-vault | `VAULT_K8S_AUTH_ROLE` | `eso` | Auth role name on Vault |
| cluster-store-vault | `VAULT_K8S_AUTH_SA_NAME` | `eso` | SA name on the cluster |
| cluster-store-vault | `VAULT_K8S_AUTH_SA_NAMESPACE` | `external-secrets` | SA namespace on the cluster |
