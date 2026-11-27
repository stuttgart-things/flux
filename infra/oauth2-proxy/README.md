# oauth2-proxy

[oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) in front of ONE
app that has no login of its own, so its UI is only reachable after an OIDC
(ZITADEL) login (stuttgart-things/stuttgart-things#5023). One instance per
protected app; a platform component per app sets the upstream and the
hostname:

| Component | Protects | Default host |
|---|---|---|
| `prometheus-oauth2-proxy` | kube-prometheus-stack's Prometheus UI | `prometheus.<INFRA_DOMAIN>` |
| `alertmanager-oauth2-proxy` | kube-prometheus-stack's Alertmanager UI | `alertmanager.<INFRA_DOMAIN>` |
| `argo-rollouts-dashboard-oauth2-proxy` (cicd bundle, add-on to `argo-rollouts`) | the Argo Rollouts dashboard | `argo-rollouts.<INFRA_DOMAIN>` (`ARGO_ROLLOUTS_HOSTNAME`) |

Why one proxy per app and not one Gateway-level auth for all: the Gateway API
`ExternalAuth` filter needs Cilium >= 1.20 and the experimental Gateway API
CRDs; the labs run Cilium 1.18/1.19 with the standard channel.

## Client model: one ZITADEL client per cluster

All proxies of a cluster share ONE confidential ZITADEL client (web app, code
flow with PKCE) and one Secret:

| Secret `OAUTH2_PROXY_SECRET_NAME` (default `oauth2-proxy`) | |
|---|---|
| `client-id` | the client's ID |
| `client-secret` | the client's secret |
| `cookie-secret` | 32 random bytes, e.g. `openssl rand -base64 32 \| head -c 32 \| base64` |

It must exist in the namespace of every proxy (SOPS or ESO). Each proxy adds
one redirect URI to the client: `https://<host>/oauth2/callback`. The cookie
`_oauth2_proxy` is set for `.<INFRA_DOMAIN>`, with the same secret everywhere,
so **one login opens every protected app of the cluster**.

**Who may log in is decided by ZITADEL**: put the client in a project with
"check for project role on authentication" -- only users with a role on that
project get a token. oauth2-proxy has no group check here: its groups claim
must be a list, and ZITADEL's roles claim is a map.

## Variables

| Variable | Default | |
|---|---|---|
| `OAUTH2_PROXY_ISSUER` | *(required)* | ZITADEL issuer, as in the discovery document |
| `OAUTH2_PROXY_SECRET_NAME` | `oauth2-proxy` | the Secret above |
| `OAUTH2_PROXY_CA_CONFIGMAP` / `_KEY` | `cluster-trust-bundle` / `trust-bundle.pem` | the issuer's CA (`--provider-ca-file`) |
| `OAUTH2_PROXY_VERSION` | `10.7.4` | oauth2-proxy Helm chart |
| `PROMETHEUS_UI_HOSTNAME` / `ALERTMANAGER_UI_HOSTNAME` | `prometheus` / `alertmanager` | host prefix under `INFRA_DOMAIN` |

The base itself reads `OAUTH2_PROXY_NAME`, `OAUTH2_PROXY_NAMESPACE`,
`OAUTH2_PROXY_UPSTREAM`, `GATEWAY_NAME`, `GATEWAY_NAMESPACE`, `HOSTNAME` and
`DOMAIN`; the components set them.

## Adding an app

Copy `../platform/components/prometheus-oauth2-proxy`, change the name,
upstream (`http://<svc>.<ns>.svc.cluster.local:<port>`), namespace, hostname
variable and `dependsOn`, and add the new component to the
`./infra/oauth2-proxy` entry's users in `hack/check-shared-path-wiring.py`'s
comment. If the app already routes its UI, drop that route: the proxy's
HTTPRoute takes the hostname.
