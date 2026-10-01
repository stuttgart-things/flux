# stuttgart-things/flux/machinery

Flux app for machinery — gRPC + HTMX service for watching Crossplane-managed Kubernetes custom resources. Deploys via OCI kustomize base (built from KCL manifests) with Gateway API HTTPRoute.

## Kustomization Example

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: machinery
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./cicd/machinery
  prune: true
  wait: true
  postBuild:
    substitute:
      MACHINERY_NAMESPACE: machinery
      MACHINERY_VERSION: v1.14.0
      MACHINERY_HOSTNAME: machinery
      # NOTE: this path no longer carries the HTTPRoute -- it lives in
      # ./cicd/machinery/httproute and needs a SECOND Kustomization that
      # dependsOn this one. Cilium resolves an HTTPRoute's backendRefs once,
      # and machinery's Service is created by the nested Kustomization inside
      # this path, so a route applied together with it answers 500 forever.
      # The cicd-platform bundle's machinery component does both for you.
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `MACHINERY_NAMESPACE` | `machinery` | Target namespace |
| `MACHINERY_VERSION` | `v1.14.0` | Image + kustomize OCI tag — **keep the `v`** |
| `MACHINERY_HOSTNAME` | `machinery` | HTTPRoute hostname prefix |
| `MACHINERY_GRPC_HOSTNAME` | `machinery-grpc` | GRPCRoute hostname prefix (`./grpcroute` only) |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute hostname |

Both `ghcr.io/stuttgart-things/machinery` and `ghcr.io/stuttgart-things/machinery-kustomize` publish `v`-prefixed tags, so one variable serves both — but only in that form. A bare `1.13.4` leaves the `OCIRepository` unresolvable, and the resulting error does not mention the version, so the app simply never deploys.

## What the dashboard watches

The kinds and fields come from `config.json` in the `machinery-watch-config` ConfigMap ([`watch-config.yaml`](watch-config.yaml)), mounted at `/etc/machinery` and pointed to by `MACHINERY_CONFIG`. It ships this fleet's XRs:

| kind | shown |
|---|---|
| `ClusterStack` | `status.stage` — the one field to look at when a build is stuck — plus endpoint, domain and IP; `Stage` and `StatusReady` (`status.ready`) also as info fields, so a gRPC client gets them as keys instead of parsing `connection_details` |
| `Kustomization` | Flux: last applied and attempted revision, path — whether an order in git has reached the cluster yet |
| `Platform` | `readyComponents` / `componentCount`, so `3 / 4` is visible without opening the YAML |
| `XIPReservation` | reservation status, FQDN, addresses |
| `VaultK8sAuth` | Vault address and cluster (its status is empty today, so Ready comes from conditions) |
| `NativeProxmoxVM` | IP, VMID, whether it started, and whether its AnsibleRun succeeded |
| `NativeVsphereVM` | IP, MOID, power state, and whether its AnsibleRun succeeded |
| `AnsibleRun` | reason and result, plus the PipelineRun name — which is what you need to find the logs |

The two VM kinds are separate entries rather than one, because their `status.share` blocks genuinely differ: proxmox reports `vmId` and `started`, vsphere `moid` and `powerState`. Merged, one column would always be blank.

The file is deliberately **not** a substitution variable: it is one document, identical on every cluster here, and threading ~60 lines of JSON through `postBuild.substitute` would mean escaping it across newlines for nothing. To watch something else, patch the ConfigMap.

It is also deliberately **not** called `machinery-config`. That name belongs to the Kustomize base, which feeds it to the container through `envFrom` — a `config.json` key there would additionally be offered as an environment variable, and `config.json` is not a valid environment variable name.

Field paths are verified against a live cluster rather than read off the XRD schemas. For the VM kinds that is not a formality: both XRDs declare `status.share` as an open object with **no** declared properties, so the schema says nothing about what is in it. Note that the renderer does not support array indexing (`spec.parentRefs[0].name`); point at the parent path and let it flatten.

## RBAC lives beside the watch set

The kinds machinery displays are configured in [`watch-config.yaml`](watch-config.yaml);
the permission to read them is in [`rbac.yaml`](rbac.yaml), deliberately in the
same directory.

It used to be in the kustomize base over in `stuttgart-things/machinery`. That
is a different repository, so #193 — which retargeted the watch set at this
fleet's XRs — changed what machinery looks at without changing what it may
read, and the two disagreed in silence.

The failure is easy to misread. The Deployment reports 1/1, the HTTPRoute
attaches, HTTPS answers in milliseconds — and every request is a 500, because
each informer is stuck on

```
clusterstacks.config.stuttgart-things.com is forbidden:
User "system:serviceaccount:machinery:machinery" cannot list resource
"clusterstacks" in API group "config.stuttgart-things.com" at the cluster scope
```

The grant is read-only (`get`, `list`, `watch`) and cluster-scoped, because the
XRs are. It covers both groups this fleet uses, `config.stuttgart-things.com`
and `resources.stuttgart-things.com`, plus `kustomizations` in
`kustomize.toolkit.fluxcd.io`.

**Adding a kind to `watch-config.yaml` means adding its group here, in the same
commit.** That is the point of the two files being neighbours.

## Endpoints

| Endpoint | Description |
|---|---|
| `https://<hostname>.<domain>/` | HTMX dashboard |
| `machinery.<namespace>.svc:50051` | gRPC API, in-cluster, plaintext |
| `<grpc-hostname>.<domain>:443` | gRPC API through the Gateway, TLS — only with the `machinery-grpcroute` component |

