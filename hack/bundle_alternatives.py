"""Which component sets a bundle has to be built with.

"Every component at once" is the strictest cheap check, and it cannot include
ALTERNATIVES. An alternative stands in for another component -- the same child
Kustomization under the same name, wired differently (velero-eso for velero)
-- so selecting both is one object defined twice, and kustomize refuses the
whole build. It says so with a line `# bundle-alternative-of: <component>` in
its kustomization.yaml; hack/check-bundle-components.sh reads the same marker.

Leaving alternatives out would report OK while they are unverified, so each is
built once more IN PLACE of the component it replaces.
"""
import re
from pathlib import Path

MARKER = re.compile(r"^# bundle-alternative-of: *(\S+)", re.M)


def alternative_of(component: Path):
    k = component / "kustomization.yaml"
    m = MARKER.search(k.read_text()) if k.exists() else None
    return m.group(1) if m else None


def selections(components: Path):
    """[(label, [component names])]: all but the alternatives, then one set per alternative."""
    names = sorted(d.name for d in components.iterdir() if d.is_dir())
    replaces = {n: alternative_of(components / n) for n in names}
    regular = [n for n in names if not replaces[n]]
    out = [("every component", regular)]
    for n, replaced in replaces.items():
        if not replaced:
            continue
        if replaced not in regular:
            raise SystemExit(f"{components / n}: declares itself an alternative of "
                             f"'{replaced}', which is not a component beside it")
        out.append((f"{n} in place of {replaced}",
                    [x for x in regular if x != replaced] + [n]))
    return out
