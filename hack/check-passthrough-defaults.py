#!/usr/bin/env python3
"""A bundle's pass-through default must match the default it is passing through.

A Flux Kustomization that threads a value into a child writes it twice:

    # cicd/platform/components/crossplane/ks-crossplane.yaml
    CROSSPLANE_HELM_PROVIDER_VERSION: "${CROSSPLANE_HELM_PROVIDER_VERSION:-v1.2.0}"

    # cicd/crossplane/components/install/release.yaml   <- what spec.path builds
    - xpkg.upbound.io/crossplane-contrib/provider-helm:${CROSSPLANE_HELM_PROVIDER_VERSION:-v1.4.0}

The copy WINS. A child Kustomization cannot inherit a default -- an empty
substitute value renders as YAML null and the API server rejects the CR -- so
the copy has to exist, and bumping only the base silently keeps installing the
old version. Every object stays Ready; nothing anywhere reports it.

Three of these were live at once when this check was written: the two crossplane
providers above (cicd-test2 ran provider-helm v1.2.0 for a day), ARGO_CD_VERSION
(9.4.15 vs 10.4.0) and CLUSTERBOOK_OPERATOR_VERSION (v0.19.0 vs v0.20.0, so the
argocd-platform bundle installed the older operator wherever it was used).

Scoped to the path the Kustomization actually builds, which is what makes it
usable: comparing every ${VAR:-x} in the repo against every other flags a dozen
generic names -- INGRESS_HOSTNAME, STORAGE_CLASS, FLUX_SOURCE -- that legitimately
differ between apps. Rendered with kustomize, so a default reached through a
component or a base counts too.

A deliberate override is declared by putting `# passthrough-override: <reason>`
on the line above.
"""
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KS_API = "kustomize.toolkit.fluxcd.io"

# "${NAME:-value}" and nothing else -- the pass-through shape. A value that
# merely CONTAINS the variable is a composed string, not a copied default.
SELF = re.compile(r'^\$\{([A-Z0-9_]+):-(.*)\}$', re.S)
ANY = re.compile(r'\$\{([A-Z0-9_]+):-([^}]*)\}')

_cache = {}


def rendered(path: Path):
    key = str(path)
    if key not in _cache:
        out = subprocess.run(["kustomize", "build", str(path)],
                             capture_output=True, text=True)
        _cache[key] = out.stdout if out.returncode == 0 else None
    return _cache[key]


def defaults_for(text, name):
    return {m.group(2) for m in ANY.finditer(text) if m.group(1) == name}


def norm(v):
    v = str(v).strip()
    if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def overridden(file: Path, name):
    """A `# passthrough-override:` comment above the line declaring `name`."""
    lines = file.read_text().splitlines()
    for i, line in enumerate(lines):
        if re.match(rf'\s*{name}:\s', line):
            for prev in reversed(lines[max(0, i - 3):i]):
                if "passthrough-override:" in prev:
                    return True
                if not prev.strip().startswith("#"):
                    break
    return False


def main():
    fail = 0
    checked = 0
    skipped = set()

    for f in sorted(ROOT.rglob("*.yaml")):
        if ".git" in f.parts:
            continue
        try:
            docs = list(yaml.safe_load_all(f.read_text()))
        except yaml.YAMLError:
            continue
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Kustomization":
                continue
            if KS_API not in str(doc.get("apiVersion", "")):
                continue
            spec = doc.get("spec") or {}
            subs = ((spec.get("postBuild") or {}).get("substitute") or {})
            path = spec.get("path")
            if not subs or not path:
                continue

            # The path is resolved inside the SOURCE, which for a foreign
            # source (argocd-catalog, an upstream repo) is not this checkout.
            # Those are unverifiable here rather than wrong.
            target = ROOT / str(path).lstrip("./")
            if not target.is_dir():
                skipped.add(str(path))
                continue
            text = rendered(target)
            if text is None:
                skipped.add(str(path))
                continue

            for name, value in subs.items():
                m = SELF.match(str(value).strip())
                if not m or m.group(1) != name:
                    continue
                here = norm(m.group(2))
                there = {norm(x) for x in defaults_for(text, name)}
                if not there:
                    continue
                checked += 1
                if here in there:
                    continue
                if overridden(f, name):
                    continue
                rel = f.relative_to(ROOT)
                print(f"FAIL {rel}: {name} defaults to {here!r} here, but "
                      f"{path} defaults it to {', '.join(sorted(repr(t) for t in there))}",
                      file=sys.stderr)
                print(f"     The copy above WINS, so the value in {path} is "
                      f"never used and that component installs {here!r}. Bump "
                      f"both, or mark this line with "
                      f"`# passthrough-override: <reason>`.", file=sys.stderr)
                fail = 1

    if skipped:
        print(f"note: {len(skipped)} path(s) not in this checkout, not checked")
    if not fail:
        print(f"OK: {checked} pass-through default(s) match the path they thread into")
    return fail


if __name__ == "__main__":
    sys.exit(main())
