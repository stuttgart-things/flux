# stuttgart-things/flux/fluent-bit

[Fluent Bit](https://fluentbit.io/) as a DaemonSet: every container log of the
node, with its Kubernetes metadata, pushed to Loki ([`infra/loki`](../loki)).
Chart: `fluent-bit` from `oci://ghcr.io/fluent/helm-charts`.

Each stream is labelled `job=fluent-bit`, `cluster=<FLUENT_BIT_CLUSTER_NAME>`,
`namespace_name`, `pod_name`, `container_name`.

## Two ways to reach Loki

| | output | select |
|---|---|---|
| Loki on the **same** cluster | HTTP, port 80, to `FLUENT_BIT_LOKI_HOST` (default `loki-gateway.loki.svc.cluster.local`) | `./infra/fluent-bit` / bundle component `fluent-bit` |
| Loki on **another** cluster | HTTPS, port 443, to that cluster's `loki` route, verified against `FLUENT_BIT_CA_CONFIGMAP` | `components/remote` / bundle component `fluent-bit-remote` |

Port and TLS are fixed per variant rather than variables: they would
substitute to an int and a bool, and a bundle only threads strings
(`hack/check-substitute-strings.py`).

The CA bundle ConfigMap (default `cluster-trust-bundle`, key
`trust-bundle.pem`, as trust-manager writes it) is mounted optional. Without it
the pod still starts, and every push then fails TLS verification.

## Deployment (remote)

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: fluent-bit
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/fluent-bit
  components:
    - components/remote
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUENT_BIT_CLUSTER_NAME: homerun2-dev
      FLUENT_BIT_LOKI_HOST: loki.platform.sthings.lab
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `FLUENT_BIT_NAMESPACE` | `logging` | Target namespace |
| `FLUENT_BIT_VERSION` | `0.58.3` | Chart version (Fluent Bit 5.1.3) |
| `FLUENT_BIT_CLUSTER_NAME` | *(required)* | `cluster` label on every stream |
| `FLUENT_BIT_LOKI_HOST` | `loki-gateway.loki.svc.cluster.local` / *(required for remote)* | Loki gateway host |
| `FLUENT_BIT_CA_CONFIGMAP` | `cluster-trust-bundle` | remote: CA bundle ConfigMap |
| `FLUENT_BIT_CA_KEY` | `trust-bundle.pem` | remote: key in it |
