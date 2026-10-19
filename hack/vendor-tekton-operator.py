#!/usr/bin/env python3
"""Re-vendor the Tekton Operator release manifest into cicd/tekton/components/operator.

    hack/vendor-tekton-operator.py v0.81.2

Downloads the upstream Kubernetes `release.yaml` (NOT openshift-release.yaml)
for VERSION and splits it by kind:

    namespace.yaml      Namespace
    crd-<plural>.yaml   one file per CustomResourceDefinition
    rbac.yaml           ServiceAccount, (Cluster)Role(Binding)s
    config.yaml         ConfigMaps + webhook Secret
    deployment.yaml     Services + Deployments

and rewrites kustomization.yaml to list them. Documents keep upstream order
inside each file and are dumped with PyYAML defaults (sorted keys, width 80),
which is how v0.79.0 was vendored: re-running this for v0.79.0 reproduces
namespace/rbac/config/deployment.yaml byte for byte, and the crd-*.yaml files
hold exactly the documents of the former single crds.yaml.

Why one file per CRD: since v0.80 the CRDs carry full OpenAPI schemas and a
single crds.yaml is ~660 KB, over pre-commit's check-added-large-files limit
(500 KB). The files stay flat in one directory because the Argo CD catalog
(stuttgart-things/argocd cicd/tekton/operator) reads this path as a
`directory:` source with `recurse: false` -- a crds/ subdirectory would be
silently skipped there.
"""
import sys
import urllib.request
from pathlib import Path

import yaml

URL = "https://infra.tekton.dev/tekton-releases/operator/previous/{v}/release.yaml"
DEST = Path(__file__).resolve().parent.parent / "cicd/tekton/components/operator"

GROUP = {
    "Namespace": "namespace",
    "ServiceAccount": "rbac",
    "Role": "rbac",
    "ClusterRole": "rbac",
    "RoleBinding": "rbac",
    "ClusterRoleBinding": "rbac",
    "ConfigMap": "config",
    "Secret": "config",  # pragma: allowlist secret
    "Service": "deployment",
    "Deployment": "deployment",
}
ORDER = ["namespace", "crds", "rbac", "config", "deployment"]


def main(version: str) -> None:
    with urllib.request.urlopen(URL.format(v=version)) as resp:
        docs = [d for d in yaml.safe_load_all(resp.read()) if d]

    groups = {g: [] for g in ORDER if g != "crds"}
    crds = []
    for d in docs:
        kind = d["kind"]
        if kind == "CustomResourceDefinition":
            crds.append(d)
        elif kind in GROUP:
            groups[GROUP[kind]].append(d)
        else:
            sys.exit(f"unmapped kind {kind} ({d['metadata']['name']}) -- extend GROUP")

    for old in DEST.glob("crd*.yaml"):
        old.unlink()

    files = []
    for g in ORDER:
        if g == "crds":
            for d in crds:
                name = f"crd-{d['spec']['names']['plural']}.yaml"
                (DEST / name).write_text(yaml.safe_dump(d, default_flow_style=False))
                files.append(name)
            continue
        name = f"{g}.yaml"
        (DEST / name).write_text(yaml.safe_dump_all(groups[g], default_flow_style=False))
        files.append(name)

    kustomization = "---\napiVersion: kustomize.config.k8s.io/v1alpha1\nkind: Component\nresources:\n"
    kustomization += "".join(f"  - {f}\n" for f in files)
    (DEST / "kustomization.yaml").write_text(kustomization)

    print(f"{version}: {len(docs)} documents, {len(crds)} CRDs -> {DEST}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].startswith("v"):
        sys.exit(__doc__)
    main(sys.argv[1])
