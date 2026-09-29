#!/usr/bin/env bash
# Every AppProfile has the shape the app-profile KCL schema allows.
#
# check-app-profiles.py compares a profile's vars and keys with its component;
# this checks the values themselves -- generate types, ref syntax, unknown
# fields -- against ghcr.io/stuttgart-things/app-profile, the schema
# blueprints' render-cluster-apps reads profiles with.
#
# APP_PROFILE_SCHEMA=<path to main.k> skips the pull, e.g. to test a schema
# change from a kcl checkout before it is published.
set -euo pipefail

VERSION="${APP_PROFILE_VERSION:-0.1.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

schema="${APP_PROFILE_SCHEMA:-}"
if [ -z "$schema" ]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  (cd "$tmp" && kcl mod pull oci://ghcr.io/stuttgart-things/app-profile --tag "$VERSION" >/dev/null)
  schema="$tmp/oci/ghcr.io/stuttgart-things/app-profile/$VERSION/main.k"
fi

fail=0
count=0
for f in "$ROOT"/*/platform/components/*/profile.yaml; do
  [ -e "$f" ] || continue
  count=$((count + 1))
  if ! out="$(kcl vet "$f" "$schema" -s AppProfile --format yaml 2>&1)"; then
    echo "FAIL ${f#"$ROOT"/}:" >&2
    echo "$out" | sed 's/\x1b\[[0-9;]*m//g; s/^/  /' >&2
    fail=1
  fi
done

[ "$fail" = 0 ] && echo "OK: $count AppProfile(s) match the app-profile $VERSION schema"
exit "$fail"
