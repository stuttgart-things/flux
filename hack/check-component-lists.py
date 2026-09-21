#!/usr/bin/env python3
"""Every `spec.components` list on a Flux Kustomization has to build.

check-bundle-components.sh proves a bundle component renders a Flux
Kustomization CR. It cannot prove that what the CR points AT builds, and since
the profiles collapsed into

    path: ./apps/homerun2/root
    components:
      - ../components/omni-pitcher
      - ../components/omni-pitcher/${HOMERUN2_SECRETS:-eso}

that is where the wiring now lives. To kustomize those entries are opaque
strings in a YAML document; only Flux resolves them, on a cluster. A typo or a
missing variant directory would therefore be a deploy-time failure with no
pull-request-time tell -- the exact failure the profiles this replaced existed
to avoid.

Every list is built with each `${VAR:-default}` at its default. A list whose
variable is a SWITCH -- a value the consumer is meant to change, of which the
credential mode is the reason this check exists -- declares the values it can
take in a comment above it, and each is built too:

    components:
      # component-switch: HOMERUN2_SECRETS = eso sops
      - ../components/omni-pitcher/${HOMERUN2_SECRETS:-eso}

so a component that grew an `eso/` and never got a `sops/` fails here rather
than on the one cluster that selects sops. Without the comment a variable is
built at its default only: that still catches a path that exists nowhere, which
is the common typo, and it is the coverage every list had before (none).
"""
import os
import re
import subprocess
import sys
import tempfile

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)(?::[-=]([^}]*))?\}")
SWITCH = re.compile(r"^\s*#\s*component-switch:\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$", re.M)


def documents():
    """Flux Kustomizations that select components, with their file's switches."""
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(root, name)
            text = open(path, encoding="utf-8", errors="replace").read()
            if "kustomize.toolkit" not in text or "components:" not in text:
                continue
            try:
                docs = list(yaml.safe_load_all(text))
            except yaml.YAMLError:
                continue  # not our business -- other checks read these too
            switches = {v: values.split() for v, values in SWITCH.findall(text)}
            for doc in docs:
                if not isinstance(doc, dict) or doc.get("kind") != "Kustomization":
                    continue
                if not str(doc.get("apiVersion", "")).startswith("kustomize.toolkit"):
                    continue
                spec = doc.get("spec") or {}
                comps, target = spec.get("components"), spec.get("path")
                if comps and isinstance(target, str) and target.startswith("./"):
                    yield path, doc["metadata"]["name"], target, comps, switches


def is_component(directory):
    """True when the directory's kustomization is a `kind: Component`."""
    for name in ("kustomization.yaml", "kustomization.yml", "Kustomization"):
        path = os.path.join(directory, name)
        if os.path.exists(path):
            # Parsed, not grepped: root/kustomization.yaml explains in a COMMENT
            # that a `kind: Component` directory cannot be a path target.
            doc = yaml.safe_load(open(path, encoding="utf-8")) or {}
            return doc.get("kind") == "Component"
    return False


def build(target, entries, values):
    """Render `target` with `entries` selected, placeholders resolved by `values`."""
    def resolve(m):
        return values.get(m.group(1), m.group(2) or "")

    resolved = [PLACEHOLDER.sub(resolve, e) for e in entries]
    with tempfile.TemporaryDirectory(dir=REPO) as tmp:
        rel = os.path.relpath(os.path.join(REPO, target.lstrip("./")), tmp)
        selected = [os.path.normpath(os.path.join(rel, e)) for e in resolved]
        # Flux appends spec.components to the kustomization AT spec.path, so
        # how the target is pulled in depends on what that kustomization is.
        # cert-manager-vault-issuer points at a `kind: Component` directory and
        # selects a nested one; listed under `resources` that is an error.
        lines = ["apiVersion: kustomize.config.k8s.io/v1beta1",
                 "kind: Kustomization"]
        if is_component(os.path.join(REPO, target.lstrip("./"))):
            lines += ["components:", f"  - {rel}"]
        else:
            lines += ["resources:", f"  - {rel}", "components:"]
        lines += [f"  - {s}" for s in selected]
        open(os.path.join(tmp, "kustomization.yaml"), "w").write("\n".join(lines) + "\n")
        r = subprocess.run(["kustomize", "build", tmp], capture_output=True, text=True)
    return r.returncode == 0, r.stderr.strip(), resolved


def main():
    fail = builds = 0
    for path, name, target, entries, switches in documents():
        rel = os.path.relpath(path, REPO)
        if not os.path.isdir(os.path.join(REPO, target.lstrip("./"))):
            continue  # points at a path this repository does not carry

        used = {v for e in entries for v, _ in PLACEHOLDER.findall(e)}
        # The defaults, then each declared switch value in turn -- one switch at
        # a time, from the default baseline. The full product of six independent
        # switches (tabletennis) is 64 builds and proves nothing the singles do.
        cases = [({}, "defaults")]
        for var in sorted(used & switches.keys()):
            cases += [({var: value}, f"{var}={value}") for value in switches[var]]

        for values, label in cases:
            ok, err, resolved = build(target, entries, values)
            builds += 1
            if ok:
                print(f"OK   {name} ({label}) -- {len(resolved)} components")
            else:
                print(f"FAIL {rel}: {name} ({label}) does not build\n{err}",
                      file=sys.stderr)
                fail = 1

    print(f"\n{builds} builds")
    return fail


if __name__ == "__main__":
    sys.exit(main())
