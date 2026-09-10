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

# An ALTERNATIVE stands in for another component: the same child Kustomization,
# under the same name, wired differently (velero-eso for velero). It declares
# that with a line `# bundle-alternative-of: <component>` in its
# kustomization.yaml. Selecting both is one object defined twice, so "every
# component at once" cannot include them -- the main build leaves alternatives
# out, and each is then built again IN PLACE of the component it replaces.
# Skipping them instead would be the "reports OK while unverified" case above.
alternative_of() {
  sed -n 's/^# bundle-alternative-of: *//p' "$1/kustomization.yaml" 2>/dev/null | head -1
}

# build <bundle> <what> <component dir>... -- leaves the output in $out.
build() {
  local bundle=$1 what=$2
  shift 2
  {
    echo "---"
    echo "apiVersion: kustomize.config.k8s.io/v1beta1"
    echo "kind: Kustomization"
    echo "resources:"
    echo "  - ../$bundle/root"
    echo "components:"
    for dir in "$@"; do echo "  - ../$dir"; done
  } > "$tmp/kustomization.yaml"

  if ! out=$(kustomize build "$tmp" 2>&1); then
    echo "FAIL: $bundle does not build $what" >&2
    echo "$out" >&2
    exit 1
  fi
}

total=0
for bundle in $bundles; do
  regular=()
  alternatives=()
  for dir in "$bundle"/components/*/; do
    if [ -n "$(alternative_of "$dir")" ]; then alternatives+=("$dir"); else regular+=("$dir"); fi
  done

  build "$bundle" "with every component selected" "${regular[@]}"
  n=$(ls -d "$bundle"/components/*/ | wc -l)
  count=$(grep -c '^kind: Kustomization' <<<"$out" || true)
  echo "OK: $bundle -- $n components, builds, $count child Kustomizations"

  for alt in "${alternatives[@]}"; do
    replaced=$(alternative_of "$alt")
    if [ ! -d "$bundle/components/$replaced" ]; then
      echo "FAIL $(basename "$alt"): declares itself an alternative of '$replaced', which is not a component of $bundle" >&2
      exit 1
    fi
    swapped=()
    for dir in "${regular[@]}"; do
      [ "$dir" = "$bundle/components/$replaced/" ] || swapped+=("$dir")
    done
    build "$bundle" "with $(basename "$alt") in place of $replaced" "${swapped[@]}" "$alt"
    echo "OK: $bundle -- $(basename "$alt") builds in place of $replaced"
  done
  total=$((total + n))
done
echo "OK: $total components across $(echo $bundles | wc -w) bundles"
