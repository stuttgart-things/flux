# stuttgart-things/flux/dapr-backstage-template-execution

Flux app for the `backstage-template-execution` Dapr workflow — triggers a
Backstage scaffolder template, polls the task, watches the resulting GitHub
Actions run on the opened PR, and optionally merges the PR.

Deployed via OCI kustomize base (built from KCL manifests in
`dapr-workflows/backstage-template-execution/deploy`).

## Kustomization Example

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: dapr-backstage-template-execution
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./apps/dapr-backstage-template-execution
  prune: true
  wait: true
  postBuild:
    substitute:
      DAPR_BACKSTAGE_TPL_NAMESPACE: backstage-workflows
      DAPR_BACKSTAGE_TPL_VERSION: 60b81b0cbb6b
      DAPR_BACKSTAGE_TPL_IMAGE_TAG: 60b81b0cbb6b
    substituteFrom:
      - kind: Secret
        name: dapr-backstage-template-execution-vars
EOF
```

The `dapr-backstage-template-execution-vars` Secret must provide:

| Key | Purpose |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` scope — used by `FetchGitHubRun` / `MergePullRequest` activities |
| `BACKSTAGE_AUTH_TOKEN` | Bearer token for the Backstage scaffolder API |
| `REDIS_PASSWORD` | Password for the Dapr state store / pub-sub Redis |

### Example Secret

Create it in the same namespace as the Flux Kustomization (typically
`flux-system`) so `substituteFrom` can resolve it. In production, encrypt
with SOPS / Sealed Secrets instead of committing the plain values.

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: dapr-backstage-template-execution-vars
  namespace: flux-system
type: Opaque
stringData:
  GITHUB_TOKEN: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  BACKSTAGE_AUTH_TOKEN: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  REDIS_PASSWORD: super-secret-redis-password
```

Or on the fly:

```bash
kubectl create secret generic dapr-backstage-template-execution-vars \
  --namespace flux-system \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --from-literal=BACKSTAGE_AUTH_TOKEN="$BACKSTAGE_AUTH_TOKEN" \
  --from-literal=REDIS_PASSWORD="$REDIS_PASSWORD"
```

## Triggering a workflow run (user-supplied input)

The app only runs the *worker*; an actual workflow instance is triggered by
POSTing a JSON payload — equivalent to
`dapr-workflows/backstage-template-execution/input.json` — to the Dapr
sidecar's workflow API. This input is **not** part of the flux app; it's
user-supplied at run time, same as the secret above. Typical pattern is a
ConfigMap holding `input.json` plus a `Job` that curls the sidecar.

The in-cluster sidecar is reachable at
`http://backstage-template-execution-dapr.<namespace>.svc.cluster.local:3500`
once the Deployment is running.

### Example ConfigMap + trigger Job

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: dapr-backstage-tpl-input
  namespace: backstage-workflows
data:
  input.json: |
    {
      "backstageURL": "https://backstage.platform.sthings-vsphere.labul.sva.de",
      "templateRef": "template:default/create-terraform-vm",
      "dryRun": false,
      "values": {
        "lab": "LabUL",
        "cloud": "proxmox",
        "vm_name": "dapr-monday-1"
      },
      "watch": {
        "owner": "stuttgart-things",
        "repo": "stuttgart-things",
        "workflowFile": "pr-vm-deploy.yaml",
        "branch": "proxmox-vm-dapr-monday-1-labul",
        "timeoutMin": 30,
        "merge": {"enabled": true, "method": "squash"}
      }
    }
---
apiVersion: batch/v1
kind: Job
metadata:
  name: trigger-backstage-tpl-create-vm
  namespace: backstage-workflows
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: Never
      volumes:
        - name: input
          configMap:
            name: dapr-backstage-tpl-input
      containers:
        - name: trigger
          image: curlimages/curl:8.11.1
          volumeMounts:
            - name: input
              mountPath: /input
              readOnly: true
          command:
            - sh
            - -c
            - |
              set -eu
              INSTANCE_ID="run-$(date +%s)"
              SIDECAR="http://backstage-template-execution-dapr.backstage-workflows.svc.cluster.local:3500"
              echo "starting workflow instance: $INSTANCE_ID"
              curl -sS -X POST \
                "${SIDECAR}/v1.0-beta1/workflows/dapr/BackstageTemplateWorkflow/start?instanceID=${INSTANCE_ID}" \
                -H "Content-Type: application/json" \
                --data-binary @/input/input.json
              echo
              echo "instance started: $INSTANCE_ID"
```

Apply both, then watch the worker pod logs or poll
`${SIDECAR}/v1.0-beta1/workflows/dapr/<instanceID>` for status. The same
`input.json` format as the local `run.sh` workflow — the worker env var
fallbacks (`BACKSTAGE_AUTH_TOKEN`) mean you don't need to embed tokens
in the payload.

For a scheduled run, swap `Job` for `CronJob`.

## Layout

- `requirements.yaml` — Namespace + OCIRepository pointing at the pushed kustomize base
- `release.yaml` — Flux Kustomization; overrides image tag and deletes the placeholder Secrets / CA ConfigMap that ship in the base
- `secrets.yaml` — real Secrets resolved via `substituteFrom` (GITHUB_TOKEN, BACKSTAGE_AUTH_TOKEN, REDIS_PASSWORD)
- `kustomization.yaml` — glues the above together

## Versioning

The OCI artifact is built by `task build-scan-image-ko` in the
`dapr-workflows` repo, which also pushes a kustomize base tagged with the
same short random tag as the container image (e.g. `60b81b0cbb6b`). Bump
`DAPR_BACKSTAGE_TPL_VERSION` (OCI artifact tag) and
`DAPR_BACKSTAGE_TPL_IMAGE_TAG` (container image tag) together.
