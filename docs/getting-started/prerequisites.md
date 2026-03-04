# Prerequisites

## Required Tools

| Tool | Purpose | Install |
|---|---|---|
| `kubectl` | Kubernetes CLI | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools/) |
| `flux` | Flux CLI for bootstrap and debugging | [fluxcd.io/flux/installation](https://fluxcd.io/flux/installation/) |
| `helm` | Helm CLI (for Flux Operator install) | [helm.sh/docs/intro/install](https://helm.sh/docs/intro/install/) |
| `task` | go-task runner (replaces Make) | [taskfile.dev/installation](https://taskfile.dev/installation/) |

## Optional Tools

| Tool | Purpose |
|---|---|
| `dagger` | Run Dagger modules for SOPS encryption and KCL rendering |
| `helmfile` | Legacy Helmfile-based deployments |
| `gum` | Interactive task picker (`task do`) |
| `npx` | Run semantic-release for versioning |
| `pre-commit` | Git hook framework for validation |
| `age` / `sops` | Local secret encryption/decryption |

## Cluster Requirements

- A running Kubernetes cluster (v1.26+)
- `kubeconfig` with cluster-admin access
- Network access to `ghcr.io` for pulling OCI artifacts

## Repository Access

For private repository bootstrapping, you need:

- A GitHub personal access token with `repo` scope
- Export it as `GITHUB_TOKEN` in your shell

## SOPS Encryption (Optional)

If you need to manage encrypted secrets:

- An Age keypair (`age-keygen`)
- The public key for encrypting, the private key for Flux decryption
- See [SOPS Secrets](../bootstrap/sops-secrets.md) for details
