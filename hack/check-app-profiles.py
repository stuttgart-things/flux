#!/usr/bin/env python3
"""Every AppProfile tells the truth about its component.

An AppProfile (`<bundle>/components/<app>/profile.yaml`) describes both halves
of one catalog app for a cluster-side renderer (blueprints `render-cluster-apps`,
stuttgart-things/blueprints#206):

    kind: AppProfile
    metadata: { name: keycloak }
    spec:
      bundle: apps-platform
      component: ../components/keycloak
      vars:                       # what the bundle's postBuild.substitute may set
        KEYCLOAK_STORAGE_CLASS: { required: true }
        KEYCLOAK_HOSTNAME: {}
      secrets:                    # the Secret its substituteFrom reads
        - name: keycloak-secrets
          data:
            ADMIN_USER: admin
            ADMIN_PASSWORD: { generate: { type: alnum, length: 32 } }

The renderer trusts the profile: it refuses a var the profile does not declare
and generates exactly the keys the profile lists. So a profile that drifts from
its ks-*.yaml fails quietly on the cluster -- a key renders empty (#331), or a
REQUIRED placeholder like `set-INFRA_DOMAIN.invalid` ships. This compares them.

THE CONTRACT IS DERIVED FROM THE COMPONENT, in both directions:
  vars       exactly the ${VAR} the component's Kustomization reads in its
             YAML values (a ${VAR} in a comment substitutes nothing), minus
             the source variable (APPS_SOURCE / FLUX_SOURCE: the renderer sets it)
             and the Secret-name variable (the renderer names the Secret).
             A var whose default is a `set-...` placeholder is required: true.
  secrets    one entry per substituteFrom Secret with optional: false, named
             like its default (`${KEYCLOAK_SECRET:-keycloak-secrets}`), with
             exactly the keys of its `# substituteFrom-keys:` declaration plus
             those of `# substituteFrom-optional-keys:` (read with a default,
             still meant to come from the Secret) -- both of which
             check-substitutefrom-keys.py already keeps true.
  placement  metadata.name is the directory, spec.bundle its bundle,
             spec.component `../components/<directory>`.

The value SHAPES (generate / ref / literal) are not checked here; the KCL
AppProfile schema does that with `kcl vet`.
"""
import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KS_API = "kustomize.toolkit.fluxcd.io"
SOURCE_VARS = {"APPS_SOURCE", "FLUX_SOURCE"}
BUNDLES = {"apps": "apps-platform", "infra": "infra-platform", "cicd": "cicd-platform"}

_spec = importlib.util.spec_from_file_location(
    "substitutefrom_keys", ROOT / "hack" / "check-substitutefrom-keys.py")
sk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sk)

