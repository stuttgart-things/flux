# reloader

[Stakater Reloader](https://github.com/stakater/Reloader) controller. Watches
`ConfigMap`/`Secret` changes and performs a rolling restart of any workload that
opts in via annotation, so config/secret updates take effect without a manual
`kubectl rollout restart`.

## Opt-in (on the workload)

```yaml
metadata:
  annotations:
    # roll on change of ANY referenced ConfigMap/Secret (env, envFrom, volumes)
    reloader.stakater.com/auto: "true"
    # or pin to specific objects:
    # secret.reloader.stakater.com/reload: "backstage-secrets"
    # configmap.reloader.stakater.com/reload: "my-config"
```

`apps/backstage` already carries `reloader.stakater.com/auto: "true"` on its
Deployment.

## Consume

Add a Flux `Kustomization` referencing this path:

```yaml
spec:
  path: ./infra/reloader
  sourceRef:
    kind: GitRepository
    name: apps-upstream
```

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `RELOADER_NAMESPACE` | `reloader` | Namespace for the controller |
| `RELOADER_VERSION` | `2.2.12` | Stakater Reloader Helm chart version |
| `RELOADER_RELOAD_STRATEGY` | `annotations` | `annotations` or `env` rollout trigger |
| `RELOADER_REPLICAS` | `1` | Controller replica count |