## gRPC from another cluster

The `machinery-grpcroute` component of the cicd-platform bundle adds a
`GRPCRoute` (`./grpcroute`) on the Gateway's `https` listener, with its own
hostname: an HTTPRoute and a GRPCRoute on the same hostname conflict under the
Gateway API rules. It is opt-in because it exposes the API beyond the cluster
**without authentication** — machinery's `auth.enabled` is not set in
`watch-config.yaml` yet. Everything it serves is read-only status.

### Testing it

There is nothing to see in a **browser**: the route only matches
`resourceservice.ResourceService` calls over HTTP/2, so a page request
matches no rule. The dashboard stays on the HTTPRoute hostname.

machinery registers **no gRPC reflection**, so `grpcurl list` fails; hand it
the proto. Take the proto from the release the cluster runs -- with an older
one, grpcurl drops the fields it does not know (`conditions`, `generation`,
...) **without any warning**, and the response simply looks shorter.

```bash
# in a checkout of stuttgart-things/machinery at the deployed tag
H=machinery-grpc.machinery.4sthings.tiab.ssc.sva.de:443
P="-import-path resourceservice -proto resource_service.proto"

grpcurl $P -d '{"kind":"ClusterStack"}' $H resourceservice.ResourceService/GetResources
grpcurl $P -d '{"kind":"ClusterStack","name":"app-dev","namespace":"default"}' \
  $H resourceservice.ResourceService/GetResourceDetail
grpcurl $P -d '{"kind":"Kustomization","name":"machinery-xrs","namespace":"flux-system"}' \
  $H resourceservice.ResourceService/GetResourceDetail
grpcurl $P -d '{"kind":"ClusterStack"}' $H resourceservice.ResourceService/WatchResources
```

Or with `machinery-client` from the machinery release -- it defaults to
plaintext, so switch TLS on:

```bash
export MACHINERY_SERVER=machinery-grpc.machinery.4sthings.tiab.ssc.sva.de:443
export MACHINERY_INSECURE=false
machinery-client list  --kind=ClusterStack
machinery-client get   --kind=ClusterStack --name=app-dev --namespace=default
machinery-client watch --kind=ClusterStack
```

What a working route answers with, and what each failure means:

| Call | Expected |
|---|---|
| `GetResourceDetail` on an existing object | JSON with `ready`, `infoFields`, `conditions`, `generation`, `creationTimestamp` |
| an unknown name | `NotFound` |
| a kind not in `watch-config.yaml` | `InvalidArgument` (lists the valid kinds) |
| a configured kind whose CRD the cluster lacks | `Unavailable` |
| the same call with `-plaintext` on `:80` | `Unimplemented` -- the route is bound to `https` only, by design |
| `grpc.health.v1.Health/Check` through the Gateway | not routed (the rule matches `ResourceService` only); use `GetResources` as the reachability probe |

The certificate is the Gateway's wildcard certificate (`wildcard-machinery-tls`
on the machinery cluster). If the client does not trust the issuing CA, pass
`-cacert <ca.pem>` (grpcurl) or `--ca-cert` (machinery-client); `-insecure` /
`--tls-skip-verify` only for a quick look. The issuer is the lab CA
(`tiab.labda.sva.de`), so a container image does **not** trust it out of the
box -- mount the CA into the client.

### The Gateway must negotiate HTTP/2 (ALPN)

gRPC clients on grpc-go >= 1.67 (machinery-client, any current Go worker)
abort the TLS handshake when the listener negotiates no ALPN:

```
credentials: cannot check peer: missing selected ALPN property
```

That is a **Cilium install** setting, not a Gateway API or Flux one:
`gatewayAPI.enableAlpn` (and `enableAppProtocol`). Clusters built with
`sthings.rke` get it from stuttgart-things/deploy-configure-rke `2026.10.01`
on; `machinery` has it since 2026-10-01 (Cilium helm revision 4). Check a
listener:

```bash
echo | openssl s_client -connect machinery-grpc.<domain>:443 \
  -servername machinery-grpc.<domain> -alpn h2 2>/dev/null | grep -i alpn
# ALPN protocol: h2      <- ok
# No ALPN negotiated     <- current gRPC clients fail
```

**A green grpcurl proves nothing here**: grpcurl builds on older grpc-go
(e.g. 1.61) do not enforce ALPN and connect anyway. Test with
`machinery-client`, or check ALPN with openssl as above.
`GRPC_ENFORCE_ALPN_ENABLED=false` in the client is the escape hatch, not a
fix -- grpc-go will drop it.

## Note: PipelineRuns re-appearing daily

Machinery only **watches** Crossplane XRs (`AnsibleRun`, `VMProvision`, …) and surfaces their status — it does not create PipelineRuns itself. PipelineRuns shown in its dashboard are rendered by the `stage-time` compositions via Crossplane's `provider-kubernetes` `Object`s (`managementPolicies: ["*"]`).

If runs in the CI namespace appear to re-trigger every morning, the cause is the cluster-wide Tekton operator pruner deleting them, followed by Crossplane recreating them on the next reconcile. The fix lives in `cicd/tekton` — see that app's README section *Caveat: Pruner + Crossplane-managed PipelineRuns* and the opt-in `components/ci-namespace` component that annotates the namespace with `operator.tekton.dev/prune.skip=true`.
