# Bootstrap with Flux CLI

The simplest way to get Flux running on a cluster.

## Prerequisites

- `flux` CLI installed
- `GITHUB_TOKEN` with `repo` scope exported
- `kubeconfig` pointing at the target cluster

## Bootstrap

```bash
export KUBECONFIG=<path-to-kubeconfig>
export GITHUB_TOKEN=<your-token>

flux bootstrap github \
  --owner=stuttgart-things \
  --repository=stuttgart-things \
  --path=clusters/<your-cluster>
```

This will:

1. Install Flux components on the cluster
2. Create the repository structure if it doesn't exist
3. Configure Flux to sync from `clusters/<your-cluster>`

## Limitations

- Does not configure SOPS decryption automatically (use [Flux Operator](flux-operator.md) for that)
- Does not set concurrency tuning on controllers
- Less control over component selection

## Next Steps

After bootstrap, add a [GitRepository](../getting-started/quick-start.md#2-add-the-gitrepository) pointing to this repo and create Kustomizations for your components.
