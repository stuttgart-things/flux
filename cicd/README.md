# stuttgart-things/flux/cicd

CI/CD and Infrastructure-as-Code components deployed via Flux Kustomizations.

## Components

| Component | Description | Install Method |
|---|---|---|
| [crossplane](crossplane/) | Crossplane with Helm, K8s, and OpenTofu providers + Functions and Configurations | Kustomize components (install, functions, configs) |
| [tekton](tekton/) | Tekton Operator v0.79.0 with TektonConfig CR for Pipelines, Triggers, and Dashboard | Vendored operator manifests + TektonConfig CR |
| [komoplane](komoplane/) | Komoplane — Crossplane resource visualization UI | Helm chart via Flux HelmRelease |
