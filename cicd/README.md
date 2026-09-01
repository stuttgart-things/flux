# stuttgart-things/flux/cicd

CI/CD and Infrastructure-as-Code components deployed via Flux Kustomizations.

## Components

| Component | Description | Install Method |
|---|---|---|
| [crossplane/capabilities](crossplane/capabilities/) | What a cluster can **do**: ClusterProviderConfig, credentials and placement per environment — one set per lab, credentials from `sops-git` | Capability Helm charts + a written-out Harvester set |
| [crossplane](crossplane/) | Crossplane and one **profile**'s package set — `cicd-platform` (default), or `machinery` **generated from the KCL catalog** — selected with `CROSSPLANE_PROFILE` | Kustomize components composed by per-profile build roots |
| [tekton](tekton/) | Tekton Operator v0.79.0 with TektonConfig CR for Pipelines, Triggers, and Dashboard | Vendored operator manifests + TektonConfig CR |
| [argo-cd](argo-cd/) | Argo CD v9.4.15 with Vault Plugin sidecars for secret injection | Helm chart + optional HTTPRoute |
| [komoplane](komoplane/) | Komoplane — Crossplane resource visualization UI | Helm chart via Flux HelmRelease |