# ${VAR} or ${VAR:-default}, not the $${VAR} escape. Group 2 is the default.
VAR = re.compile(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def scalars(node):
    """Every string key and value in a parsed YAML node, recursively.

    Variables are read from these, not from the file text: a `${VAR}` in a
    YAML comment (documentation like `KEY: "${VAR}"`) is not substituted into
    anything, so it is not a var a cluster could set.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            yield from scalars(k)
            yield from scalars(v)
    elif isinstance(node, list):
        for v in node:
            yield from scalars(v)
    elif isinstance(node, str):
        yield node


def component_contract(ks_files):
    """(vars {name: required}, secrets {name: [keys]}, Secret-name vars)."""
    variables, secrets, name_vars = {}, {}, set()
    for f in ks_files:
        text = f.read_text()
        decl = sk.declarations(f)
        docs = list(yaml.safe_load_all(text))
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Kustomization":
                continue
            if KS_API not in str(doc.get("apiVersion", "")):
                continue
            name = (doc.get("metadata") or {}).get("name")
            post = (doc.get("spec") or {}).get("postBuild") or {}
            for src in post.get("substituteFrom") or []:
                if src.get("kind") != "Secret" or src.get("optional") is not False:
                    continue
                m = VAR.fullmatch(str(src.get("name", "")))
                secret = m.group(2) if m and m.group(2) else str(src.get("name"))
                optional = sk.declarations(f, sk.OPTIONAL_MARKER).get(name, [])
                secrets[secret] = sorted(set(decl.get(name, [])) | set(optional))
                if m:
                    name_vars.add(m.group(1))
        found = [m for doc in docs for v in scalars(doc) for m in VAR.findall(v)]
        for var, default in found:
            if var in SOURCE_VARS or var in name_vars:
                continue
            required = default.startswith("set-")
            variables[var] = variables.get(var, False) or required
    return variables, secrets, name_vars


def check(profile_file):
    """Error strings for one profile.yaml."""
    comp_dir = profile_file.parent
    rel = profile_file.relative_to(ROOT)
    errs = []
    try:
        docs = [d for d in yaml.safe_load_all(profile_file.read_text()) if d]
    except yaml.YAMLError as e:
        return [f"{rel}: not YAML: {e}"]
    if len(docs) != 1 or docs[0].get("kind") != "AppProfile":
        return [f"{rel}: must hold exactly one kind: AppProfile document"]
    doc = docs[0]
    spec = doc.get("spec") or {}

    app = comp_dir.name
    layer = comp_dir.relative_to(ROOT).parts[0]
    want = {"metadata.name": ((doc.get("metadata") or {}).get("name"), app),
            "spec.bundle": (spec.get("bundle"), BUNDLES.get(layer)),
            "spec.component": (spec.get("component"), f"../components/{app}")}
    for field, (have, should) in want.items():
        if have != should:
            errs.append(f"{rel}: {field} is {have!r}, want {should!r}")

    ks_files = sorted(comp_dir.glob("ks-*.yaml"))
    if not ks_files:
        return errs + [f"{rel}: no ks-*.yaml next to it to compare against"]
    need_vars, need_secrets, name_vars = component_contract(ks_files)

    have_vars = spec.get("vars") or {}
    for var in sorted(set(have_vars) - set(need_vars)):
        why = (" -- the renderer names the Secret" if var in name_vars
               else " -- the renderer sets the source" if var in SOURCE_VARS
               else "")
        errs.append(f"{rel}: declares var {var}, which the component does not read{why}")
    for var in sorted(set(need_vars) - set(have_vars)):
        errs.append(f"{rel}: the component reads ${{{var}}}, but the profile does not "
                    f"declare it -- a cluster could not set it")
    for var in sorted(need_vars):
        if need_vars[var] and not (have_vars.get(var) or {}).get("required"):
            errs.append(f"{rel}: {var} defaults to a set-... placeholder in the "
                        f"component, so it must be required: true")

    have_secrets = {}
    for s in spec.get("secrets") or []:
        have_secrets[s.get("name")] = sorted((s.get("data") or {}).keys())
    for name in sorted(set(have_secrets) - set(need_secrets)):
        errs.append(f"{rel}: secret {name} is not read by any substituteFrom "
                    f"with optional: false in the component")
    for name in sorted(set(need_secrets) - set(have_secrets)):
        errs.append(f"{rel}: the component reads Secret {name} "
                    f"({', '.join(need_secrets[name])}), the profile does not provide it")
    for name in sorted(set(need_secrets) & set(have_secrets)):
        missing = sorted(set(need_secrets[name]) - set(have_secrets[name]))
        extra = sorted(set(have_secrets[name]) - set(need_secrets[name]))
        if missing:
            errs.append(f"{rel}: secret {name} lacks {', '.join(missing)} -- "
                        f"`# substituteFrom-keys:` (or -optional-keys:) names it, "
                        f"it would render empty or keep its default")
        if extra:
            errs.append(f"{rel}: secret {name} has {', '.join(extra)}, which "
                        f"neither `# substituteFrom-keys:` nor -optional-keys: "
                        f"names -- nothing reads it")
    return errs


def main():
    profiles = sorted(ROOT.glob("*/platform/components/*/profile.yaml"))
    fail = 0
    for p in profiles:
        for e in check(p):
            print(f"FAIL {e}", file=sys.stderr)
            fail = 1
    if not fail:
        print(f"OK: {len(profiles)} AppProfile(s) match their component")
        for p in profiles:
            print(f"  {p.parent.relative_to(ROOT)}")
    return fail


if __name__ == "__main__":
    sys.exit(main())
