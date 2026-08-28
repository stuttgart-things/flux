#!/usr/bin/env bash
# Every directory under infra/platform/components must be a usable kustomize
# Component, and the bundle must build with all of them selected.
#
# Both halves exist because a component that is merely *present* is not a
# component. kustomize looks for a file literally named kustomization.yaml; a
# `kind: Component` document sitting inside some other file is invisible to it,
# and the failure surfaces only on a cluster, as
#
#   kustomize build failed: accumulating components: accumulateDirectory:
#   couldn't make target for path '.../components/<name>': unable to find one of
#   'kustomization.yaml', 'kustomization.yml' or 'Kustomization' in directory
#
# -- after the consumer has already merged and repinned. That happened with
# cert-manager-vault-issuer.
set -euo pipefail

cd "$(dirname "$0")/.."
# Both bundles. apps/platform mirrors infra/platform for the app layer, and a
# check that silently covers only one of them is worse than none: it reports OK
# while half the components are unverified.
#
# cicd/platform is the third: the delivery layer -- argo-cd, tekton, dapr,
# crossplane. It was added to this list in the same commit that created it,
# because a bundle outside the list is exactly the "reports OK while
# unverified" case the paragraph above describes.
bundles="infra/platform apps/platform cicd/platform"
fail=0

for components_dir in $bundles; do
components_dir="$components_dir/components"
for dir in "$components_dir"/*/; do
  name=$(basename "$dir")
  if [ ! -f "$dir/kustomization.yaml" ] && [ ! -f "$dir/kustomization.yml" ] && [ ! -f "$dir/Kustomization" ]; then
    echo "FAIL $name: no kustomization.yaml -- kustomize cannot see this directory" >&2
    fail=1
    continue
  fi
  if ! grep -q 'kind: Component' "$dir"/kustomization.y*ml 2>/dev/null; then
    echo "FAIL $name: kustomization.yaml is not kind: Component" >&2
    fail=1
  fi
done
done

[ "$fail" -eq 0 ] || exit 1

# And they have to compose. Selecting every component at once is the strictest
# cheap check: a bad path or a duplicate resource name shows up here.
# The scratch dir lives INSIDE the repo: kustomize refuses absolute paths in
# `resources`, so everything has to be reachable relatively.
tmp=".bundle-check"
rm -rf "$tmp"; mkdir -p "$tmp"
trap 'rm -rf "$tmp"' EXIT

total=0
for bundle in $bundles; do
  {
    echo "---"
    echo "apiVersion: kustomize.config.k8s.io/v1beta1"
    echo "kind: Kustomization"
    echo "resources:"
    echo "  - ../$bundle/root"
    echo "components:"
    for dir in "$bundle"/components/*/; do echo "  - ../$dir"; done
  } > "$tmp/kustomization.yaml"

  if ! out=$(kustomize build "$tmp" 2>&1); then
    echo "FAIL: $bundle does not build with every component selected" >&2
    echo "$out" >&2
    exit 1
  fi

  n=$(ls -d "$bundle"/components/*/ | wc -l)
  count=$(grep -c '^kind: Kustomization' <<<"$out" || true)
  echo "OK: $bundle -- $n components, builds, $count child Kustomizations"
  total=$((total + n))
done
echo "OK: $total components across $(echo $bundles | wc -w) bundles"
