# stuttgart-things/flux/machinery-order-service

OCI kustomize-based app (`OCIRepository` + Flux `Kustomization`) with a Gateway API `HTTPRoute`.
[machinery-order-service](https://github.com/stuttgart-things/machinery-order-service)
takes orders for machinery resources over REST. It renders them through claim-machinery-api,
opens the pull request in the GitOps repo and follows each order through Flux and machinery
to Ready. It never applies anything to a management cluster; its only write path is git.

Selected through the bundle component `apps/platform/components/machinery-order-service`,
one instance per lab on the lab's infra cluster.

## SUBSTITUTION VARIABLES

| Variable | Default | Purpose |
|---|---|---|
| `MACHINERY_ORDER_SERVICE_VERSION` | `v0.1.1` | OCI tag of the kustomize base and the image tag |
| `MACHINERY_ORDER_SERVICE_BASE_PATH` | `/` | URL prefix behind sthings-portal, equal to the portal key (e.g. `/orders`) |
| `MACHINERY_ORDER_SERVICE_ROUTE` | `all` | `api`: the own host serves `/api/...`, `/health`, `/ready` and `/version` only, and the UI is reachable only through the portal |
| `MACHINERY_ORDER_SERVICE_HOSTNAME` | `orders` | HTTPRoute hostname prefix |
| `INFRA_DOMAIN` | - (required) | HTTPRoute domain suffix |
| `INFRA_GATEWAY_NAME` / `_NAMESPACE` | `cilium-gateway` / `default` | Gateway parentRef |
| `MACHINERY_ORDER_SERVICE_TRUST_BUNDLE_CONFIGMAP` / `_KEY` | `cluster-trust-bundle` / `trust-bundle.pem` | trust-manager CA bundle, read through `SSL_CERT_DIR` |
| (Reloader) | on | `reloader.stakater.com/auto: "true"`; not a bundle variable, a bool would reach the child's substitute map as a non-string |
| `MACHINERY_ORDER_SERVICE_SUSPEND` | `false` | |

## FROM THE CLUSTER REPO

These objects live in the namespace `machinery-order-service`, which is fixed because the base's
ClusterRoleBinding names it:

- the `Namespace` itself, applied in the same Kustomization as the Secrets
- Secret `machinery-order-service-github-app`, key `private-key.pem`: the GitHub App key, SOPS-encrypted.
  The App needs `contents: write` and `pull_requests: write` on the GitOps repo.
- ConfigMap `machinery-order-service-cluster`: the environment, e.g. `CLAIM_API_URL`,
  `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `AUTH_OIDC_ISSUER`, `AUTH_OIDC_AUDIENCE`,
  `AUTH_OIDC_CA_FILE=/etc/ssl/custom/trust-bundle.pem`, `AUTH_TRUST_FORWARDED_USER`, `AUTH_ADMIN_ROLES`
- the machinery token Secrets that the ManagementClusters name (`tokenSecretRef`)
- the `ManagementCluster` objects, in a Kustomization of their own with
  `dependsOn: machinery-order-service`, because they need the CRDs from this app

The machinery watch config must carry the Flux Kustomization of the orders directory with the info
field `Revision` (`status.lastAppliedRevision`). `cicd/machinery/watch-config.yaml` already does.
