# homerun2/notification-catcher

Outbound dispatcher — reads the `alerts` Redis stream and posts each message to Microsoft Teams (and any other configured webhook sink). Replacement for the in-cluster `prometheus-msteams` proxy: the Adaptive Card formatting and routing logic live in version-controlled Go code (see [`homerun2-notification-catcher`](https://github.com/stuttgart-things/homerun2-notification-catcher)).

Pure consumer — no Service, no Ingress, no HTTPRoute.

## Pipeline

```
Alertmanager ─▶ omni-pitcher /pitch/grafana ─▶ Redis stream "alerts"
                                                     │
                                          notification-catcher
                                                     │
                                                ▶ MS Teams
```

## Pattern

OCIRepository + Flux Kustomization

- **Source:** `oci://ghcr.io/stuttgart-things/homerun2-notification-catcher-kustomize`
- **Image:** `ghcr.io/stuttgart-things/homerun2-notification-catcher`

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Target namespace |
| `HOMERUN2_NOTIFICATION_CATCHER_KUSTOMIZE_VERSION` | `v1.2.0` | OCI kustomize artifact version |
| `HOMERUN2_NOTIFICATION_CATCHER_VERSION` | `v1.2.0` | Container image tag |
| `HOMERUN2_REDIS_PASSWORD_B64` | *(required)* | Base64-encoded Redis password |
| `TEAMS_WEBHOOK_URL` | *(required)* | Power Automate webhook URL for the destination Teams channel |

`TEAMS_WEBHOOK_URL` must be supplied via the parent stack's `substituteFrom: homerun2-flux-secrets`.

## Customizations

- Sets the container image tag to `HOMERUN2_NOTIFICATION_CATCHER_VERSION`.
- Patches the Redis password Secret with the cluster's `HOMERUN2_REDIS_PASSWORD_B64`.
- Patches the env ConfigMap to point at `redis-stack.<namespace>.svc.cluster.local:6379`.
- Patches the output-secrets Secret with `TEAMS_WEBHOOK_URL`.

## Routing config

The catcher reads `/etc/notification-catcher/config.yaml` (a ConfigMap mounted by the kustomize base) at startup. Webhook URLs in that YAML are written as `${TEAMS_WEBHOOK_URL}` placeholders — resolved at runtime against the env var that comes from this Secret patch. The real URL never lands in plaintext in the ConfigMap. See [`homerun2-notification-catcher/docs/deployment.md`](https://github.com/stuttgart-things/homerun2-notification-catcher/blob/main/docs/deployment.md) for the two-layer secret design.

## Adding more outputs

To wire in a new sink that needs a secret env var (PagerDuty, Slack, …):

1. Extend the kustomize-base profile in `homerun2-notification-catcher/tests/kcl-deploy-profile.yaml` with the additional `outputSecrets` key and the YAML output stanza.
2. Add the secret value to `homerun2-flux-secrets` (SOPS-encrypted) in the cluster repo.
3. Add a patch here mapping the new key into the `<name>-secrets` Secret stringData (or extend the existing patch).
4. Cut a new release of `homerun2-notification-catcher`; bump `HOMERUN2_NOTIFICATION_CATCHER_VERSION` here.
