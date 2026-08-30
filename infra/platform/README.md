# stuttgart-things/flux/infra/platform

A **bundle**: one Flux `Kustomization` stands up a cluster's whole infra layer.

Nothing here is a raw manifest — every `ks-*.yaml` is a Flux `Kustomization` CR
pointing back at an existing base in this repo. The consumer's
`postBuild.substitute` fills their `${VAR:-default}` values one hop, and each
child then renders its own base.

The APP layer lives in a second bundle, [`apps/platform`](../../apps/platform)
— openbao, vault, rancher, minio, clusterbook, vcluster — and the DELIVERY
layer in a third, [`cicd/platform`](../../cicd/platform). Both are selected the
same way and read the same `INFRA_*` names.

## Layout

```
infra/platform/
├── root/          empty kustomization — the consumer's spec.path
└── components/    one kustomize Component per app, all opt-in
    ├── cilium-lb/                → ./infra/cilium/components/lb
    ├── cilium-gateway/           → ./infra/cilium/components/gateway        (requires cilium-lb)
    ├── cert-manager-install/     → ./infra/cert-manager/components/install
    ├── cert-manager-selfsigned/  → ./infra/cert-manager/components/selfsigned (requires cert-manager-install)
    ├── cert-manager-vault-issuer/→ ./infra/cert-manager/components/vault-issuer  (requires cert-manager-install)
    ├── trust-manager/            → ./infra/trust-manager                    (requires cert-manager-install)
    ├── nfs-csi/                  → ./infra/nfs-csi
    ├── openebs/                  → ./infra/openebs
    ├── prometheus/               → ./infra/prometheus                       (requires cilium-gateway)
    ├── kube-prometheus-stack/    → ./infra/kube-prometheus-stack            (requires cilium-gateway)
    ├── external-secrets/         → ./infra/external-secrets/components/install
    ├── external-secrets-vault-store/ → …/components/cluster-store-vault      (requires external-secrets)
    ├── flux-web/                 → ./apps/flux-web                          (requires cilium-gateway)
    ├── headlamp/                 → ./apps/headlamp                          (requires cilium-gateway)
    ├── reloader/                 → ./infra/reloader
    ├── velero/                   → ./infra/velero                          (requires an S3 Secret)
    ├── sops-secrets-operator/    → ./apps/sops-secrets-operator
    ├── cnpg-operator/            → ./apps/cnpg-operator
    ├── prometheus-pve-exporter/  → ./infra/prometheus-pve-exporter          (requires kube-prometheus-stack)
    └── coredns-lab-zone/         → ./infra/coredns/components/lab-zone      (RKE2/k3s only)
```

Six of those paths are under `apps/`, and that is deliberate: the bundle a
component belongs to is decided by the layer it serves, not by the directory
its base sits in. `flux-web` and `headlamp` are cluster dashboards,
`sops-secrets-operator` is part of the secrets layer beside `external-secrets`,
and `cnpg-operator` is one cluster-wide operator watching every namespace.

There is no always-on base. The first cluster pointed at this bundle wanted
`cilium-lb` + `cert-manager-install` and neither the Gateway nor the PKI chain,
so everything is opt-in.

### coredns-lab-zone

Makes CoreDNS forward one zone straight to its authoritative nameserver, for
lab zones that carry no NS records and are served by something that is not a
recursor.

```yaml
COREDNS_ZONE: "4sthings.tiab.ssc.sva.de"     # no trailing dot, the base adds it
COREDNS_ZONE_SERVER: "10.100.136.115"
```

Three things worth knowing before selecting it:

- **Fixing the node is not enough.** kubelet points CoreDNS at
  `/run/systemd/resolve/resolv.conf`, the flat file that lists every server and
  cannot express per-domain routing. A node with a systemd-resolved drop-in
  resolves the zone while every pod on it still gets SERVFAIL.
- **RKE2 and k3s only.** It writes a `HelmChartConfig`; elsewhere the
  Kustomization fails with `no matches for kind` and CoreDNS is untouched.
