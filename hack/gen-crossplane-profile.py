#!/usr/bin/env python3
"""The machinery profile is GENERATED. Its source is the KCL catalog.

`ManagementPlane` builds a management cluster from
`stuttgart-things/kcl`, `crossplane/xplane-crossplane-catalog` -- selected by
`spec.profile`, default `machinery`. That catalog's own header names the three
places it replaced, and one of them is this directory:

    stuttgart-things/flux cicd/crossplane  (an older generation of the same
    list, pointing at ghcr.io/stuttgart-things/crossplane/*)

Hand-maintaining the list here made a FOURTH transcription of something that has
one owner, and the copies had already drifted apart before anyone noticed: this
bundle carried cluster-backup v0.2.0 against the fleet's v0.1.0, opentofu v1.1.7
against v1.1.6, crossplane 2.4.0 against 2.3.3, and was missing two providers,
all five functions and three configurations. Every one of those would have
installed a management cluster that is not the one the fleet runs.

So the list is not written here any more. It is rendered from the catalog at a
PINNED version and committed, because Flux reads git and cannot evaluate KCL --
and `--check` proves the committed files still match.

WHAT IS GENERATED, and nothing else: the three things the catalog owns.

    crossplaneVersion  -> profiles/machinery/install/catalog-patch.yaml
    packages           -> profiles/machinery/configs/configs.yaml
    providerConfigs    -> profiles/machinery/provider-configs/provider-configs.yaml

WHAT IS NOT: the preconditions beside them. `preconditions.yaml` carries the
cluster-admin ClusterRoleBinding and the two flux EnvironmentConfigs -- things
a package DOCUMENTS as required and cannot ship, which the catalog deliberately
does not model. They are handwritten and stay handwritten.

NO SUBSTITUTION VARIABLES in the generated files. A pinned version that a
cluster can override is not a fleet fact any more, and the whole point of the
catalog is that every management cluster runs the same set. Override at the
catalog, in one PR, for everyone.

WHICH CATALOG FIELDS ARE RENDERED is declared, not implied -- see RENDERED and
IGNORED. A field the catalog grows and this file does not know aborts the run
rather than being dropped: a profile that silently ignores half of what the
catalog says is the same drift as a hand-maintained copy, only harder to see.

Usage:
    python3 hack/gen-crossplane-profile.py            # write
    python3 hack/gen-crossplane-profile.py --check    # verify, exit 1 on drift
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CATALOG = "ghcr.io/stuttgart-things/xplane-crossplane-catalog"
# Pinned, never floating. Bumping this is the ONLY way the package set moves,
# and the diff of that bump is the review.
#
# Renovate watches it (see renovate.json). A bump on its own FAILS the
# `--check` job, and that is deliberate: the generated files have to be
# regenerated in the same PR, which is what turns "the catalog moved" into a
# reviewable list of package versions instead of a one-line number change.
# renovate: datasource=docker depName=ghcr.io/stuttgart-things/xplane-crossplane-catalog
CATALOG_VERSION = "0.10.0"
PROFILE = "machinery"

OUT = ROOT / "cicd/crossplane/profiles" / PROFILE

BANNER = (
    "# GENERATED -- DO NOT EDIT.\n"
    "#\n"
    f"# Source: oci://{CATALOG}:{CATALOG_VERSION}, profile `{PROFILE}`.\n"
    "# Regenerate: python3 hack/gen-crossplane-profile.py\n"
    "#\n"
    "# This is the same list `ManagementPlane` installs, so a cluster built by\n"
    "# Flux and one built by Crossplane are the same cluster. Change a version\n"
    "# in the catalog, not here -- an edit here is reverted by the next run and\n"
    "# fails CI in between.\n"
)


def catalog():
    """Render the profile by evaluating the published KCL module."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = Path(tmp) / "render"
        run = lambda *a: subprocess.run(a, cwd=mod, capture_output=True, text=True)
        # `kcl mod init NAME` creates ./NAME, so it runs one level up.
        r = subprocess.run(["kcl", "mod", "init", "render"], cwd=tmp,
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"kcl mod init failed:\n{r.stderr}")
        r = run("kcl", "mod", "add", f"oci://{CATALOG}", "--tag", CATALOG_VERSION)
        if r.returncode != 0:
            sys.exit(f"kcl mod add failed:\n{r.stderr}")
        (mod / "main.k").write_text(
            "import xplane_crossplane_catalog as cat\n"
            f'_p = cat.get("{PROFILE}")\n'
            "crossplaneVersion = _p.crossplaneVersion\n"
            "namespace = _p.namespace\n"
            "packages = _p.packages\n"
            "providerConfigs = _p.providerConfigs\n"
        )
        r = run("kcl", "run", "main.k", "--format", "json")
        if r.returncode != 0:
            sys.exit(f"kcl run failed:\n{r.stderr}")
        return json.loads(r.stdout)


