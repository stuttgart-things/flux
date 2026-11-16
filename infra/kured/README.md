# kured

[kured](https://kured.dev) (Kubernetes Reboot Daemon, CNCF): reboots a node
once the OS asked for it, one node at a time, with cordon and drain.

Ubuntu writes `/var/run/reboot-required` after a kernel or libc update and then
waits. kured does that reboot: every `KURED_PERIOD` it checks the sentinel, and
inside the window it takes a cluster-wide lock (an annotation on its DaemonSet),
cordons and drains the node, reboots it and uncordons it once it is back.
kured installs nothing; the updates come from unattended-upgrades on the node.

Same defaults as the Argo CD catalog's `infra/kured/install`
(stuttgart-things/argocd), so both fleets reboot the same way.

## Consume

`../components/kured` in the cluster's `infra-platform` bundle. **It reboots
nodes** -- add it only where that should happen unattended.

| Variable | Default | |
|---|---|---|
| `KURED_NAMESPACE` | `kube-system` | |
| `KURED_VERSION` | `6.1.0` | upstream chart `kubereboot/kured` |
| `KURED_PERIOD` | `1h` | sentinel check interval |
| `KURED_START_TIME` / `KURED_END_TIME` / `KURED_TIME_ZONE` | `04:00` / `06:00` / `UTC` | reboot window |
| `KURED_DRAIN_TIMEOUT` | `15m` | then the reboot happens anyway (`forceReboot`) |
| `KURED_SUSPEND` | `false` | freezes reconciliation; the DaemonSet keeps rebooting. Remove the component to stop it |

Not threaded, change them with a patch on the HelmRelease: the reboot days
(`mo`–`fr`, a list) and `forceReboot` (`true`, a bool).

## Drains that never finish

A single-instance CloudNativePG cluster keeps a PodDisruptionBudget on its
primary, and on a single-node cluster nothing can move. Both block a drain. With
`forceReboot: true` kured reboots after `KURED_DRAIN_TIMEOUT` anyway and the pods
come back with the node; with `false` the node stays cordoned until someone
looks.

## Check

```bash
kubectl -n kube-system get ds kured
kubectl -n kube-system logs ds/kured | grep -i -E "reboot|drain|lock"
kubectl get nodes -o custom-columns=NAME:.metadata.name,REBOOT:.metadata.annotations.weave\.works/kured-reboot-in-progress
```