- **Ship it with the cluster.** Adding it to a running single-node cluster rolls
  CoreDNS, and the replacement pod cannot be co-scheduled with the one it
  replaces -- about a minute without cluster DNS.

Unset, it forwards `unset.invalid.` to `0.0.0.0`: visible in the Corefile and
verified not to touch `cluster.local`, service discovery or upstream DNS, which
live in a separate server block.

## Consumer usage

The cluster picks its components on its **own** Kustomization. `spec.components`
is a Flux field; the paths are relative to `spec.path`.

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infra-platform
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/platform/root
  components:
    - ../components/cilium-lb
    - ../components/cert-manager-install
    - ../components/openebs
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUX_SOURCE: flux-infra
      CILIUM_LB_IP_START: '10.100.136.210'
      CILIUM_LB_IP_STOP: '10.100.136.210'
      CERT_MANAGER_NAMESPACE: cert-manager
      OPENEBS_VERSION: '4.5.1'
```

**Adding a line deploys that component. Removing one prunes everything it
deployed, and deletes its child Kustomization too.** That is the entire on/off
mechanism — there is no `<APP>_ENABLED` variable and no switch directory.

A substituted variable could never have done this job: `kustomize build`
produces the resource set first and substitution runs afterwards on its output,
so a variable can change what a resource *says*, never whether it *exists*.
Selection has to happen at build time, and `spec.components` is the build-time
mechanism Flux gives you.

Verified: an eight-component selection renders **byte-for-byte** the same
manifests as the eight hand-written CRs it replaces.

## Prerequisites between components

Six components carry a `dependsOn` and therefore need their prerequisite in
the same list:

| Component | Requires |
|---|---|
| `cilium-gateway` | `cilium-lb` |
| `cert-manager-selfsigned` | `cert-manager-install` |
| `cert-manager-vault-issuer` | `cert-manager-install` |
| `trust-manager` | `cert-manager-install` |
| `prometheus` | `cilium-gateway` |
| `kube-prometheus-stack` | `cilium-gateway` |
| `external-secrets-vault-store` | `external-secrets` |
| `flux-web` | `cilium-gateway` |
| `headlamp` | `cilium-gateway` |
| `prometheus-pve-exporter` | `kube-prometheus-stack` |

The four behind `cilium-gateway` render an `HTTPRoute` unconditionally, and an
`HTTPRoute` whose `parentRef` does not resolve sits at `Accepted=False` without
explaining itself. The dependency turns that into a loud stall instead.

Two constraints this table cannot express:

- **`prometheus` and `kube-prometheus-stack` are alternatives.** Both deploy a
  Prometheus, into `monitoring` by default. Selecting both is not an error
  anywhere — it just scrapes the cluster twice.
- **`external-secrets-vault-store` needs a Vault auth backend the bundle
  cannot create.** The store is Flux's half; the Kubernetes auth mount, its
  role and the bound ServiceAccount come from the VM pipeline
  (`CreateVaultKubernetesAuth --auth-name eso`), because configuring a mount
  needs a Vault token and the cluster's API address. Without it the store sits
  at `Ready=False / InvalidProviderConfig`. And `Ready=True` only proves the
  *login* — a store pointed at a KV mount outside the bound policy validates
  identically and fails at the first ExternalSecret.
- **`prometheus-pve-exporter` is not satisfied by the standalone
  `prometheus`.** Its dependency names `kube-prometheus-stack` because it
  applies a `PodMonitor`, whose CRD comes from the prometheus-operator that kps
  installs — the standalone prometheus chart ships neither, and has no Grafana
  to import the dashboard ConfigMap either. It is also pinned to the
  `monitoring` namespace throughout its base, so a cluster that moved kps with
  `KPS_NAMESPACE` gets an exporter kps never scrapes: nothing fails, the
  metrics are just absent.
- **`kube-prometheus-stack` needs a StorageClass that exists here.** Its
  default, `nfs4-csi`, is real only on clusters that also selected `nfs-csi`.
  Get it wrong and the Kustomization goes Ready — the Helm release installs
  fine — while the Prometheus pod sits Pending forever on an unbound PVC. Set
  `KPS_PROMETHEUS_STORAGE_CLASS` to whatever `kubectl get sc` reports.

Flux has no optional dependency, so selecting one without its prerequisite
parks it on "dependency not ready" instead of deploying something half-wired.
That is a loud, correct failure — but it is a failure, so check the table when
trimming a list.

## Why child Kustomizations and not one merged build

`apps/homerun2` composes components whose manifests all land in **one** Flux
Kustomization. That works there because those components are independent.

Infra is not: `cert-manager-selfsigned` applies `ClusterIssuer`/`Certificate`,
`cilium-gateway` applies a `Gateway`, `trust-manager` applies a `Bundle`,
`cilium-lb` applies `CiliumLoadBalancerIPPool` — CRs whose CRDs are installed by
the very same bundle. Merged into one build, every reconcile races those CRDs
and only converges by retry, with `wait: true` reporting failure in between.
Child CRs keep `dependsOn`, plus per-component health, retry and blast radius.

Same shape as [`cicd/argocd-platform`](../../cicd/argocd-platform).

## Freezing a component without removing it

Each child also has `<COMPONENT>_SUSPEND`, default `false`:

```yaml
postBuild:
  substitute:
    PROMETHEUS_SUSPEND: "true"     # note the quotes: substitute is map[string]string
