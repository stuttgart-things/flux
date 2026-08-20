#!/usr/bin/env bash
# Fail if a HelmRelease chart version behind Flux variable substitution is
# missing its "# renovate:" annotation.
#
# Renovate's flux manager cannot parse ${VAR:-1.2.3} in chart.spec.version; it
# drops the dep as "contains-variable" without a warning, so the chart simply
# never gets an update PR. The annotation on the preceding line is what feeds
# the custom manager instead.
set -euo pipefail

if [ "$#" -gt 0 ]; then
  roots=("$@")
else
  roots=(apps infra cicd)
fi

# shellcheck disable=SC2016  # the awk program must not be expanded by the shell
missing=$(find "${roots[@]}" -name '*.yaml' -print0 \
  | xargs -0 awk '
      FNR == 1 { prev = "" }
      /^[[:space:]]*version:[[:space:]]*\$\{[A-Z0-9_]+:-/ {
        if (prev !~ /#[[:space:]]*renovate:/) printf "  %s:%d\n", FILENAME, FNR
      }
      { prev = $0 }
    ')

if [ -n "${missing}" ]; then
  echo "Chart versions with no '# renovate:' annotation:"
  echo "${missing}"
  echo
  echo "Renovate will never propose an update for these."
  echo "Derive the annotation from the HelmRepository the sourceRef points at:"
  echo "  type: oci   -> # renovate: datasource=docker depName=<host>/<path>/<chart>"
  echo "  plain HTTPS -> # renovate: datasource=helm depName=<chart> registryUrl=<url>"
  echo "See CLAUDE.md -> Dependency Management."
  exit 1
fi

echo "OK: every substituted chart version is annotated."
