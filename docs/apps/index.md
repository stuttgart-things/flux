# Apps

Application HelmReleases and OCI kustomizations.

## Components

| Component | Source Pattern | Chart / OCI Artifact | Default Version |
|---|---|---|---|
| [Argo CD](argo-cd.md) | HelmRepository | `argo-cd` | `7.7.14` |
| [Claim Machinery API](claim-machinery-api.md) | OCIRepository | `claim-machinery-api-kustomize` | `v0.5.6` |
| [Clusterbook](clusterbook.md) | HelmRepository (OCI) | `clusterbook` | `v1.3.1-chart` |
| [Flux Web](flux-web.md) | HelmRepository (OCI) | `flux-operator` | `0.43.0` |
| [Headlamp](headlamp.md) | HelmRepository | `headlamp` | `0.40.0` |
| [Homepage](homepage.md) | HelmRepository (OCI) | `homepage` | `4.8.0` |
| [Homerun Base Stack](homerun-base-stack.md) | HelmRepository (OCI) | `homerun` | `v0.1.2` |
| [Homerun IoT Stack](homerun-iot-stack.md) | HelmRepository (OCI) | `homerun` | `v0.2.0` |
| [Keycloak](keycloak.md) | HelmRepository (OCI) | `keycloak` | `24.4.9` |
| [MinIO](minio.md) | HelmRepository (OCI) | `minio` | `16.0.10` |
| [OpenLDAP](openldap.md) | HelmRepository | `openldap-stack-ha` | `v4.3.2` |
| [Uptime Kuma](uptime-kuma.md) | HelmRepository | `uptime-kuma` | `4.0.0` |
| [Vault](vault.md) | HelmRepository (OCI) | `vault` | `1.9.0` |
| [vCluster](vcluster.md) | HelmRepository | `vcluster` | `0.29.1` |

## Source Patterns

- **HelmRepository**: Points to a Helm chart registry. `release.yaml` contains a `HelmRelease`.
- **HelmRepository (OCI)**: Same as above but using an OCI registry URL (`oci://...`).
- **OCIRepository**: Points to a kustomize OCI artifact. `release.yaml` contains a Flux `Kustomization` with patches.

See [Conventions](../development/conventions.md#two-source-patterns) for details.
