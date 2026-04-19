# sops-demo — smoke test for the SOPS CMP sidecars

End-to-end test that proves the `sops-decrypt-kustomize` CMP plugin can decrypt a SOPS-encrypted Secret at Argo CD manifest-generation time.

## Prerequisites

- Argo CD repo-server reconciled with the SOPS CMP sidecars (see `cicd/argo-cd/release.yaml`).
- `argocd-sops-age-key` Secret present in the `argocd` namespace with `keys.txt`.
- Local `dagger` CLI + network access to `github.com/stuttgart-things/dagger/sops`.

## Files

| File | Committed? | Purpose |
|---|---|---|
| `configmap.yaml` | yes | Plain ConfigMap, passes through untouched |
| `secret.yaml` | **no** (gitignored) | Plaintext Secret template — the thing you encrypt |
| `secret.enc.yaml` | **yes, after encryption** | SOPS-encrypted Secret — what Argo CD pulls |
| `kustomization.yaml` | yes | Lists `configmap.yaml` + `secret.yaml` (post-decrypt name) |
| `application.yaml` | yes | Argo CD `Application` selecting `sops-decrypt-kustomize` |

## One-time setup

```bash
cd cicd/argo-cd/examples/sops-demo

# 1. Encrypt the plaintext Secret with the cluster age key
export AGE_PUBLIC_KEY="age19vgzvmpt9tdlcsu8rzaacj397yz8gguz38nsmuy6eeelt5vjsyms542xtm"
dagger call -m github.com/stuttgart-things/dagger/sops encrypt \
  --age-key="env:AGE_PUBLIC_KEY" \
  --plaintext-file="./secret.yaml" \
  --file-extension="yaml" \
  export --path="./secret.enc.yaml"

# 2. Remove plaintext and commit the encrypted sibling
rm secret.yaml
git add secret.enc.yaml
git commit -m "test(argocd): add sops-demo encrypted secret"
git push
```

## Run the test

```bash
# 3. Create the Argo CD Application
kubectl apply -f application.yaml

# 4. Watch it sync
kubectl get application sops-demo -n argocd -w

# 5. Confirm the decrypted Secret exists in the target namespace
kubectl get secret sops-demo-secret -n sops-demo \
  -o jsonpath='{.data.password}' | base64 -d
# → "if you can read this after sops-decrypt-kustomize renders, it worked"
```

## Tear down

```bash
kubectl delete -f application.yaml   # finalizer prunes namespace + resources
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Application` stuck in `ComparisonError: no matches for kind "Secret"` | `secret.enc.yaml` not committed or not on `targetRevision` branch |
| Plugin picks `argocd-vault-plugin-kustomize` instead | `spec.source.plugin.name` missing — must be set explicitly (discovery overlaps) |
| `sops: Error getting data key: ...` in the generate output | `argocd-sops-age-key` Secret missing or `keys.txt` doesn't match the recipient used to encrypt |
| `secret.yaml: No such file` during kustomize build | Encrypted file was committed with the wrong name — must be `secret.enc.yaml`, not `secret.yaml.enc` |
