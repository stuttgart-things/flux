# stuttgart-things/flux/dapr-backstage-template-execution-trigger

The kro `ResourceGraphDefinition` `backstage-template-run`, which defines the
`BackstageTemplateRun` kind: one CR starts one run of the
`backstage-template-execution` worker. Source and docs:
[stuttgart-things/dapr-workflows `workflows/backstage-template-execution/trigger`](https://github.com/stuttgart-things/dapr-workflows/tree/main/workflows/backstage-template-execution/trigger).

## Where it comes from

Every dapr-workflows release publishes the RGD alone, next to the worker's
kustomize base and under the same tag with a `-trigger` suffix:

```
oci://ghcr.io/stuttgart-things/dapr-backstage-template-execution-kustomize:<release-tag>          # worker
oci://ghcr.io/stuttgart-things/dapr-backstage-template-execution-kustomize:<release-tag>-trigger  # this
```

The RGD and the worker are one interface — the trigger Job posts the payload
the worker reads — so a cluster pins both from one release.

## Layout

- `requirements.yaml` — OCIRepository at `${DAPR_BACKSTAGE_TPL_TRIGGER_TAG}`
- `release.yaml` — Kustomization applying the artifact, **without**
  `postBuild.substitute`: the RGD is full of kro `${...}` expressions that
  substitution would destroy

## Selecting it

Through the cicd bundle: component `dapr-workflows-trigger`, which orders
itself behind `kro` and `dapr-workflows`.

| Variable | Default | Description |
|----------|---------|-------------|
| `DAPR_WORKFLOWS_NAMESPACE` | `backstage-workflows` | Namespace of the OCIRepository and Kustomization (the RGD is cluster-scoped) |
| `DAPR_WORKFLOWS_TRIGGER_TAG` | `<release-tag>-trigger` | Move it together with `DAPR_WORKFLOWS_VERSION` / `DAPR_WORKFLOWS_IMAGE_TAG` |

A cluster that applied the RGD by hand before needs nothing else: Flux takes
the existing object over.