```

`CILIUM_LB_SUSPEND`, `CILIUM_GATEWAY_SUSPEND`, `CERT_MANAGER_INSTALL_SUSPEND`,
`CERT_MANAGER_SELFSIGNED_SUSPEND`, `CERT_MANAGER_VAULT_ISSUER_SUSPEND`,
`TRUST_MANAGER_SUSPEND`, `NFS_CSI_SUSPEND`, `OPENEBS_SUSPEND`,
`PROMETHEUS_SUSPEND`, `KPS_SUSPEND`, `EXTERNAL_SECRETS_SUSPEND`,
`ESO_STORE_SUSPEND`, `FLUX_WEB_SUSPEND`, `HEADLAMP_SUSPEND`,
`RELOADER_SUSPEND`, `COREDNS_LAB_ZONE_SUSPEND`, `VELERO_SUSPEND`,
`SOPS_OPERATOR_SUSPEND`, `CNPG_OPERATOR_SUSPEND`, `PVE_EXPORTER_SUSPEND`.

Two of them freeze less than they look like they do. `SOPS_OPERATOR_SUSPEND`
stops the wrapper Kustomization only — the inner one it applied keeps
reconciling, because `suspend` does not propagate into an applied
Kustomization's own spec. And a suspended `cnpg-operator` leaves every Postgres
`Cluster` running with nobody to fail it over or back it up, still reporting
the status it last had.

This **stops reconciliation and leaves deployed objects running**, unmanaged —
it is for maintenance, not for "this cluster doesn't need X" (that is a line in
`spec.components`). A suspended Kustomization never reports Ready, so do not
suspend one that others depend on: everything behind it stalls.

Note it is also the one place a bool works *directly*, and the reason is worth
knowing: `spec.suspend` is a **boolean field**, so the bare `false` that
`${VAR:-false}` renders is exactly the right type. `postBuild.substitute` is
`map[string]string`, so the same bare `false` is rejected there. The field's
type decides, not the syntax — which is also the subject of the next section.

## Two constraints that shape every file here

**1. A child's substitute values must be non-empty strings.**
`kustomize build` normalises away *every* quoting style — `"${VAR}"`,
`'${VAR}'`, `!!str`, `|-` all emit plain `${VAR}` — so an unset variable
reaches Flux as `KEY:`, a YAML null, and the CRD declares
`postBuild.substitute` as `map[string]string` with no `nullable`: the API
server rejects the entire CR. A child therefore **cannot inherit** a base's
default by passing an empty value, and every threaded variable carries its own
default here.

That means chart versions exist twice — in the base (where the `# renovate:`
annotation lives) and here. `renovate.json`'s fourth `customManager` matches
these lines so both copies move in the same PR. **When adding a version
default to a `ks-*.yaml`, copy the base's `# renovate:` comment with it** —
without it the bundle silently pins the old version after the next bump.

