#!/usr/bin/env python3
"""No postBuild.substitute value may resolve to a non-string.

`postBuild.substitute` is map[string]string. A value that YAML parses as a
bool, an int or a float is rejected by the API server's typed patch with

  .spec.postBuild.substitute.X: expected string, got &value.valueUnstructured{...}

and the failure is NOT contained to the offending child: it fails the parent
Kustomization's apply, taking every sibling component down with it.

Quoting the value in the source does not help. kustomize parses and re-emits
this bundle, and it drops "x", 'x' and !!str alike whenever the bare form
round-trips to the same string -- which `${VAR:-true}` does. So the quotes are
gone by the time envsubst runs, and `true` arrives as a bool.

The value is checked as it will actually look on a cluster: the envsubst
default is extracted from ${NAME:-default} and parsed. Witnessed with
EXTERNAL_SECRETS_INSTALL_CRDS.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "infra/platform/components"
# ${NAME:-default} / ${NAME} -- the whole value must be one reference for the
# default to be what lands. A value mixing text and references is a string.
REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*))?\}$")


def resolved(value):
    """What this substitute value looks like once envsubst has run unset."""
    if not isinstance(value, str):
        return value  # already non-string in the source
    m = REF.match(value.strip())
    if not m:
        return value
    default = m.group(2)
    if default is None:
        return ""
    try:
        return yaml.safe_load(default)
    except yaml.YAMLError:
        return default


def main():
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        tmp = Path(tmp)
        lines = [
            "apiVersion: kustomize.config.k8s.io/v1beta1",
            "kind: Kustomization",
            "resources:",
            f"  - ../{ROOT.name and 'infra/platform/root'}",
            "components:",
        ]
        lines += [f"  - ../infra/platform/components/{d.name}"
                  for d in sorted(COMPONENTS.iterdir()) if d.is_dir()]
        (tmp / "kustomization.yaml").write_text("\n".join(lines) + "\n")
        out = subprocess.run(["kustomize", "build", str(tmp)],
                             capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stderr, file=sys.stderr)
        return 1

    bad = []
    checked = 0
    for doc in yaml.safe_load_all(out.stdout):
        if not doc or doc.get("kind") != "Kustomization":
            continue
        name = doc.get("metadata", {}).get("name", "?")
        sub = (doc.get("spec", {}).get("postBuild") or {}).get("substitute") or {}
        for key, value in sub.items():
            checked += 1
            r = resolved(value)
            if not isinstance(r, str):
                bad.append((name, key, value, type(r).__name__, r))

    for name, key, value, kind, r in bad:
        print(f"FAIL {name}: {key}: {value}", file=sys.stderr)
        print(f"     resolves to {kind} {r!r}; postBuild.substitute takes "
              f"strings only, and quoting it here will not survive kustomize.",
              file=sys.stderr)
    if bad:
        return 1
    print(f"OK: {checked} substitute values, all strings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
