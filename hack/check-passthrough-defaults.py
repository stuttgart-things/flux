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
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KS_API = "kustomize.toolkit.fluxcd.io"

# "${NAME:-value}" and nothing else -- the pass-through shape. A value that
# merely CONTAINS the variable is a composed string, not a copied default.
SELF = re.compile(r'^\$\{([A-Z0-9_]+):-(.*)\}$', re.S)
ANY = re.compile(r'\$\{([A-Z0-9_]+):-([^}]*)\}')

_cache = {}


SUBST_PATH = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def rendered(path: Path, components=()):
    """What Flux actually applies for this Kustomization.

    spec.components are applied BY FLUX on top of the built path, so
    `kustomize build <path>` alone does not see them -- and for some components
    that is the whole content. `dapr`'s spec.path is ./apps/dapr/root, whose
    kustomization.yaml is `resources: []`: rendering the path gave zero lines,
    and this check compared against nothing and reported clean. DAPR_VERSION had
    drifted 1.17.4 against 1.18.3 for a day, on every cluster that selected it.

    Rendered here the way Flux composes it: a kustomization that takes the path
    as a resource and the components on top. Paths must be RELATIVE -- kustomize
    refuses an absolute root -- so the scratch directory lives inside the repo.
    """
    key = (str(path), tuple(str(c) for c in components))
    if key in _cache:
        return _cache[key]

    if not components:
        out = subprocess.run(["kustomize", "build", str(path)],
                             capture_output=True, text=True)
        _cache[key] = out.stdout if out.returncode == 0 else None
        return _cache[key]

    def _remember(k, v):
        _cache[k] = v
        return v

    scratch = Path(tempfile.mkdtemp(prefix=".render-", dir=ROOT))
    try:
        def rel(p):
            return os.path.relpath(p, scratch)
        # A component path can itself carry a substitution -- openbao selects
        # its seal mode with ./components/seal-${OPENBAO_SEAL_MODE:-transit},
        # one component covering three modes. Resolve to the default, the same
        # reading this check applies to values. Left literal, kustomize fails on
        # a directory that does not exist and the whole path went unchecked --
        # losing the comparisons it USED to make before components were rendered
        # at all.
        comps = []
        for c in components:
            c = SUBST_PATH.sub(lambda m: m.group(2) or "", str(c))
            d = (path / c).resolve()
            if not d.is_dir():
                return _remember(key, None)
            comps.append(rel(d))
        kust = {"resources": [rel(path)], "components": comps}
        (scratch / "kustomization.yaml").write_text(yaml.safe_dump(kust))
        out = subprocess.run(["kustomize", "build", str(scratch)],
                             capture_output=True, text=True)
        _cache[key] = out.stdout if out.returncode == 0 else None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return _cache[key]



def paths_for(path):
    """Every directory in this checkout a spec.path can resolve to.

    Usually one. But spec.path is itself substituted by the PARENT, and the
    crossplane component uses that to select a cluster shape:

        path: ./cicd/crossplane/profiles/${CROSSPLANE_PROFILE:-cicd-platform}/configs

    Resolving only the default would leave every pin of every OTHER profile
    unchecked -- and those pins are second copies that WIN over the base, which
    is the failure this whole check exists for. So a variable standing for one
    path SEGMENT becomes a glob, and each match is compared on its own: a
    variable a given profile does not use contributes no comparison there
    (`not there`), and a profile whose copy has drifted fails on its own path.

    A variable whose default carries a `/` is NOT a segment -- it stands for the
    whole path, as ARGOCD_PLATFORM_PATH does -- and globbing it would match every
    directory in the repo. Those resolve to their default and nothing else.
    """
    p = str(path).lstrip("./")
    if "${" not in p:
        d = ROOT / p
        return [d] if d.is_dir() else []
    if any("/" in (m.group(2) or "") for m in SUBST_PATH.finditer(p)):
        d = ROOT / SUBST_PATH.sub(lambda m: m.group(2) or "", p).lstrip("./")
        return [d] if d.is_dir() else []
    return sorted(d for d in ROOT.glob(SUBST_PATH.sub("*", p)) if d.is_dir())


def defaults_for(text, name):
    return {m.group(2) for m in ANY.finditer(text) if m.group(1) == name}


def norm(v):
    v = str(v).strip()
    if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def overridden(file: Path, name):
    """A `# passthrough-override:` comment in the comment block above `name`.

    The WHOLE contiguous block, not a fixed number of lines above it. A reason
    worth writing down is usually longer than the marker, and a window that cuts
    it off rejects the declaration while the explanation sits right there --
    which reads as the check being broken rather than as the comment being in
    the wrong place.
    """
    lines = file.read_text().splitlines()
    for i, line in enumerate(lines):
        if re.match(rf'\s*{name}:\s', line):
            for prev in reversed(lines[:i]):
                if not prev.strip().startswith("#"):
                    break
                if "passthrough-override:" in prev:
                    return True
    return False


def main():
    fail = 0
    checked = 0
    skipped, empty = set(), set()

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
            targets = paths_for(str(path))
            if not targets:
                skipped.add(str(path))
                continue

            for target in targets:
                shown = f"./{target.relative_to(ROOT)}"
                text = rendered(target, spec.get("components") or [])
                if text is None:
                    skipped.add(shown)
                    continue
                # An empty render is not agreement. Before this, a path that
                # built to nothing produced no comparison and no finding --
                # indistinguishable from a clean one.
                if not text.strip():
                    empty.add(shown)
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
                          f"{shown} defaults it to "
                          f"{', '.join(sorted(repr(t) for t in there))}",
                          file=sys.stderr)
                    print(f"     The copy above WINS, so the value in {shown} "
                          f"is never used and that component installs {here!r}. "
                          f"Bump both, or mark this line with "
                          f"`# passthrough-override: <reason>`.", file=sys.stderr)
                    fail = 1

    if skipped:
        print(f"note: {len(skipped)} path(s) not in this checkout, not checked")
    if empty:
        for p in sorted(empty):
            print(f"UNVERIFIABLE {p}: renders to nothing, so no default there "
                  f"could be compared. Not a pass.", file=sys.stderr)
        fail = 1
    if not fail:
        print(f"OK: {checked} pass-through default(s) match the path they thread into")
    return fail


if __name__ == "__main__":
    sys.exit(main())
