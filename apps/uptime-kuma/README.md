# stuttgart-things/flux/uptime-kuma

## Deployment

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: uptime-kuma
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/uptime-kuma
  prune: true
  wait: true
  postBuild:
    substitute:
      UPTIME_KUMA_NAMESPACE: uptime-kuma
      UPTIME_KUMA_VERSION: "4.0.0"
      UPTIME_KUMA_STORAGE_CLASS: nfs4-csi
      UPTIME_KUMA_STORAGE_SIZE: 4Gi
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: uptime
      DOMAIN: example.sthings-vsphere.labul.sva.de
EOF
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `UPTIME_KUMA_NAMESPACE` | `uptime-kuma` | Target namespace |
| `UPTIME_KUMA_VERSION` | `4.0.0` | Helm chart version |
| `UPTIME_KUMA_STORAGE_CLASS` | `nfs4-csi` | StorageClass for persistent volume |
| `UPTIME_KUMA_STORAGE_SIZE` | `4Gi` | PVC size |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Components

- **release.yaml** - HelmRelease from `https://dirsigler.github.io/uptime-kuma-helm` with trust-bundle CA volume mount
- **httproute.yaml** - Gateway API HTTPRoute

## Setup Job (per-cluster)

The setup job is not included in the flux app — it's cluster-specific. Apply it separately after uptime-kuma is running to create an admin account and configure monitors.

```yaml
# Example: save as setup-job.yaml in your cluster folder
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: uptime-kuma-monitors
  namespace: uptime-kuma
data:
  monitors.json: |
    [
      {
        "name": "Flux Web UI",
        "type": "http",
        "url": "https://flux.example.sthings-vsphere.labul.sva.de",
        "interval": 60,
        "maxretries": 3
      },
      {
        "name": "Vault",
        "type": "http",
        "url": "https://vault.example.sthings-vsphere.labul.sva.de",
        "interval": 60,
        "maxretries": 3
      }
    ]
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: uptime-kuma-setup
  namespace: uptime-kuma
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: uptime-kuma-setup
  namespace: uptime-kuma
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: uptime-kuma-setup
  namespace: uptime-kuma
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: uptime-kuma-setup
subjects:
  - kind: ServiceAccount
    name: uptime-kuma-setup
    namespace: uptime-kuma
---
apiVersion: batch/v1
kind: Job
metadata:
  name: uptime-kuma-setup
  namespace: uptime-kuma
spec:
  backoffLimit: 5
  activeDeadlineSeconds: 600
  template:
    spec:
      restartPolicy: OnFailure
      serviceAccountName: uptime-kuma-setup
      containers:
        - name: setup
          image: python:3.12-slim
          command:
            - /bin/bash
            - -c
            - |
              pip install -q uptime-kuma-api kubernetes &&
              python3 /scripts/setup.py
          env:
            - name: KUMA_URL
              value: "http://uptime-kuma.uptime-kuma.svc:3001"
            - name: NAMESPACE
              value: "uptime-kuma"
            - name: ADMIN_USER
              value: "admin"
          volumeMounts:
            - name: scripts
              mountPath: /scripts
            - name: monitors
              mountPath: /config
      volumes:
        - name: scripts
          configMap:
            name: uptime-kuma-setup-script
        - name: monitors
          configMap:
            name: uptime-kuma-monitors
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: uptime-kuma-setup-script
  namespace: uptime-kuma
data:
  setup.py: |
    import json
    import os
    import secrets
    import string
    import time as _time
    from uptime_kuma_api import UptimeKumaApi
    from kubernetes import client, config

    url = os.environ["KUMA_URL"]
    namespace = os.environ["NAMESPACE"]
    user = os.environ["ADMIN_USER"]
    secret_name = "uptime-kuma-admin"

    config.load_incluster_config()
    v1 = client.CoreV1Api()

    password = None
    try:
        secret = v1.read_namespaced_secret(secret_name, namespace)
        import base64
        password = base64.b64decode(secret.data["password"]).decode()
        print(f"Found existing admin secret '{secret_name}'.")
    except client.exceptions.ApiException as e:
        if e.status == 404:
            alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(alphabet) for _ in range(24))
            secret = client.V1Secret(
                metadata=client.V1ObjectMeta(name=secret_name),
                type="Opaque",
                string_data={"username": user, "password": password}
            )
            v1.create_namespaced_secret(namespace, secret)
            print(f"Generated password and created secret '{secret_name}'.")
        else:
            raise

    print(f"Connecting to {url}...")
    api = None
    for attempt in range(12):
        try:
            api = UptimeKumaApi(url, timeout=30, wait_events=3)
            break
        except Exception as e:
            print(f"  Connection attempt {attempt+1}/12 failed: {e}")
            _time.sleep(15)
    if api is None:
        print("ERROR: Could not connect after all retries.")
        exit(1)

    if api.need_setup():
        print("Running initial setup...")
        api.setup(user, password)
        print("Admin account created.")
    else:
        print("Setup already done, logging in...")
        api.login(user, password)

    with open("/config/monitors.json") as f:
        desired = json.load(f)

    existing = {m["name"]: m for m in api.get_monitors()}
    print(f"Found {len(existing)} existing monitors.")

    for monitor in desired:
        name = monitor["name"]
        if name in existing:
            print(f"  Monitor '{name}' already exists, skipping.")
        else:
            print(f"  Creating monitor '{name}'...")
            api.add_monitor(**monitor)
            print(f"  Monitor '{name}' created.")

    print("Done. All monitors configured.")
    api.disconnect()
```

```bash
kubectl apply -f setup-job.yaml
kubectl logs -n uptime-kuma job/uptime-kuma-setup -f
```

## Claims CLI

```bash
claims render --non-interactive \
-t flux-kustomization-uptime-kuma \
-p uptimeKumaGatewayName=my-gateway \
-p uptimeKumaDomain=example.sthings-vsphere.labul.sva.de \
-o ./apps/ \
--filename-pattern "{{.name}}.yaml"
```

See also: [claims CLI](https://github.com/stuttgart-things/claims) | [claim-machinery-api](https://github.com/stuttgart-things/claim-machinery-api)