def doc(body, indent=0):
    """Minimal YAML emitter -- readable output, no library quoting surprises."""
    pad = "  " * indent
    out = []
    for k, v in body.items():
        if isinstance(v, dict):
            if not v:
                # `{}`, not a bare `key:`. The latter parses as null, and a
                # DeploymentRuntimeConfig's deploymentTemplate.spec.selector is
                # a required object -- null there is rejected by the API server.
                out.append(f"{pad}{k}: {{}}")
                continue
            out.append(f"{pad}{k}:")
            out.append(doc(v, indent + 1))
        elif isinstance(v, list):
            if not v:
                out.append(f"{pad}{k}: []")
                continue
            out.append(f"{pad}{k}:")
            for item in v:
                if isinstance(item, dict):
                    inner = doc(item, indent + 2).lstrip()
                    out.append(f"{pad}  - {inner}")
                else:
                    out.append(f"{pad}  - {scalar(item)}")
        else:
            out.append(f"{pad}{k}: {scalar(v)}")
    return "\n".join(x for x in out if x)


YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "y", "n",
              "null", "~"}


def scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if "\n" in s:
        body = "\n".join("    " + line for line in s.rstrip("\n").split("\n"))
        return "|\n" + body
    # Quote anything YAML would otherwise retype. A chart version like 2.3.3 is
    # safe unquoted, 2.3 would become a float.
    # The word list is YAML 1.1's, case-insensitively: sigs.k8s.io/yaml reads
    # `value: True`, `on` or `no` as a bool, and an env value that arrives as a
    # bool is rejected. ": " and " #" would end the scalar early.
    if (s == "" or s[0] in "&*!%@`{[|>#'\"-?:," or s[-1] in " :"
            or s.lower() in YAML_WORDS or ": " in s or " #" in s):
        return json.dumps(s)
    try:
        float(s)
        return json.dumps(s)
    except ValueError:
        return s


# Catalog fields this generator RENDERS, and the ones it deliberately does not.
# Anything outside both sets aborts the run: the catalog is the source of truth
# and a field it grew that lands here unnoticed is silent drift in the one
# direction this generator exists to prevent -- the profile would keep
# rendering, `--check` would keep passing, and the cluster would be missing
# whatever the new field says.
#
# NOT rendered, each for its own reason:
#
#   pulls        documentation of the dependency graph, asserted in the catalog
#                and checked there. Nothing to apply.
#   providerCrd  a thing to WAIT for, which is the play's execution model. Flux
#                waits through a Kustomization's healthCheckExprs instead, in
#                the cluster folder -- see stuttgart-things#3136.
#   clusterRole  the play binds it per provider, to a ServiceAccount the chart
#                pins by name. This profile does not: configs/preconditions.yaml
#                binds cluster-admin to the GROUP
#                system:serviceaccounts:crossplane-system, which covers every
#                provider without depending on an SA name that carries the
#                package-revision hash. Emitting per-provider bindings here
#                would be one real grant and N decorative ones.
RENDERED = {"kind", "name", "package", "apiVersion", "env", "resources",
            "runtimeConfig"}
IGNORED = {"pulls", "providerCrd", "clusterRole"}


