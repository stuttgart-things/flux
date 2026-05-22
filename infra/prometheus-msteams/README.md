# stuttgart-things/flux/prometheus-msteams

[`stakater/prometheus-msteams`](https://github.com/stakater/prometheus-msteams)
— a small proxy that converts Alertmanager webhook notifications into
Microsoft Teams Adaptive Cards and posts them to a Teams **Power Automate
Workflow** webhook.

## Why

Alertmanager's native `msteamsv2` receiver sends a flat `{title,text}`
payload that a stock Teams Workflow cannot render (`cards.unsupported`) —
it needs the Workflow to be hand-edited in the Power Automate GUI, which
is not reproducible. This proxy does the Adaptive Card formatting itself
(`workflowWebhook: true`), from a Git-managed template, so the Teams
Workflow can stay a stock "post the received card" flow.

```
Alertmanager --webhook_configs--> prometheus-msteams --> Teams Workflow
```

## Deployment

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: prometheus-msteams
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/prometheus-msteams
  prune: true
  wait: true
  postBuild:
    substitute:
      PROMETHEUS_MSTEAMS_NAMESPACE: monitoring
      PROMETHEUS_MSTEAMS_VERSION: v1.0.2
    substituteFrom:
      - kind: Secret
        name: prometheus-msteams-webhook
EOF
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_MSTEAMS_NAMESPACE` | `monitoring` | Target namespace |
| `PROMETHEUS_MSTEAMS_VERSION` | `v1.0.2` | Git tag of the chart source |
| `MSTEAMS_WEBHOOK_URL` | *(required, from Secret)* | Teams Power Automate webhook URL |

**`MSTEAMS_WEBHOOK_URL`** must come from a SOPS-encrypted Secret consumed
via the Kustomization's `postBuild.substituteFrom` — it is never committed
in plain text.

## Wiring Alertmanager

The `kube-prometheus-stack` component routes its `msteams` receiver here:

```yaml
receivers:
  - name: msteams
    webhook_configs:
      - url: http://prometheus-msteams.monitoring.svc.cluster.local:2000/alertmanager
        send_resolved: true
```

The connector name (`alertmanager`) is the request path the proxy serves.

## Components

- **requirements.yaml** — Namespace + `GitRepository` chart source
- **release.yaml** — `prometheus-msteams` HelmRelease (chart sourced from Git)
