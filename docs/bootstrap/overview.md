# Bootstrap Overview

There are three ways to bootstrap Flux on a Kubernetes cluster. Choose the method that best fits your workflow.

## Method Comparison

| Method | Complexity | Best For |
|---|---|---|
| [Flux Operator](flux-operator.md) | Medium | Production clusters with full control |
| [Flux CLI](flux-cli.md) | Low | Quick setup, dev clusters |
| [Blueprints (Dagger + KCL)](blueprints.md) | High | Automated/reproducible provisioning |

## Flux Operator (Recommended)

Install the Flux Operator via Helm, create secrets for Git and SOPS, then apply a `FluxInstance` CR. This gives full control over Flux components and SOPS decryption configuration.

See [Flux Operator](flux-operator.md) for step-by-step instructions.

## Flux CLI

Use `flux bootstrap github` for the simplest setup. The CLI handles creating the repository structure and deploying Flux components.

See [Flux CLI](flux-cli.md) for details.

## Blueprints (Dagger + KCL)

Render a complete `FluxInstance` manifest using Dagger and KCL. This approach is ideal for automated cluster provisioning pipelines.

See [Blueprints](blueprints.md) for the Dagger module usage.

## After Bootstrap

Once Flux is running, add a `GitRepository` pointing to this repo and create `Kustomization` resources for each component you want to deploy. See [Quick Start](../getting-started/quick-start.md).