def env_value(v):
    """A catalog env value as the string a container env var has to be.

    Not str(): that turns a KCL `True` into "True", where the YAML convention
    for the same flag is "true". scalar() quotes either spelling.
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def runtime_doc(p):
    """The DeploymentRuntimeConfig for a provider that pins env or resources.

    Shape-identical to what the play's chart emits from the same two fields
    (stuttgart-things/helm, cicd/values/crossplane-providers.values.yaml.gotmpl)
    -- a cluster built either way has to be the same cluster, and this is the
    object that decides how hard its providers hit the API server.

    NO serviceAccountTemplate, unlike that chart. It pins the SA name only
    because its ClusterRoleBinding names the SA; here the binding is
    group-scoped (see IGNORED above), so letting Crossplane derive the SA is
    both fine and one less thing to keep level.
    """
    container = {"name": "package-runtime"}
    if p.get("env"):
        # env, not args: args in a DeploymentRuntimeConfig REPLACE the image's
        # own arguments instead of adding to them.
        # env_value(), so a catalog value written bare (`PROVIDER_POLL = 3600`,
        # `DEBUG = True`) still renders as a quoted string -- a container env
        # value has to be one and the API server rejects a number or a bool.
        container["env"] = [{"name": k, "value": env_value(v)}
                            for k, v in sorted(p["env"].items())]
    if p.get("resources"):
        container["resources"] = p["resources"]
    return doc({
        "apiVersion": "pkg.crossplane.io/v1beta1",
        "kind": "DeploymentRuntimeConfig",
        "metadata": {"name": p["name"]},
        "spec": {"deploymentTemplate": {"spec": {
            "selector": {},
            "template": {"spec": {"containers": [container]}},
        }}},
    })


def package_docs(packages):
    """Providers, then Functions, then Configurations -- the install order."""
    out = []
    for kind in ("Provider", "Function", "Configuration"):
        for p in packages:
            if p["kind"] != kind:
                continue
            unknown = sorted(set(p) - RENDERED - IGNORED)
            if unknown:
                sys.exit(f"{p['name']}: catalog field(s) {', '.join(unknown)} "
                         f"are not rendered by this generator. The catalog "
                         f"moved ahead of it -- teach it the field (and say in "
                         f"RENDERED/IGNORED which one it is) before bumping "
                         f"CATALOG_VERSION.")
            body = {
                "apiVersion": p.get("apiVersion") or "pkg.crossplane.io/v1",
                "kind": kind,
                "metadata": {"name": p["name"]},
                "spec": {"package": p["package"]},
            }
            external = p.get("runtimeConfig")
            if p.get("env") or p.get("resources"):
                if kind != "Provider":
                    sys.exit(f"{p['name']}: env/resources are a provider "
                             f"runtime setting, and this is a {kind}.")
                if external:
                    sys.exit(f"{p['name']}: the catalog sets runtimeConfig "
                             f"({external}) AND env/resources. A Provider has "
                             f"exactly one runtimeConfigRef, so these two "
                             f"cannot both apply -- put the env and resources "
                             f"into whatever ships {external}, or drop "
                             f"runtimeConfig and let this generator own the "
                             f"DeploymentRuntimeConfig.")
                # The DRC sits next to its Provider for the reader. Apply order
                # is not decided here -- kustomize and the kustomize-controller
                # sort by kind -- and a Provider whose runtimeConfigRef is not
                # there yet only retries.
                out.append(runtime_doc(p))
                body["spec"]["runtimeConfigRef"] = {
                    "apiVersion": "pkg.crossplane.io/v1beta1",
                    "kind": "DeploymentRuntimeConfig",
                    "name": p["name"],
                }
            elif external:
                # A DeploymentRuntimeConfig this profile does NOT create: the
                # catalog names one that something else on the cluster ships.
                # provider-kubeconfig is the case -- its CA mount comes from
                # the provider-kubeconfig-vault chart, which cannot also own a
                # field on a CR the package manager created.
                #
                # So this reference is a CONTRACT, and an unkept one is
                # visible: a Provider pointed at a config that is not on the
                # cluster does not start. That is the right failure -- the
                # alternative, leaving the reference out, gives a provider that
                # runs and fails every login on an unknown certificate
                # authority instead.
                if kind != "Provider":
                    sys.exit(f"{p['name']}: runtimeConfig is a provider "
                             f"runtime setting, and this is a {kind}.")
                body["spec"]["runtimeConfigRef"] = {
                    "apiVersion": "pkg.crossplane.io/v1beta1",
                    "kind": "DeploymentRuntimeConfig",
                    "name": external,
                }
            out.append(doc(body))
    return out


def render(data):
    """{relative path: file content} for every generated file."""
    files = {}

    files["configs/configs.yaml"] = (
        BANNER
        + "#\n"
        + "# Providers, then Functions, then Configurations -- the catalog's own\n"
        + "# order. A Configuration whose functions are missing reconciles into an\n"
        + "# error rather than waiting, so the order is not cosmetic even though\n"
        + "# one Kustomization applies all three in a single pass.\n"
        + "#\n"
        + "# The LONG CR names are the point. Crossplane derives that name from the\n"
        + "# package path, so an explicit CR and a dependsOn-derived one are the SAME\n"
        + "# lock node instead of two -- which is what makes the #247 collision\n"
        + "# impossible here rather than merely unlikely, and why this list may name\n"
        + "# a package that another package also pulls. Functions are the exception\n"
        + "# and stay short: Compositions reference them by name in `functionRef`.\n"
        + "#\n"
        + "# A provider the catalog gives `env` or `resources` is preceded by its\n"
        + "# DeploymentRuntimeConfig and carries a runtimeConfigRef to it. That is\n"
        + "# not tuning for its own sake: at the image defaults an upjet provider\n"
        + "# re-runs terraform per resource per poll, and on u26-kind3 that held the\n"
        + "# node at load 8 and cost ~3950 control-plane restarts in 39 days, because\n"
        + "# a saturated API server misses lease renewals.\n"
        + "---\n"
        + "\n---\n".join(package_docs(data["packages"]))
        + "\n"
    )

    pcs = []
    for pc in data["providerConfigs"]:
        pcs.append(doc({
            "apiVersion": pc["apiVersion"],
            "kind": pc["kind"],
            "metadata": {"name": pc["name"]},
            "spec": pc["spec"],
        }))
    files["provider-configs/provider-configs.yaml"] = (
        BANNER
        + "#\n"
        + "# All three, because this profile installs all three providers itself.\n"
        + "# They are an instance of a CRD each PROVIDER registers, which is a later\n"
        + "# moment than the chart being installed -- hence a Kustomization of their\n"
        + "# own, behind the one that applies configs.yaml.\n"
        + "---\n"
        + "\n---\n".join(pcs)
        + "\n"
    )

    files["install/catalog-patch.yaml"] = (
        BANNER
        + "#\n"
        + "# Two values, both from the catalog:\n"
        + "#\n"
        + "#   the chart version, which the fleet pins per profile -- so this profile\n"
        + "#   deliberately does NOT read ${CROSSPLANE_VERSION}, the bundle-wide\n"
        + "#   variable the cicd-platform profile uses;\n"
        + "#\n"
        + "#   an EMPTY provider list, because the providers are package CRs in\n"
        + "#   configs.yaml under the catalog's derived names. Letting the chart\n"
        + "#   install them too would put the same source under a second CR.\n"
        + "- op: replace\n"
        + "  path: /spec/chart/spec/version\n"
        + f'  value: "{data["crossplaneVersion"]}"\n'
        + "- op: replace\n"
        + "  path: /spec/values/provider/packages\n"
        + "  value: []\n"
    )
    return files


def main():
    check = "--check" in sys.argv
    if subprocess.run(["which", "kcl"], capture_output=True).returncode != 0:
        # Same policy as check-crossplane-deps.py and skopeo: a check that turns
        # red on a runner without a tool teaches people to ignore it.
        print("note: kcl not installed -- machinery profile not verified "
              "against the catalog")
        return 0

    files = render(catalog())
    drift = []
    for rel, content in files.items():
        path = OUT / rel
        current = path.read_text() if path.exists() else None
        if current == content:
            continue
        if check:
            drift.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"wrote {path.relative_to(ROOT)}")

    if check and drift:
        for rel in drift:
            print(f"FAIL {(OUT / rel).relative_to(ROOT)}: does not match "
                  f"{CATALOG}:{CATALOG_VERSION}", file=sys.stderr)
        print("     The machinery profile is generated. Run "
              "`python3 hack/gen-crossplane-profile.py` and commit the result; "
              "to change a version, change the CATALOG_VERSION pin or the "
              "catalog itself.", file=sys.stderr)
        return 1
    if check:
        print(f"OK: machinery profile matches {CATALOG}:{CATALOG_VERSION} "
              f"({len(files)} generated file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
