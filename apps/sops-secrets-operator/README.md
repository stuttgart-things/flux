# stuttgart-things/flux/apps/sops-secrets-operator

Flux app for [sops-secrets-operator](https://github.com/stuttgart-things/sops-secrets-operator) —
the operator that turns a `SopsSecret` (an age-encrypted blob committed to git)
into a real Kubernetes `Secret`. Deploys the OCI kustomize base built from that
repo's `config/default`.

## Kustomization Example

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: sops-secrets-operator
  namespace: flux-system
spec:
  interval: 1h
  sourceRef:
    kind: OCIRepository
    name: stuttgart-things-flux
  path: ./apps/sops-secrets-operator
  prune: true
  wait: true
  postBuild:
    substitute:
      SOPS_OPERATOR_VERSION: v0.9.0
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `SOPS_OPERATOR_VERSION` | `v0.9.0` | Tag of the kustomize base — **keep the `v`** |
| `FLUX_NAMESPACE` | `flux-system` | Where the source and Kustomization live |
| `FLUX_SOURCE_API_VERSION` | `v1` | `source.toolkit.fluxcd.io` version |

Do not pin below **v0.9.0**. Earlier tags carry an off-by-one: the repo writes
`config/manager/kustomization.yaml` before tagging, so `ref=v0.8.5` built a
bundle running image `v0.8.4`. Fixed in
[sops-secrets-operator#90](https://github.com/stuttgart-things/sops-secrets-operator/pull/90).

## Preconditions

**cert-manager.** The operator ships a validating webhook, and the webhook
cannot serve until cert-manager has issued its serving certificate. Without it
the Deployment runs and every `SopsSecret` apply is rejected by a webhook that
never answers — a failure that reads like a broken CRD.

**An age key.** The operator does not carry one: it resolves the key per
resource through `spec.decryption.keyRef`, so this app installs the operator and
nothing else. How the key reaches the cluster is a separate decision and
deliberately not baked in here — today the machinery play writes
`sops-age-key` into `sops-secrets-operator-system` from `SOPS_AGE_KEY`, and a
cluster with external-secrets could pull it from Vault instead.

`v0.9.0` can additionally hold ONE global key for resources that omit `keyRef`
([#47](https://github.com/stuttgart-things/sops-secrets-operator/pull/47)).
That is opt-in and does not remove per-namespace copies: a resource's own
`keyRef` always wins over the global default.

## Namespace ownership

The OCIRepository sits in `flux-system`, not in the operator's namespace. The
base is a kubebuilder `config/default` and creates
`sops-secrets-operator-system` itself; creating it here as well would give the
namespace two owners across two Kustomizations, and a `prune` on either would
take it out from under the other.

For the same reason the Kustomization sets no `targetNamespace` — the base
names its namespace throughout, and overriding it would rewrite the Deployment
while leaving RBAC subjects and the webhook's service reference pointing at the
old one.
