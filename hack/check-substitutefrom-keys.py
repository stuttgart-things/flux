#!/usr/bin/env python3
"""A substituteFrom Secret's keys are declared, and the declaration is true.

Eight bundle components refuse to install without a Secret the cluster
supplies:

    postBuild:
      substituteFrom:
        # substituteFrom-keys: VELERO_S3_ACCESS_KEY, VELERO_S3_SECRET_KEY
        - kind: Secret
          name: ${VELERO_SECRET:-velero-s3-credentials}
          optional: false

`optional: false` guards the SOURCE, not the KEYS. Flux fails the Kustomization
when the Secret is absent, and substitutes an empty string for any key it does
not carry -- with no error at all. So the list of keys is the contract a cluster
has to meet, and the only thing a cluster-side preflight can check against
(#331). #334 wrote those lists down. This keeps them true.

THE REQUIRED KEYS ARE DERIVED, not trusted. They are every variable the
component's build references with no default anywhere in it and no entry in its
own `substitute:` map. A variable that has neither can only come from the
Secret; if the Secret lacks it, the value renders empty.

The build is spec.path PLUS spec.components, rendered the way Flux composes it
(check-passthrough-defaults.rendered). Rendering the path alone gets it wrong in
both directions, and did when the lists were first derived: argo-cd picked up
ISSUER_NAME/ISSUER_KIND from a Certificate its no-ingress-cert component
removes, and dapr-workflows came out as needing nothing, because all three of
its keys arrive through a component.

BOTH DIRECTIONS FAIL:
  undeclared   the build needs a key the declaration does not name -- a cluster
               following the comment ships a Secret without it, and that value
               renders empty
  stale        the declaration names a key nothing reads any more -- the next
               reader provisions a credential for nothing, or trusts the list
               less. Dropping it is the fix.

The declaration is the `# substituteFrom-keys:` comment in the substituteFrom
block, comma-separated; it may wrap onto the following comment lines.
"""
import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KS_API = "kustomize.toolkit.fluxcd.io"
MARKER = "substituteFrom-keys:"

_spec = importlib.util.spec_from_file_location(
    "passthrough_defaults", ROOT / "hack" / "check-passthrough-defaults.py")
pd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pd)

# Not preceded by a second `$`: `$${VAR}` is Flux's escape and renders as the
# literal `${VAR}` -- Argo CD plugin variables and Backstage's own config
# placeholders are written that way, and are not Flux's to fill.
BARE = re.compile(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
DEFAULTED = re.compile(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*):-")
DISABLED = "kustomize.toolkit.fluxcd.io/substitute"
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def declared(lines, start):
    """The key names after MARKER on line `start`, following wrapped lines.

    A continuation is a comment line directly below whose content is only
    names and commas. A blank `#`, prose, or a non-comment line ends it.
    """
    names = []
    text = lines[start].split(MARKER, 1)[1]
    i = start
    while True:
        parts = [p.strip() for p in text.split(",")]
        if not all(NAME.match(p) for p in parts if p):
            break
        names += [p for p in parts if p]
        if not text.rstrip().endswith(","):
            break
        i += 1
        if i >= len(lines) or not lines[i].strip().startswith("#"):
            break
        text = lines[i].strip().lstrip("#")
    return names


def declarations(f: Path):
    """{Kustomization name: [keys]} for every MARKER in the file.

    Attributed to the nearest `name:` of a Flux Kustomization above it -- the
    marker sits inside that document's postBuild block.
    """
    lines = f.read_text().splitlines()
    out, current = {}, None
    for i, line in enumerate(lines):
        if line.startswith("---"):
            current = None
        m = re.match(r"^  name:\s*(\S+)", line)
        if m and current is None:
            current = m.group(1)
        if MARKER in line and line.lstrip().startswith("#"):
            out.setdefault(current, []).extend(declared(lines, i))
    return out


def substituted(text):
    """The rendered objects Flux actually substitutes into, as text.

    Flux skips an object annotated `kustomize.toolkit.fluxcd.io/substitute:
    disabled` entirely, so its ${...} are not variables at all.
    """
    out = []
    for doc in yaml.safe_load_all(text):
        if not isinstance(doc, dict):
            continue
        ann = ((doc.get("metadata") or {}).get("annotations") or {})
        if str(ann.get(DISABLED, "")).lower() == "disabled":
            continue
        # width: a folded long line could split a ${...} in two.
        out.append(yaml.safe_dump(doc, width=1 << 20))
    return "\n".join(out)


def required(text, own_substitute):
    """Variables the build reads with no default anywhere and no own value."""
    text = substituted(text)
    bare = set(BARE.findall(text))
    defaulted = set(DEFAULTED.findall(text))
    return sorted(bare - defaulted - set(own_substitute))


def main():
    fail = 0
    checked = []
    for f in sorted(ROOT.rglob("*.yaml")):
        if ".git" in f.parts:
            continue
        try:
            docs = list(yaml.safe_load_all(f.read_text()))
        except (yaml.YAMLError, UnicodeDecodeError):
            continue
        decl = None
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Kustomization":
                continue
            if KS_API not in str(doc.get("apiVersion", "")):
                continue
            spec = doc.get("spec") or {}
            post = spec.get("postBuild") or {}
            strict = [s for s in post.get("substituteFrom") or []
                      if s.get("optional") is False]
            if not strict:
                continue
            name = (doc.get("metadata") or {}).get("name", "?")
            rel = f.relative_to(ROOT)
            if decl is None:
                decl = declarations(f)
            have = sorted(set(decl.get(name, [])))
            if not have:
                print(f"FAIL {rel}: {name} reads a Secret with optional: false "
                      f"but declares no `# {MARKER}`. Say which keys that "
                      f"Secret must carry -- a missing one renders empty, "
                      f"silently.", file=sys.stderr)
                fail = 1
                continue

            targets = pd.paths_for(str(spec.get("path", "")))
            if not targets:
                print(f"note: {rel}: {name}: path not in this checkout, "
                      f"declaration not verified")
                continue
            for target in targets:
                shown = f"./{target.relative_to(ROOT)}"
                text = pd.rendered(target, spec.get("components") or [])
                if not text or not text.strip():
                    print(f"FAIL {rel}: {name}: {shown} does not render, so its "
                          f"keys cannot be derived. Not a pass.", file=sys.stderr)
                    fail = 1
                    continue
                need = required(text, post.get("substitute") or {})
                missing = sorted(set(need) - set(have))
                stale = sorted(set(have) - set(need))
                if missing:
                    print(f"FAIL {rel}: {name} needs {', '.join(missing)} from "
                          f"its Secret (read in {shown} with no default and no "
                          f"substitute entry), but `# {MARKER}` does not name "
                          f"it. A Secret built from the declaration leaves it "
                          f"empty.", file=sys.stderr)
                    fail = 1
                if stale:
                    print(f"FAIL {rel}: {name} declares {', '.join(stale)}, "
                          f"which nothing in {shown} reads without a default "
                          f"any more. Drop it from `# {MARKER}`.",
                          file=sys.stderr)
                    fail = 1
                if not missing and not stale:
                    checked.append((name, need))

    if not fail:
        print(f"OK: {len(checked)} substituteFrom declaration(s) match what "
              f"their build reads")
        for name, need in checked:
            print(f"  {name}: {', '.join(need)}")
    return fail


if __name__ == "__main__":
    sys.exit(main())
