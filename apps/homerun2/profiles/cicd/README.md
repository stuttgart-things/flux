# homerun2 / profiles / cicd

Git event watching for homerun2. **This is an add-on, not a standalone stack:**
it composes `git-pitcher` and nothing else.

Deploy it as its own Flux Kustomization *alongside* a
[`profiles/base`](../base/README.md) one. Both point at the same
`HOMERUN2_NAMESPACE`; base brings Redis and the catchers, this brings the
pitcher that feeds them from Git.

That split is deliberate — folding the core stack in here would make two
Kustomizations own the same Redis, omni-pitcher and core-catcher objects, and
would require this one to carry gateway/hostname variables it has no use for.
See `clusters/labul/vsphere/platform-sthings/apps/homerun2-cicd-stack.yaml` for
a live example.

## Components

| Component | Description |
|-----------|-------------|
| `git-pitcher` | Watches Git repositories and pitches events to Redis Streams |

## Usage

```yaml
path: ./apps/homerun2/profiles/cicd
```

## Required Variables

| Variable | Description |
|----------|-------------|
| `HOMERUN2_NAMESPACE` | Shared namespace — must match the `profiles/base` deployment |
| `HOMERUN2_GIT_PITCHER_VERSION` | Git-pitcher OCI + image tag |
| `HOMERUN2_REDIS_PASSWORD_B64` | Base64-encoded Redis password (from Secret) |
| `HOMERUN2_GIT_PITCHER_GITHUB_TOKEN_B64` | Base64-encoded GitHub PAT (from Secret) |

Optional: `FLUX_SOURCE_API_VERSION` (OCIRepository apiVersion, default `v1`),
`HOMERUN2_GIT_PITCHER_WATCH_CONFIG_CM`, `HOMERUN2_GIT_PITCHER_TRUST_BUNDLE_CM`.
That is the component's complete variable surface — verified against
`components/git-pitcher/`, not inherited from the old core-stack write-up.

Redis connection details come from the `profiles/base` deployment in the same
namespace; this profile does not deploy Redis.

## Additional Resources

The git-pitcher component deletes the KCL-generated watch ConfigMap. You must
provide a cluster-side `homerun2-git-pitcher-watch-config` ConfigMap with the
watch profile. See the [git-pitcher component README](../../components/git-pitcher/README.md).
