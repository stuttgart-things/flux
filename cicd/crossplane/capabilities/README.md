# cicd/crossplane/capabilities

What a management cluster can **do**, as opposed to what it *is*.

The [profile](../profiles/) installs the packages — providers, functions and
Configurations — and it is a **fleet fact**: identical on every management
cluster, generated from the KCL catalog. A package on its own does nothing
useful:

| missing | consequence |
|---|---|
| `ClusterProviderConfig` | the provider runs and does not know where to connect |
| credentials | it knows where, and may not log in |
| `EnvironmentConfig` | it is logged in and does not know which node, datastore or template to place a VM on |

Those three are **cluster facts** — where a VM goes and what it authenticates
with is per datacentre, not per fleet — which is why they are here and
deliberately not in the profile. The rule is stated at its source in
`stuttgart-things`, `crossplane/xrs/capability/labda/seed-labda-1.yaml`.

## One directory per set

```
components/   vspherevm  proxmoxvm  ansible-run  harvester-vm
sets/         labda-vsphere  labul-proxmox  harvester-demo
              labda-vsphere-labul-proxmox   (two environments, see below)
```

A **set** is one environment's worth of capabilities -- except
`labda-vsphere-labul-proxmox`, which is two: a machinery cluster sits in LabDA
and builds the app clusters on LabUL Proxmox. Both live in one set rather than
two Kustomizations because both would own `ansible-run` and fight over it every
reconcile. `CROSSPLANE_CAPABILITY_ENVIRONMENT` still selects ONE environment --
`labda` there -- and the set patches proxmoxvm's release name and `environment`
to `labul` literally, because that chart ships `environments.labul` only.

The consumer names the set:

```yaml
path: ./cicd/crossplane/capabilities/sets/${CROSSPLANE_CAPABILITY_SET}
```

Same shape as the profiles, for the same reason: adding an environment is
adding a directory, and one path means one thing to the checks that key on
`spec.path`.

## Credentials come from git, not from a Vault

`secretStore.backend: sops-git` throughout. The charts can also read from a
Vault (`eso`), and on the fleet's *managed* clusters they do — but that needs a
Kubernetes auth mount on each environment's Vault, and there are three of them.
For a cluster that is nobody's managed cluster, nothing creates those: on
managed clusters the mount comes from the `vaultIssuer` block of a Platform XR,
whose autoReviewer chain lives in the platform Composition, and a standalone
`VaultK8sAuth` has `backendConfig.secretName` as a required field with no
producer.

So the credentials are the encrypted files already in `stuttgart-things`, and
the only secret the cluster needs is the age key — which arrives through the one
Vault it already authenticates to. See [`infra/sops-git`](../../../infra/sops-git),
which this depends on.

## The charts already know the environments

`vspherevm` ships `environments.labda` and `.labul`, `proxmoxvm` ships `.labul`,
`ansible` ships both — template UUIDs, datastore and network IDs, folders. So a
component here passes `environment: <name>` and does not restate placement.
Change a datastore in the chart, not here.

`configuration.install: false` everywhere: the profile installs the packages, and
letting a chart install one too would put the same OCI path under a second CR.

## harvester-demo has no chart

There is no harvester capability chart, so that set writes its
`EnvironmentConfig` and `ClusterProviderConfig` directly. The values are
shorter (`storageClassName`, `namespace`, `networkName`, `imageId`) because
harvester-vm renders a KubeVirt VirtualMachine through provider-kubernetes and
registers no provider of its own — there is no hypervisor credential to fetch,
only a kubeconfig to the Harvester cluster.

Every value is a variable the parent Kustomization passes through, so a cluster
sets it in its `cicd-platform` substitutes:

| variable | default | |
|---|---|---|
| `CROSSPLANE_CAPABILITY_HARVESTER_ENVIRONMENT` | `default` | the EnvironmentConfig's selector label |
| `CROSSPLANE_CAPABILITY_HARVESTER_PROVIDER_CONFIG` | `in-cluster` | provider-kubernetes config for the Harvester API |
| `CROSSPLANE_CAPABILITY_HARVESTER_STORAGE_CLASS` | `harvester-longhorn` | on a lab Harvester, the image's `lh-<uuid>` class |
| `CROSSPLANE_CAPABILITY_HARVESTER_NAMESPACE` | `vms` | |
| `CROSSPLANE_CAPABILITY_HARVESTER_NETWORK` | `default/vms` | |
| `CROSSPLANE_CAPABILITY_HARVESTER_IMAGE` | `default/image-ubuntu` | |

The defaults only fit a Harvester that **is** the cluster. A management cluster
building on a separate one has to set all of them — nothing reports a wrong one;
the first sign is a VM whose PVC stays Pending.

The set still carries `ansible-run`. Its SSH login comes from sops-git like
everywhere else; `CROSSPLANE_CAPABILITY_ANSIBLE_SSH_BACKEND=none` drops that and
the cluster supplies the `ansible-credentials` Secret in the tekton namespace
itself. The `sops-git` Kustomization stays a dependency either way — it also
owns the `stuttgart-things-charts` HelmRepository.

A variable read under `components/` and missing from the parent's substitute
list fails CI (`hack/check-passthrough-coverage.py`).
