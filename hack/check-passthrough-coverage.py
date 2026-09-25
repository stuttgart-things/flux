#!/usr/bin/env python3
"""A Kustomization marked `passthrough-complete` passes EVERY variable its path reads.

A child Kustomization sees only the variables in its own postBuild.substitute.
A cluster setting a value on the PARENT reaches the child only if the child's
list names it; otherwise the child renders the default, whatever the cluster
set, and every object stays Ready.

That was #514: the harvester-demo capability read five
CROSSPLANE_CAPABILITY_HARVESTER_* variables, ks-crossplane-capabilities passed
none of them, and a management cluster that set all five got `in-cluster`,
`harvester-longhorn` and `default/image-ubuntu` anyway -- a VM composed onto the
wrong cluster, behind a PVC that stayed Pending.

check-passthrough-defaults.py compares the defaults of variables that ARE
passed. This is the other half: variables that are not.

OPT-IN, because most Kustomizations here deliberately leave some variables to
their defaults. The marker is a `# passthrough-complete:` comment inside the
postBuild block. Every directory the spec.path can resolve to is rendered (a
substituted segment becomes a glob, as in check-passthrough-defaults.py), so a
variable read by ONE set among several still counts.
"""
import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KS_API = "kustomize.toolkit.fluxcd.io"
MARKER = "passthrough-complete:"

_spec = importlib.util.spec_from_file_location(
    "passthrough_defaults", ROOT / "hack" / "check-passthrough-defaults.py")
pd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pd)

READ = re.compile(r"\$\{([A-Z0-9_]+)(?::-[^}]*)?\}")


def marked_docs(f: Path):
    """The Kustomization documents in `f` whose postBuild block carries MARKER."""
    text = f.read_text()
    if MARKER not in text:
        return
    for chunk in re.split(r"(?m)^---\s*$", text):
        if MARKER not in chunk:
            continue
        try:
            doc = yaml.safe_load(chunk)
        except yaml.YAMLError:
            continue
        if (isinstance(doc, dict) and doc.get("kind") == "Kustomization"
                and KS_API in str(doc.get("apiVersion", ""))):
            yield doc


def main():
    fail = 0
    checked = 0

    for f in sorted(ROOT.rglob("*.yaml")):
        if ".git" in f.parts:
            continue
        for doc in marked_docs(f):
            rel = f.relative_to(ROOT)
            spec = doc.get("spec") or {}
            subs = set(((spec.get("postBuild") or {}).get("substitute") or {}))
            targets = pd.paths_for(str(spec.get("path", "")))
            if not targets:
                print(f"FAIL {rel}: marked {MARKER} but its path "
                      f"{spec.get('path')!r} resolves to nothing in this checkout",
                      file=sys.stderr)
                fail = 1
                continue

            for target in targets:
                shown = f"./{target.relative_to(ROOT)}"
                text = pd.rendered(target, spec.get("components") or [])
                if not text or not text.strip():
                    print(f"UNVERIFIABLE {shown}: does not render, so the "
                          f"variables it reads could not be listed. Not a pass.",
                          file=sys.stderr)
                    fail = 1
                    continue
                checked += 1
                for name in sorted(set(READ.findall(text)) - subs):
                    print(f"FAIL {rel}: {shown} reads ${{{name}}}, which is not "
                          f"in postBuild.substitute. It renders its default on "
                          f"every cluster, whatever the cluster sets. Pass it "
                          f"through with the same default.", file=sys.stderr)
                    fail = 1

    if not fail:
        print(f"OK: {checked} path(s) read no variable their Kustomization "
              f"leaves out")
    return fail


if __name__ == "__main__":
    sys.exit(main())
