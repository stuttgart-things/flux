#!/usr/bin/env python3
"""Crossplane locks on the SOURCE STRING, and one bad node fails every package.

The lock is keyed by the OCI path a package was installed from. Two nodes for
one path, or a dependency naming a path nothing installed, and the resolver
gives up on the WHOLE graph:

  cannot initialize dependency graph from the packages in the lock:
  node ghcr.io/stuttgart-things/crossplane/volume-claim already exists

  cannot resolve package dependencies: missing dependencies:
  "xpkg.upbound.io/crossplane-contrib/provider-kubernetes" (>=v1.2.0)

Every Configuration, Function and Provider goes Healthy=False at once, INCLUDING
ones with no relation to the offender. Installed stays True, the pods keep
running, nothing restarts. Crossplane simply reconciles no claim at all, and no
Kustomization reports anything: this bundle applies cleanly either way.

Both messages above were real, on cicd-test2, hours apart. Neither was visible
in this repository, because the fact that decides them lives in the PACKAGES --
their own dependsOn, published inside the OCI artifact. So this check reads
them, with skopeo, the way verify-image-tags.py already reads the registry.

Two rules, one per failure:

  1. A Configuration that depends on another Configuration IN THE SAME FILE
     must set skipDependencyResolution. Those are applied in one pass, so it is
     a race: Crossplane materialises the dependency as a second Configuration
     named after the OCI path (stuttgart-things-crossplane-volume-claim), and
     whether that beats our own declaration varies per cluster. cicd-test1 came
     up clean and cicd-test2 did not, from identical manifests.

     Narrowed to Configuration -> Configuration on evidence, not taste. Every
     Configuration here also depends on providers and functions, and none of
     those produced a duplicate: they are installed by the `crossplane`
     Kustomization, which `crossplane-configs` dependsOn, so their nodes are in
     the lock before any Configuration resolves. Only the Configurations race
     each other.

  2. A package that does NOT skip resolution must have every dependency shipped
     under the EXACT source string it names. The two crossplane-contrib
     mirrors, xpkg.upbound.io and xpkg.crossplane.io, are different sources and
     therefore different nodes -- consolidating onto one registry looks like
     tidying and takes the cluster down.
"""
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Where the packages are declared, grouped by PROFILE -- the set of files that
# can land on ONE cluster together. Kept explicit: a glob would pick up tests/
# and examples/, which are not what a cluster installs.
#
# The grouping is not cosmetic. Rule 2 asks "does this bundle install the same
# package from a different registry", and the answer is only meaningful within
# one cluster. cicd-platform installs the crossplane/* family and machinery
# installs crossplane-configurations/*, and the two share package NAMES
# (harvester-vm, volume-claim, ansible-run, cloud-config). Compared globally,
# machinery's harvester-vm needing crossplane-configurations/volume-claim would
# be reported as a cross-registry node against cicd-platform's
# crossplane/volume-claim -- a finding about two clusters that never meet.
# Per profile it stays the real check it was written to be.
#
# The two profiles do NOT share install + functions, and that asymmetry is the
# whole point of the machinery one.
#
# cicd-platform installs three Providers and four Functions explicitly, at the
# xpkg.upbound.io spellings the crossplane/* family declares for them.
# crossplane-configurations declares the same packages against
# xpkg.crossplane.io -- provider-kubernetes (>=v1.2.0), provider-helm
# (>=v1.0.0), function-kcl (>=v0.12.0), function-patch-and-transform
# (>=v0.10.6) -- and Crossplane keys its lock on the source string, so a
# machinery cluster carrying the upbound spellings reports each of those as a
# missing dependency while the other spelling sits there installed. CI proved
# this on the first run of these profiles, on eight of the nine packages.
#
# A machinery cluster therefore installs NO Provider and NO Function
# explicitly: every one arrives through some Configuration's dependsOn, at the
# registry that Configuration names. stuttgart-things/argocd takes the same
# position for provider-kubernetes in cicd/crossplane/providers/values.yaml.
#
# components/install is shared and hardcodes the upbound provider list, so it
# is NOT usable by a machinery cluster as it stands -- see profiles/README.md.
PROFILES = {
    "cicd-platform": [
        "cicd/crossplane/components/install/release.yaml",
        "cicd/crossplane/components/functions/functions.yaml",
        "cicd/crossplane/components/configs/configs.yaml",
    ],
    "machinery": [
        "cicd/crossplane/profiles/machinery/configs.yaml",
        "cicd/crossplane/profiles/machinery-platform/configs.yaml",
    ],
}

REF = re.compile(
    r'(?:package:|-)\s*'
    r'(?P<src>(?:xpkg\.[^:$\s]+|ghcr\.io/[^:$\s]+))'
    r':(?:\$\{[A-Z0-9_]+:-(?P<sub>[^}]+)\}|(?P<plain>[^\s"\']+))'
)


