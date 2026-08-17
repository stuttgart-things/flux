---
name: rancher-app-validated-platform-sthings
description: apps/rancher (PR #152) — HTTPRoute + trust-manager privateCA, validated on platform-sthings
metadata:
  type: project
---

`apps/rancher` (PR #152, branch `feature/add-rancher`) deploys Rancher via the `rancher-stable` Helm repo with Gateway API HTTPRoute (not Ingress): `ingress.enabled: false` + `tls: external`, HTTPRoute backend → the `rancher-deployment` Service (chart names the svc after the HelmRelease) port 80. Default chart `2.14.2` — only the 2.14.x line allows kubeVersion `< 1.36.0`; 2.13.x caps at `< 1.35.0` and the platform-sthings cluster runs k8s 1.35.

privateCA's `tls-ca` secret (`cacerts.pem`) is produced by **trust-manager** (Option 1), not hand-fed: `infra/trust-manager/release.yaml` enables `secretTargets` (authorized: `tls-ca`) and `post-release.yaml` adds a Bundle writing `cacerts.pem` into the rancher namespace. trust-manager v0.22.0's secret targets are off by default — they need the `--secret-targets-enabled=true` flag (chart value `secretTargets.enabled: true`).

**Why:** Validated end-to-end on platform-sthings (gateway `platform-sthings-gateway` ns `default`, domain `platform.sthings-vsphere.labul.sva.de`, issuer used for test `cluster-ca` because `vault-pki` was failing). `GET https://rancher.<domain>/` returned HTTP 200.

**How to apply:** Two cluster gotchas hit during the work — the trust-pkg-debian init image (`quay.io/jetstack/trust-pkg-debian-bookworm`) was 504-ing from quay.io (worked around by cordoning to the node that had it cached); and uninstalling Rancher leaves a `rancher.cattle.io` webhook + `v1.ext.cattle.io` APIService that must be deleted or they block namespace ops. See [[trust-manager-owns-cert-manager-ns]].
