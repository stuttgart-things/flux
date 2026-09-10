# cnpg-barman-cloud

Deploys the [Barman Cloud plugin](https://github.com/cloudnative-pg/plugin-barman-cloud)
for CloudNativePG: WAL archiving, base backups and recovery against S3-compatible
object storage.

It replaces the operator's in-tree `spec.backup.barmanObjectStore`, which
CloudNativePG 1.30 marks for removal in 1.31.0.

## What gets deployed

`release.yaml` -- the `plugin-barman-cloud` HelmRelease in the operator's
namespace, with the `objectstores.barmancloud.cnpg.io` CRD. It reuses the
`cloudnative-pg` HelmRepository that [`cnpg-operator`](../cnpg-operator) creates.

## Requirements

- `cnpg-operator` -- the plugin must live in the operator's namespace; the
  operator finds it by the `cnpg.io/pluginName` label on its Service.
- cert-manager -- the chart renders a self-signed Issuer and the two
  Certificates for operator <-> plugin TLS.

The bundle component `infra/platform/components/cnpg-barman-cloud` waits on
both.

## Using it

A Cluster opts in with an `ObjectStore` in its own namespace and

```yaml
spec:
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: <ObjectStore name>
```

plus a `ScheduledBackup` with `method: plugin` and
`pluginConfiguration.name: barman-cloud.cloudnative-pg.io`. A worked example,
including recovery, is `apps/tabletennis/components/schmetterpause-db-backup`.

## Substitution variables

| Var | Default | Notes |
|---|---|---|
| `CNPG_NAMESPACE` | `cnpg-system` | Must be the operator's namespace |
| `CNPG_BARMAN_CLOUD_VERSION` | `0.8.0` | `plugin-barman-cloud` chart version (app v0.15.0) |
