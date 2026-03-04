# SOPS Secrets Encryption

Encrypt and decrypt Kubernetes secrets using SOPS with Age keys. Flux automatically decrypts SOPS-encrypted secrets during reconciliation.

## How It Works

1. Secrets are encrypted with an Age public key before committing to Git
2. The Age private key is stored as a Kubernetes secret (`sops-age`) in `flux-system`
3. The Flux Operator patches `kustomize-controller` to use SOPS decryption on all `Kustomization` resources

## Create an Age Keypair

```bash
age-keygen -o age.key
# Public key: age1...
# Private key is in the file
```

## Deploy the SOPS Secret to the Cluster

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: sops-age
  namespace: flux-system
type: Opaque
stringData:
  age.agekey: AGE-SECRET-KEY-1...
EOF
```

## Encrypt a Secret File

```bash
export AGE_PUBLIC_KEY="age1..."

dagger call -m github.com/stuttgart-things/dagger/sops encrypt \
  --age-key="env:AGE_PUBLIC_KEY" \
  --plaintext-file="./secret.yaml" \
  --file-extension="yaml" \
  export --path="./secret.enc.yaml"
```

## Decrypt a Secret File

```bash
export SOPS_AGE_KEY="AGE-SECRET-KEY-1..."

# View contents
dagger call -m github.com/stuttgart-things/dagger/sops decrypt \
  --age-key="env:SOPS_AGE_KEY" \
  --encrypted-file="./secret.enc.yaml" \
  contents

# Export to file
dagger call -m github.com/stuttgart-things/dagger/sops decrypt \
  --age-key="env:SOPS_AGE_KEY" \
  --encrypted-file="./secret.enc.yaml" \
  export --path="./secret.dec.yaml"
```

## Flux Integration

The FluxInstance includes a SOPS patch that automatically adds decryption to all Kustomization resources:

```yaml
kustomize:
  patches:
    - patch: |
        - op: add
          path: /spec/decryption
          value:
            provider: sops
            secretRef:
              name: sops-age
      target:
        group: kustomize.toolkit.fluxcd.io
        version: v1
        kind: Kustomization
```

This means any SOPS-encrypted file referenced by a Flux Kustomization will be automatically decrypted during reconciliation.