def shipped(files):
    """{source: (version, skips_resolution, file)} for one profile."""
    out = {}
    for rel in files:
        f = ROOT / rel
        text = f.read_text()
        # skipDependencyResolution is per document, so split on the same
        # boundary the YAML does rather than guessing by proximity.
        for doc in text.split("\n---"):
            skip = "skipDependencyResolution: true" in doc
            for m in REF.finditer(doc):
                ver = m.group("sub") or m.group("plain")
                out[m.group("src")] = (ver, skip, rel)
    return out


def dependencies(src, ver, cache):
    """dependsOn of a published package, read out of its OCI artifact."""
    ref = f"{src}:{ver}"
    if ref in cache:
        return cache[ref]
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            ["skopeo", "copy", "--quiet", f"docker://{ref}", f"dir:{tmp}/p"],
            capture_output=True, text=True)
        if r.returncode != 0:
            cache[ref] = None
            return None
        deps = []
        for blob in sorted(Path(f"{tmp}/p").iterdir()):
            try:
                with tarfile.open(blob, "r:gz") as t:
                    member = next((m for m in t.getmembers()
                                   if m.name.endswith("package.yaml")), None)
                    if member is None:
                        continue
                    body = t.extractfile(member).read().decode()
            except (tarfile.TarError, OSError, UnicodeDecodeError):
                continue
            for doc in yaml.safe_load_all(body):
                if not isinstance(doc, dict):
                    continue
                if doc.get("kind") not in ("Configuration", "Provider", "Function"):
                    continue
                for d in (doc.get("spec") or {}).get("dependsOn") or []:
                    for kind in ("provider", "function", "configuration", "package"):
                        if kind in d:
                            deps.append((d[kind], d.get("version", "*"), kind))
            break
        cache[ref] = deps
        return deps


def main():
    # skopeo, because the xpkg registries answer a plain anonymous manifest
    # request with 401 and their auth challenge is not the ghcr shape that
    # verify-image-tags.py implements. Missing binary is UNVERIFIABLE, never a
    # failure: a check that turns red on a runner without a tool teaches people
    # to ignore it.
    if subprocess.run(["which", "skopeo"], capture_output=True).returncode != 0:
        print("note: skopeo not installed -- crossplane package dependencies "
              "not checked")
        return 0

    cache, fail = {}, 0
    for profile, files in PROFILES.items():
        fail |= check_profile(profile, files, cache)
    return fail


def check_profile(profile, files, cache):
    pkgs = shipped(files)
    if not pkgs:
        print(f"FAIL {profile}: no package references found -- did the files "
              f"move?", file=sys.stderr)
        return 1

    # Same package, different registry: harmless to name, fatal to install.
    # Scoped to this profile -- see the PROFILES comment.
    by_name = {}
    for src in pkgs:
        by_name.setdefault(src.rsplit("/", 1)[-1], []).append(src)

    fail, checked = 0, 0
    for src, (ver, skip, where) in sorted(pkgs.items()):
        deps = dependencies(src, ver, cache)
        if deps is None:
            print(f"FAIL {where}: cannot read {src}:{ver} from its registry",
                  file=sys.stderr)
            fail = 1
            continue
        checked += 1
        name = src.rsplit("/", 1)[-1]

        # Same file, and configuration-kind only: see rule 1 above.
        siblings = {s for s, (_, _, w) in pkgs.items() if w == where}
        overlap = [d for d, _, kind in deps
                   if kind == "configuration" and d in siblings and d != src]
        if overlap and not skip:
            print(f"FAIL {where}: {name} depends on {len(overlap)} package(s) "
                  f"this bundle also installs, and does not set "
                  f"skipDependencyResolution", file=sys.stderr)
            for d in overlap:
                print(f"       {d}", file=sys.stderr)
            print(f"     Crossplane will materialise each of them a SECOND "
                  f"time under the name it derives from the OCI path, and a "
                  f"duplicate node takes every package to Healthy=False. It is "
                  f"a race, so a cluster that came up clean proves nothing. "
                  f"Set skipDependencyResolution: true on {name} -- but only "
                  f"while this bundle keeps installing all of its "
                  f"dependencies.", file=sys.stderr)
            fail = 1

        if skip:
            continue
        for d, constraint, _ in deps:
            if d in pkgs:
                continue
            other = [s for s in by_name.get(d.rsplit("/", 1)[-1], []) if s != d]
            if other:
                print(f"FAIL {where}: {name} needs {d} ({constraint}), and "
                      f"this bundle installs that package from a DIFFERENT "
                      f"source: {', '.join(other)}", file=sys.stderr)
                print(f"     Crossplane keys its lock on the source string, so "
                      f"the two spellings are two packages to it. It reports "
                      f"the one it wants as a missing dependency while the "
                      f"other sits there installed. Move it back to the "
                      f"registry its consumers declare.", file=sys.stderr)
                fail = 1

    if not fail:
        print(f"OK {profile}: {checked} crossplane package(s), dependencies "
              f"read from the registry, no duplicate or cross-registry node")
    return fail


if __name__ == "__main__":
    sys.exit(main())