**2. Booleans and numbers cannot be threaded at all.**
Same quote-stripping: `KEY: "${FOO:-false}"` renders as `KEY: false`, a YAML
bool, which the string-typed map rejects. Those knobs are listed as
`# NOT threaded` in the file that would carry them and are left to the base's
default (all of which already match this fleet). To change one, patch the child
from the consumer with a **literal** value — a literal keeps its quotes:

```yaml
patches:
  - target: {kind: Kustomization, name: openebs}
    patch: |
      - op: add
        path: /spec/postBuild/substitute/REPLICATED_MAYASTOR_ENABLED
        value: "true"
```

The same limit applies to two-part versions: `OPENEBS_VERSION: '4.5'` renders
as a float and is rejected — use `4.5.0`, or the literal-patch form.

## Variables

```bash
task get-variables    # every ${VAR:-default} in this folder
```

Bundle-level names (they map onto differently-named base variables):

| Variable | Default | Feeds |
|---|---|---|
| `FLUX_SOURCE` | `flux-infra` | `sourceRef.name` of every child |
| `INFRA_DOMAIN` | *(required)* | `CILIUM_GATEWAY_DOMAIN`, `CERT_MANAGER_SELFSIGNED_DOMAIN`, prometheus/flux-web/headlamp `DOMAIN` |
| `INFRA_GATEWAY_NAME` | `cilium-gateway` | `CILIUM_GATEWAY_NAME`, prometheus/flux-web/headlamp `GATEWAY_NAME` |
| `INFRA_GATEWAY_NAMESPACE` | `default` | both of the above + `CERT_MANAGER_SELFSIGNED_CERT_NAMESPACE` |
| `INFRA_TLS_SECRET` | `wildcard-tls` | `CILIUM_GATEWAY_TLS_SECRET`, `CERT_MANAGER_SELFSIGNED_{CERT,SECRET}_NAME` |
| `PROMETHEUS_HOSTNAME` | `prometheus` | prometheus `HOSTNAME` (the base's name is too generic to expose) |
| `KPS_HOSTNAME` | `grafana` | kube-prometheus-stack `HOSTNAME` (same reason) |
| `FLUX_WEB_HOSTNAME` | `flux` | flux-web `HOSTNAME` (same reason) |
| `HEADLAMP_HOSTNAME` | `headlamp` | headlamp `HOSTNAME` (same reason) |
| `COREDNS_ZONE` | `unset.invalid` | coredns-lab-zone `zones[0].zone` |
| `COREDNS_ZONE_SERVER` | `0.0.0.0` | coredns-lab-zone `forward` target |
| `COREDNS_CHART_NAME` | `rke2-coredns` | the HelmChart it configures (`coredns` on k3s) |
| `VELERO_BUCKET` | *(required)* | the S3 bucket backups are written to |
| `VELERO_S3_ENDPOINT` | *(required)* | S3 / MinIO endpoint URL |
| `VELERO_SECRET` | `velero-s3-credentials` | Secret holding `VELERO_S3_ACCESS_KEY` / `VELERO_S3_SECRET_KEY` |
| `PVE_EXPORTER_TARGET` | *(required)* | the Proxmox host scraped via `?target=` |
| `<COMPONENT>_SUSPEND` | `false` | that child's `spec.suspend` |

Required variables have no upstream default, so they fall back to an
unmistakable sentinel (`set-INFRA_DOMAIN.invalid`, `0.0.0.0`,
`set-NFS_SERVER_FQDN.invalid`) rather than a null.

Every other variable keeps its base name and its base default.

## velero is wired for one of the base's two credential modes

`./infra/velero` offers two mutually exclusive ways to fill the
`cloud-credentials` Secret (its README → *Credential modes*). This component
wires **mode 1**: the base's own `pre-release.yaml` Secret, filled from a
`substituteFrom` Secret that must carry `VELERO_S3_ACCESS_KEY` and
`VELERO_S3_SECRET_KEY` — SOPS-encrypted in the cluster repo.

```yaml
postBuild:
  substitute:
    VELERO_BUCKET: velero-cluster-test4
    VELERO_S3_ENDPOINT: https://minio.4sthings.tiab.ssc.sva.de
    VELERO_SECRET: velero-s3-credentials     # the Secret this bundle reads
```

`optional: false`, deliberately. Left optional, Flux substitutes empty strings
and installs a Velero whose credentials file reads `aws_access_key_id=` — the
Deployment starts, the Kustomization reports Ready, and every backup fails at
the first upload. That is the worst moment to find out, because by then
somebody believes the cluster is backed up.

Mode 2 (ESO pulling from Vault) needs `components/external-secret` **plus** a
patch deleting the base Secret so the two do not fight over one name. A
kustomize Component cannot express "and also patch out a resource from the path
I point at", so mode 2 stays what it is today: a cluster that wants it wires
`./infra/velero` itself. Selecting this component *and* adding the ESO
component by hand gives two writers for `cloud-credentials` — pick one.

Note also that removing this component **prunes Velero, not the backups**. The
bucket contents survive, which is the point of them being there.

## Migrating a cluster off per-component CRs

The bundle's children are named exactly like the CRs they replace
(`cilium-lb`, `cert-manager-install`, …), so they adopt the existing objects
instead of duplicating them. Apply the bundle **first**, confirm the children
are `Ready`, then remove the old files from the cluster repo.

Do not simply `kubectl delete kustomization <name>` — those CRs have
`prune: true` and deletion takes their workloads with them. Either let the
bundle adopt them by name as above, or set `prune: false` on a CR before
deleting it.

If you are rebuilding rather than adopting, delete the old files in their own
commit and let the prune finish **before** the bundle lands, so the teardown
does not race the bundle's create — the two use the same child names.

## The Vault ClusterIssuer, and the half that is not here

`cert-manager-vault-issuer` deploys a `ClusterIssuer` that authenticates to
Vault with a Kubernetes ServiceAccount token minted per request — no static
token anywhere in the cluster.

It carries only the half that belongs in Git. The Vault kubernetes auth backend,
its role, and the CA `Secret` the issuer trusts are created by the VM pipeline's
vault-auth step (`blueprints CreateVaultKubernetesAuth`), which is the only
thing holding Vault credentials. Until that has run, the issuer sits not-Ready
and any `Certificate` naming it waits — correct, and loud.

Three variables are REQUIRED and fall back to sentinels:

```yaml
VAULT_ISSUER_SERVER: https://vault-vsphere.tiab.labda.sva.de:8200
VAULT_ISSUER_PKI_PATH: pki/sign/4sthings.tiab.ssc.sva.de
VAULT_ISSUER_AUTH_MOUNT_PATH: /v1/auth/<cluster>-certmanager
```

The mount path is per-cluster: the pipeline creates the backend as
`<cluster>-<authName>`, so a cluster named `foo` gives `/v1/auth/foo-certmanager`.

To have this issuer sign the wildcard, point `cert-manager-selfsigned` at it:

```yaml
CERT_MANAGER_SELFSIGNED_ISSUER: ${VAULT_ISSUER_NAME}
```

**It also ships `Role`/`RoleBinding` `cert-manager-tokenrequest`, and that is not
optional.** The cert-manager chart rendered it up to v1.18.x and renders no
`serviceaccounts/token` rule at all from v1.21.1, with no values flag to bring it
back. Without it cert-manager cannot mint the token — and the ClusterIssuer
still reports `Ready`, because cert-manager verifies only the Vault *login*,
never the ability to sign. Certificates simply never get issued. Never accept
`Ready=True` as proof here; the only proof is an issued `Certificate`.
