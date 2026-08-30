#!/usr/bin/env python3
"""Two Kustomizations rendering the same path must be wired the same way.

A path under this repository can be rendered by more than one Flux
Kustomization -- ./cicd/argo-cd is rendered both by the `argo-cd` component and
by the argocd-platform base, which installs the same ArgoCD as part of a
control plane. Nothing keeps the two in step, and on 2026-08-30 they were not:
argocd-platform had drifted away from the component it duplicates and was
missing

  * both kustomize components -- no-ingress-cert and httproute -- so the
    cluster got an ArgoCD with no HTTPRoute and no Ingress (a 404 from the
    Gateway, while every pod was healthy and every Kustomization Ready), plus
    an argocd-ingress Certificate nothing mounts;
  * the ISSUER_NAME / INGRESS_DOMAIN threading, so the base's own defaults won
    -- an issuer that exists on no other cluster, and another lab's domain.

None of that failed loudly. The Certificate parked InProgress, the HelmRelease
waited for it and timed out, and eight Kustomizations reported "dependency not
ready" -- pointing at each other rather than at the wiring.

WHAT IS DERIVED: which paths have more than one Kustomization. A new
duplication is therefore NOTICED the day it appears rather than the day it
breaks, and an undeclared one fails this check on purpose -- somebody has to
say whether the two are meant to agree.

WHAT CANNOT BE DERIVED is that answer. ./apps/dapr/root is also rendered twice,
by `dapr` and by `dapr-workflows`, and those are two flavours of one app that
differ deliberately in both directions. Nothing in the YAML distinguishes that
from drift, so it is stated once, below.
"""
import collections
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Paths whose Kustomizations must stay in step, and what one may carry beyond
# the other. The extras are named rather than counted: a key that stops being
# explained is a key somebody should look at again.
MUST_MATCH = {
    "./cicd/argo-cd": {
        "why": "argocd-platform installs the same ArgoCD as the argo-cd "
               "component, from the same path, and has to wire it the same way",
        # Read by the argocd-certificate block in cicd/argo-cd/pre-release.yaml.
        # Both wirings apply no-ingress-cert, which removes that block, so these
        # are inert today -- and still correct to carry: a variant WITHOUT that
        # component needs every one of them.
        "extra_allowed": {
            "INGRESS_DOMAIN",
            "INGRESS_HOSTNAME",
            "INGRESS_SECRET_NAME",
            "ISSUER_NAME",
            "ISSUER_KIND",
        },
    },
    "./apps/clusterbook-operator": {
        "why": "the clusterbook-operator component and argocd-platform install "
               "the same operator from the same path -- argocd-platform orders "
               "it behind argo-cd because it writes Argo CD cluster-secrets, "
               "but what it installs has to be identical",
        # Nothing. Both thread NAMESPACE and VERSION and neither should grow a
        # key the other lacks: the base's remaining variables (the trust-bundle
        # mount, FLUX_SOURCE_API_VERSION) all carry usable defaults, so adding
        # one here means adding it there in the same commit.
        "extra_allowed": set(),
    },
}

# Rendered more than once ON PURPOSE, and not comparable.
DIVERGENT = {
    "./apps/dapr/root": "dapr and dapr-workflows are two flavours of one app: "
                        "the workflow one adds template-execution, redis-stack, "
                        "redis-auth and backstage-ca, the plain one adds "
                        "control-plane. Each carries components and variables "
                        "the other must not have.",
}


def kustomizations():
    """(path, file, name, components, substitute keys) for every Flux Kustomization."""
    for f in sorted(ROOT.rglob("*.yaml")):
        if ".git" in f.parts:
            continue
        try:
            docs = list(yaml.safe_load_all(f.read_text()))
        except (yaml.YAMLError, UnicodeDecodeError):
            continue
        for d in docs:
            if not isinstance(d, dict) or d.get("kind") != "Kustomization":
                continue
            if "kustomize.toolkit.fluxcd.io" not in str(d.get("apiVersion", "")):
                continue
            spec = d.get("spec") or {}
            path = spec.get("path")
            if not path:
                continue
            yield (
                path,
                str(f.relative_to(ROOT)),
                (d.get("metadata") or {}).get("name", "?"),
                set(spec.get("components") or []),
                set(((spec.get("postBuild") or {}).get("substitute") or {})),
            )


def main():
    by_path = collections.defaultdict(list)
    for path, f, name, comps, subs in kustomizations():
        by_path[path].append((f, name, comps, subs))

    shared = {
        p: v for p, v in by_path.items()
        if len({f for f, _, _, _ in v}) > 1
    }

    problems = []
    for path, entries in sorted(shared.items()):
        if path in DIVERGENT:
            print(f"ok (divergent on purpose)  {path}")
            continue
        if path not in MUST_MATCH:
            problems.append(
                f"{path} is rendered by {len(entries)} Kustomizations and this "
                f"check does not know whether they are meant to agree:\n"
                + "".join(f"      {n}  ({f})\n" for f, n, _, _ in entries)
                + "    Add it to MUST_MATCH (they duplicate each other) or to "
                  "DIVERGENT (they are different on purpose), with the reason."
            )
            continue

        rule = MUST_MATCH[path]
        extra_ok = rule["extra_allowed"]
        base = entries[0]
        for other in entries[1:]:
            (fa, na, ca, sa), (fb, nb, cb, sb) = base, other

            if ca != cb:
                only_a = sorted(x.rsplit("/", 1)[-1] for x in ca - cb)
                only_b = sorted(x.rsplit("/", 1)[-1] for x in cb - ca)
                problems.append(
                    f"{path}: {na} and {nb} apply different kustomize components.\n"
                    f"    only {na}: {only_a or '-'}\n"
                    f"    only {nb}: {only_b or '-'}\n"
                    f"    {rule['why']}."
                )

            for missing, where, whose in ((sa - sb - extra_ok, nb, na),
                                          (sb - sa - extra_ok, na, nb)):
                if missing:
                    problems.append(
                        f"{path}: {where} does not thread {sorted(missing)}, "
                        f"which {whose} does.\n"
                        f"    Flux does not inherit postBuild.substitute, so a "
                        f"cluster setting one of these gets {where}'s default "
                        f"instead -- silently.\n"
                        f"    {rule['why']}."
                    )

        if not problems:
            names = ", ".join(n for _, n, _, _ in entries)
            print(f"ok  {path}  ({names})")

    if problems:
        print(file=sys.stderr)
        for p in problems:
            print(f"  {p}\n", file=sys.stderr)
        sys.exit(1)

    print(f"OK: {len(shared)} path(s) rendered by more than one Kustomization, "
          f"all as declared")


if __name__ == "__main__":
    main()
