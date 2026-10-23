# homerun2 / k8s-pitcher component

Flux component for homerun2-k8s-pitcher. Watches the K8s API via informers and collectors, sends events to omni-pitcher via HTTP.

## Architecture

```
K8s API → informers (real-time add/update/delete)  → HTTP POST → omni-pitcher → Redis Streams
        → collectors (periodic snapshots)           → HTTP POST → omni-pitcher → Redis Streams
```

## Substitution Variables

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_K8S_PITCHER_VERSION` | see `requirements.yaml` | no | OCI kustomize base + container image tag |
| `HOMERUN2_K8S_PITCHER_NAMESPACE` | `homerun2-flux` | no | Target namespace |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | `changeme` | no | Bearer auth token (shared with omni-pitcher, from `substituteFrom` Secret) |
| `HOMERUN2_K8S_PITCHER_TRUST_BUNDLE_CM` | `cluster-trust-bundle` | no | ConfigMap with CA bundle for TLS trust |
| `HOMERUN2_K8S_PITCHER_PROFILE_CM` | `homerun2-k8s-pitcher-profile` | no | ConfigMap with K8sPitcherProfile YAML |
| `HOMERUN2_CENTRAL_PITCHER_URL` | sentinel | with `remote/` | Central omni-pitcher `/pitch` endpoint |
| `CLUSTER_NAME` | sentinel | with `remote/` | `spec.cluster` in the profile |
| `HOMERUN2_K8S_PITCHER_AUTH_TOKEN` | - | with `sops/` | Token for the token Secret |
| `HOMERUN2_SECRET_STORE`, `HOMERUN2_OMNI_PITCHER_TOKEN_PATH`, `HOMERUN2_OMNI_PITCHER_TOKEN_PROPERTY` | sentinel, `homerun2`, `omni-pitcher-auth-token` | with `eso/` | Where the token lives |

## Remote: k8s-pitcher only, pitching to a central homerun2 (#823)

Three sub-components, each listed after this one:

| Sub-component | Adds |
|---|---|
| `remote/` | the namespace, the profile ConfigMap (the `important-events` preset of homerun2-k8s-pitcher, `pitcher.addr: ${HOMERUN2_CENTRAL_PITCHER_URL}`, `spec.cluster: ${CLUSTER_NAME}`, `insecure: false`), and a ClusterRole replacing the artefact's with exactly what that profile watches: `nodes`, `events`, `kustomizations.kustomize.toolkit.fluxcd.io`, `helmreleases.helm.toolkit.fluxcd.io` (get/list/watch), plus `get` on the one Secret `homerun2-k8s-pitcher-token` |
| `eso/` | the token Secret as an ExternalSecret: `${HOMERUN2_SECRET_STORE}`, entry `${HOMERUN2_OMNI_PITCHER_TOKEN_PATH}`, property `${HOMERUN2_OMNI_PITCHER_TOKEN_PROPERTY}` |
| `sops/` | the token Secret from `${HOMERUN2_K8S_PITCHER_AUTH_TOKEN}`, no default |

`eso/` and `sops/` delete the artefact's placeholder Secret in the child, so the
parent's Secret is its only writer. Select one of them. `profiles/k8s-pitcher-remote`
(eso) and `profiles/k8s-pitcher-remote-sops` compose them; the apps-platform
bundle components `homerun2-k8s-pitcher-remote` / `-sops` apply those.

`remote/` **needs k8s-pitcher v1.3.0 or later** (homerun2-k8s-pitcher#88). The
profile loader ignores fields it does not know, so an older image starts fine,
drops `types`, `reasons`, `cooldown` and `rateLimit`, and pitches every Event.

The token is the **central** omni-pitcher's. The pitcher verifies TLS against
trust-manager's `cluster-trust-bundle`, which must hold the central endpoint's CA.

## Profile ConfigMap

The component **deletes** the KCL-generated profile ConfigMap and expects the calling side to provide a cluster-specific one. This is because the profile contains cluster-specific configuration (pitcher URL, watched namespaces, informer/collector config).

Create the profile ConfigMap on the calling side:

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: homerun2-k8s-pitcher-profile
  namespace: homerun2-flux
data:
  profile.yaml: |
    apiVersion: homerun2.sthings.io/v1alpha1
    kind: K8sPitcherProfile
    metadata:
      name: my-cluster
    spec:
      pitcher:
        addr: https://pitcher.example.com/pitch
        insecure: false
      auth:
        tokenFrom:
          secretKeyRef:
            name: homerun2-k8s-pitcher-token
            namespace: homerun2-flux
            key: auth-token
      collectors:
        - kind: Node
          interval: 60s
        - kind: Pod
          namespace: "*"
          interval: 30s
        - kind: Event
          namespace: "*"
          interval: 15s
      informers:
        - group: ""
          version: v1
          resource: pods
          namespace: "*"
          events: [add, update, delete]
        - group: apps
          version: v1
          resource: deployments
          namespace: homerun2-flux
          events: [add, update, delete]
```

## TLS Trust Bundle

The component mounts a trust-manager CA bundle (`cluster-trust-bundle` ConfigMap) and sets `SSL_CERT_DIR=/etc/ssl/custom` so Go's TLS stack automatically uses the custom CAs. This allows `insecure: false` in the profile when the pitcher endpoint uses a private CA.

The volume mount is `optional: true` — the pod starts without the bundle (falls back to system trust store).

## CRD Watching

To watch custom resources, extend the ClusterRole with additional RBAC rules on the calling side and add matching informer entries in the profile:

```yaml
# Additional ClusterRole for CRD RBAC (calling side)
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: homerun2-k8s-pitcher-crds
rules:
  - apiGroups: ["stable.example.com"]
    resources: ["crontabs"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: homerun2-k8s-pitcher-crds
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: homerun2-k8s-pitcher-crds
subjects:
  - kind: ServiceAccount
    name: homerun2-k8s-pitcher
    namespace: homerun2-flux
```

Profile informer entry:

```yaml
informers:
  - group: stable.example.com
    version: v1
    resource: crontabs
    namespace: "*"
    events: [add, update, delete]
```

## Patches Applied

| Target | Patch |
|--------|-------|
| Deployment | Override container image tag |
| Secret (`homerun2-k8s-pitcher-token`) | Override auth token from variable |
| Deployment | Mount trust-bundle volume + `SSL_CERT_DIR` env var |
| Deployment | Override profile ConfigMap name |
| ConfigMap (`homerun2-k8s-pitcher-profile`) | Delete (calling side provides its own) |
