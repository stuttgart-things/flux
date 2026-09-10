#!/usr/bin/env python3
"""Every HelmRelease's values must satisfy its chart's own schema.

The class of defect this exists for: a renovate bump moves a chart across a
major, the chart changes the SHAPE of a values field, and the base keeps
writing the old shape. Nothing in this repo notices. `kustomize build` is
happy -- the YAML is well formed either way. Every other check here reads
manifests, and a values/schema mismatch is not visible in a manifest.

It surfaces at `helm install`, which no CI runs, so it reaches a cluster:

  values don't meet the specifications of the schema(s) in the following
  chart(s): velero:
  - at '/configuration/extraEnvVars': got object, want array

velero's `configuration.extraEnvVars` went map -> list of name/value in chart
10.0.0. Renovate moved the version, the values did not follow, and the base
was uninstallable for weeks in TWO catalogs (stuttgart-things/flux#396,
stuttgart-things/argocd#380) without a single red build. Nobody noticed
because no cluster had selected the component -- an unused component carries
a defect indefinitely, which is exactly why this has to run without one.

What it does: renders each bundle to find the child Kustomizations, resolves
their path and postBuild.substitute the way Flux would, builds that path,
substitutes, and runs `helm template` against the real chart.

What it cannot do: reach a private registry. Those are reported as SKIPPED
with the reason and counted in the summary -- a skip is a hole, not a pass,
and it should be visible rather than quiet.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from bundle_alternatives import selections

ROOT = Path(__file__).resolve().parent.parent
BUNDLES = sorted(
    str(d.relative_to(ROOT))
    for d in ROOT.glob("*/platform")
    if (d / "root").is_dir() and (d / "components").is_dir()
)
# ${NAME:-default} or ${NAME}. Matched anywhere in the text, not anchored:
# unlike check-substitute-strings.py this resolves values EMBEDDED in longer
# strings too, because helm sees the whole rendered string.
REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
# What a bare ${VAR} with no default and no consumer value becomes. Non-empty
# on purpose: charts commonly require a bucket/host/name to be set, and an
# empty one fails on "required", which is a different complaint than the one
# this check is about.
UNSET = "ci-placeholder"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def build(path):
    out = run(["kustomize", "build", str(path)])
    if out.returncode != 0:
        return None, out.stderr.strip()
    return out.stdout, None


def substitute(text, values):
    """Resolve ${VAR} the way Flux's postBuild would, twice.

    Twice because a bundle threads VELERO_VERSION: "${VELERO_VERSION:-12.1.0}"
    -- one pass leaves the inner reference behind.
    """
    for _ in range(2):
        text = REF.sub(
            lambda m: values.get(m.group(1)) or (m.group(2) if m.group(2) is not None else UNSET),
            text,
        )
    return text


def children():
    """(path, substitute) for every child Kustomization the bundles ship."""
    seen = {}
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        tmp = Path(tmp)
        builds = []
        for bundle in BUNDLES:
            # One build per selection: an alternative component cannot be
            # built beside the one it replaces, and its children count too.
            for label, names in selections(ROOT / bundle / "components"):
                lines = ["apiVersion: kustomize.config.k8s.io/v1beta1",
                         "kind: Kustomization", "resources:", f"  - ../{bundle}/root",
                         "components:"]
                lines += [f"  - ../{bundle}/components/{n}" for n in names]
                (tmp / "kustomization.yaml").write_text("\n".join(lines) + "\n")
                docs, err = build(tmp)
                if docs is None:
                    print(f"{bundle} ({label}):", file=sys.stderr)
                    print(err, file=sys.stderr)
                    sys.exit(1)
                builds.append(docs)
        for docs in builds:
            for doc in yaml.safe_load_all(docs):
                if not doc or doc.get("kind") != "Kustomization":
                    continue
                spec = doc.get("spec", {})
                path = spec.get("path")
                if not path:
                    continue
                sub = (spec.get("postBuild") or {}).get("substitute") or {}
                # The bundle's own value is itself a ${VAR:-default}; take the
                # default, which is what a consumer that sets nothing gets.
                resolved = {k: substitute(str(v), {}) for k, v in sub.items()}
                # The PATH takes substitution too -- crossplane's child renders
                # ./cicd/crossplane/profiles/${CROSSPLANE_PROFILE:-...}/install,
                # and without this every one of them reads as a missing path
                # and is skipped, which looks like coverage and is not.
                path = substitute(path, resolved)
                seen.setdefault((path, tuple(sorted(resolved.items()))),
                                doc["metadata"]["name"])
    return seen


def charts(docs):
    """HelmReleases in a rendered path, paired with their repository."""
    repos, releases = {}, []
    for doc in yaml.safe_load_all(docs):
        if not doc:
            continue
        kind, meta = doc.get("kind"), doc.get("metadata", {})
        if kind == "HelmRepository":
            repos[meta.get("name")] = doc.get("spec", {})
        elif kind == "HelmRelease":
            releases.append(doc)
    return repos, releases


def template(release, repos, workdir):
    """Run helm template. Returns (status, detail)."""
    spec = release.get("spec", {})
    chart = (spec.get("chart") or {}).get("spec") or {}
    name, version = chart.get("chart"), str(chart.get("version", ""))
    ref = (chart.get("sourceRef") or {}).get("name")
    if not name:
        return "skip", "chartRef, not an inline chart spec"
    repo = repos.get(ref)
    if repo is None:
        return "skip", f"HelmRepository {ref!r} is not in this path"
    url = repo.get("url", "")
    values = spec.get("values") or {}

    vf = workdir / "values.yaml"
    vf.write_text(yaml.safe_dump(values))
    if repo.get("type") == "oci":
        target, args = f"{url.rstrip('/')}/{name}", []
    else:
        target, args = name, ["--repo", url]
    cmd = ["helm", "template", "release", target, *args,
           "--version", version, "-f", str(vf), "--namespace", "default"]
    out = run(cmd, env={**os.environ, "HELM_EXPERIMENTAL_OCI": "1"})
    if out.returncode == 0:
        return "ok", ""
    err = out.stderr.strip()
    if "schema" in err or "want array" in err or "want object" in err:
        return "fail", err
    # Anything else is the check's own reach failing, not the values: a
    # private registry, a withdrawn version, no network. Loud, but not red.
    return "skip", err.splitlines()[-1] if err else "helm template failed"


def strays():
    """Paths holding a HelmRelease that no bundle component renders.

    Half the HelmReleases in this repo are not reachable from a bundle -- an
    app wired directly by a cluster, or a kustomize Component selected inside
    another path. Checking only the bundle would report full coverage over
    58% of the charts, which is the failure mode this whole check exists to
    avoid. They are rendered with no consumer values, so only the inline
    ${VAR:-default} fallbacks apply.
    """
    covered = {p for p, _ in children()}
    found = {}
    for f in ROOT.rglob("*.yaml"):
        rel = f.relative_to(ROOT)
        if not rel.parts or rel.parts[0] not in ("infra", "apps", "cicd"):
            continue
        try:
            if "kind: HelmRelease" not in f.read_text():
                continue
        except OSError:
            continue
        d = f.parent
        if f"./{d.relative_to(ROOT)}" in covered:
            continue
        kfile = d / "kustomization.yaml"
        if not kfile.is_file():
            continue
        try:
            kind = (yaml.safe_load(kfile.read_text()) or {}).get("kind")
        except yaml.YAMLError:
            continue
        # A Component cannot be built on its own -- it is not a root. Build the
        # path that OWNS it with the component selected, which is how a
        # consumer reaches it anyway. Prefer a sibling root/ when there is one:
        # apps/dapr/kustomization.yaml selects every component itself, so
        # adding one on top duplicates the Namespace its requirements.yaml
        # brings. apps/dapr/root exists for exactly this and is what a
        # consumer points spec.path at.
        if kind == "Component":
            base = d.parent.parent
            found[d] = ("component", base / "root" if (base / "root").is_dir() else base)
        else:
            found[d] = ("root", None)
    return found


def build_stray(path, mode, parent, tmp):
    if mode == "root":
        return build(path)
    if not (parent / "kustomization.yaml").is_file():
        return None, f"component at {path.relative_to(ROOT)} has no buildable parent"
    (tmp / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\n"
        f"resources:\n  - {os.path.relpath(parent, tmp)}\n"
        f"components:\n  - {os.path.relpath(path, tmp)}\n")
    return build(tmp)


def main():
    if run(["helm", "version"]).returncode != 0:
        print("helm not found", file=sys.stderr)
        return 1
    ok = skipped = 0
    failures, skips = [], []
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        for (path, sub), owner in sorted(children().items()):
            target = ROOT / path.lstrip("./")
            if not target.is_dir():
                skips.append((owner, path, "path not in this checkout"))
                skipped += 1
                continue
            docs, err = build(target)
            if docs is None:
                failures.append((owner, path, "?", f"kustomize build failed: {err}"))
                continue
            docs = substitute(docs, dict(sub))
            repos, releases = charts(docs)
            for rel in releases:
                who = rel.get("metadata", {}).get("name", "?")
                status, detail = template(rel, repos, work)
                if status == "ok":
                    ok += 1
                elif status == "skip":
                    skips.append((owner, path, f"{who}: {detail}"))
                    skipped += 1
                else:
                    failures.append((owner, path, who, detail))

        with tempfile.TemporaryDirectory(dir=ROOT) as sub_tmp:
            sub_tmp = Path(sub_tmp)
            for path, (mode, parent) in sorted(strays().items()):
                shown = f"./{path.relative_to(ROOT)}"
                docs, err = build_stray(path, mode, parent, sub_tmp)
                if docs is None:
                    skips.append(("(no bundle)", shown, err))
                    skipped += 1
                    continue
                docs = substitute(docs, {})
                repos, releases = charts(docs)
                for rel in releases:
                    who = rel.get("metadata", {}).get("name", "?")
                    status, detail = template(rel, repos, work)
                    if status == "ok":
                        ok += 1
                    elif status == "skip":
                        skips.append(("(no bundle)", shown, f"{who}: {detail}"))
                        skipped += 1
                    else:
                        failures.append(("(no bundle)", shown, who, detail))

    for owner, path, who, detail in failures:
        print(f"FAIL {owner} ({path}) -> HelmRelease {who}", file=sys.stderr)
        for line in detail.splitlines():
            print(f"     {line}", file=sys.stderr)
    for skip in skips:
        print(f"skipped {skip[0]} ({skip[1]}): {skip[-1]}")
    if failures:
        print(f"\n{len(failures)} HelmRelease(s) whose values their chart rejects.",
              file=sys.stderr)
        return 1
    print(f"OK: {ok} HelmRelease(s) template cleanly, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
