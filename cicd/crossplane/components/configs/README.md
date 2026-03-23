# crossplane/components/configs

Deploys Crossplane Configurations from the stuttgart-things registry.

**Note:** This component is currently **not included** in the root `kustomization.yaml`. Add it if needed.

## Flux Kustomization

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-configs
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/components/configs
  prune: true
  wait: true
  dependsOn:
    - name: crossplane-install
    - name: crossplane-functions
  postBuild:
    substitute:
      CROSSPLANE_CONFIG_CLOUD_CONFIG_VERSION: v0.5.1
      CROSSPLANE_CONFIG_VOLUME_CLAIM_VERSION: v0.1.1
      CROSSPLANE_CONFIG_STORAGE_PLATFORM_VERSION: v0.6.0
      CROSSPLANE_CONFIG_ANSIBLE_RUN_VERSION: v12.0.0
      CROSSPLANE_CONFIG_PIPELINE_INTEGRATION_VERSION: v0.1.2
      CROSSPLANE_CONFIG_HARVESTER_VM_VERSION: v0.3.3
```

## Resources

| Resource | Kind | Purpose |
|---|---|---|
| `cloud-config` | Configuration | Cloud infrastructure configuration |
| `volume-claim` | Configuration | Volume claim management |
| `storage-platform` | Configuration | Storage platform provisioning |
| `ansible-run` | Configuration | Ansible playbook execution |
| `pipeline-integration` | Configuration | CI/CD pipeline integration |
| `harvester-vm` | Configuration | Harvester VM provisioning |

## Dependencies

- **crossplane-install** - Crossplane core must be running
- **crossplane-functions** - Functions must be available (configurations may reference them in compositions)
