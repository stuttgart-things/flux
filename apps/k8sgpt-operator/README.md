# k8sgpt-operator

Deploys the [K8sGPT operator](https://github.com/k8sgpt-ai/k8sgpt-operator)
and, in [`scan/`](scan), one `K8sGPT` CR that scans the cluster **without an
AI backend** (`ai.enabled: false`).

The operator runs k8sgpt's analyzers every `K8SGPT_ANALYSIS_INTERVAL` --
the defaults **without ConfigMap** (`spec.filters`, #1003: on platform-sthings
the ConfigMap analyzer produced 138 of 139 findings, empty or unused
ConfigMaps), plus the Gateway API analyzers `GatewayClass`, `Gateway` and
`HTTPRoute` (#1011; acceptance and references, not reachability; without the
Gateway API CRDs they only log an analyzer error) -- and writes one
`Result` CR (`core.k8sgpt.ai/v1alpha1`) per finding into its namespace:
`spec.kind`, `spec.name`, `spec.parentObject` and `spec.error[].text`.
`spec.details` holds the AI explanation and stays empty here. A Result is
deleted once its problem is gone, so the Results are always the current
findings.

## What Gets Deployed

1. **requirements.yaml** — `Namespace` (`k8sgpt-operator-system`) and the
   `k8sgpt` HelmRepository (`https://charts.k8sgpt.ai`).
2. **release.yaml** — the `k8sgpt-operator` HelmRelease with its CRDs
   (`K8sGPT`, `Result`, `Mutation`) via `crds: CreateReplace`; Interplex off.
3. **scan/k8sgpt.yaml** — the `K8sGPT` CR. It is a **separate path**: its kind
   exists only after the HelmRelease installed the CRDs, so it needs its own
   Kustomization with `dependsOn` on the operator (the platform component does
   exactly that).

## Substitution Variables

| Var | Default | Path | Notes |
|---|---|---|---|
| `K8SGPT_NAMESPACE` | `k8sgpt-operator-system` | both | Operator, CR and Results |
| `K8SGPT_OPERATOR_VERSION` | `0.2.29` | `.` | `k8sgpt-operator` chart version |
| `K8SGPT_OPERATOR_CPU_REQUEST` | `10m` | `.` | |
| `K8SGPT_OPERATOR_MEMORY_REQUEST` | `64Mi` | `.` | |
| `K8SGPT_OPERATOR_MEMORY_LIMIT` | `256Mi` | `.` | |
| `K8SGPT_NAME` | `k8sgpt` | `scan` | Name of the K8sGPT CR |
| `K8SGPT_ANALYSIS_INTERVAL` | `5m` | `scan` | `^[0-9]+[smh]$` |
| `K8SGPT_VERSION` | `v0.4.41` | `scan` | k8sgpt server image tag (`ghcr.io/k8sgpt-ai/k8sgpt`) |

## Enabling in a Cluster

Through the `apps-platform` bundle: add the component
`../components/k8sgpt-operator` (two Kustomizations, `k8sgpt-operator` and
`k8sgpt-scan`). Without the bundle, two Kustomizations on `./apps/k8sgpt-operator`
and `./apps/k8sgpt-operator/scan`, the second with
`dependsOn: [{name: k8sgpt-operator}]`.

## Reporting the findings

The operator's own sinks (Slack, Mattermost, CloudEvents) only send the AI
text, which is empty without AI, and its S3 `remoteCache` stores AI answers,
not reports. The findings are reported by watching the Results instead:

- **Remote clusters:** the `homerun2-k8s-pitcher-remote` component's preset
  carries a K8sGPT part (#1003, homerun2-k8s-pitcher v1.9.0): new, changed and
  resolved findings plus one snapshot of all open findings per hour, as system
  `k8sgpt-<cluster>` to the central omni-pitcher. It routes them to the stream
  `k8sgpt` (`apps/homerun2/components/omni-pitcher/routes-configmap.yaml`),
  which an archive (homerun2-s3-catcher) reads and nothing that posts to
  Teams, lights or speakers. Without this component on the cluster the part
  is inert.
- **A cluster with its own homerun2:** a k8s-pitcher with the same informer
  and collector (homerun2-k8s-pitcher `profiles/k8sgpt-results.yaml`).

## Verify

```bash
flux get hr -n k8sgpt-operator-system            # k8sgpt-operator Ready
kubectl -n k8sgpt-operator-system get k8sgpt,pods # k8sgpt CR + its k8sgpt server pod
kubectl -n k8sgpt-operator-system get results     # the findings (after one interval)
kubectl -n k8sgpt-operator-system get result <name> -o jsonpath='{.spec.error[*].text}'
```
