#!/usr/bin/env python3
"""Check that every substituted image tag / OCIRepository ref actually exists.

Renovate writes these defaults, and a manager misconfigured with
extractVersionTemplate will happily strip a "v" that the registry requires --
producing a tag that resolves to nothing until a deploy fails. This walks the
manifests, resolves each default against the real registry and reports misses.

Only ghcr.io and docker.io are queried; anything else is reported as skipped
rather than silently counted as fine.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT = 20
UNREADABLE = "unreadable"
_tag_cache: dict[str, set[str] | str | None] = {}


def _get(url: str, token: str | None = None) -> tuple[dict, str | None]:
    """Fetch JSON and return it with the Link rel=next URL, if any."""
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        body = json.load(r)
        link = r.headers.get("link", "")
    nxt = None
    m = re.search(r'<([^>]+)>\s*;\s*rel="?next"?', link)
    if m:
        nxt = m.group(1)
    return body, nxt


def _all_tags(listing: str, host: str, token: str | None) -> set[str]:
    """Registries page tag lists -- ghcr.io caps at 100 without ?n=, and a repo
    with many tags still spans pages. Miss this and existing tags look absent."""
    tags: set[str] = set()
    url = f"{listing}?n=1000"
    for _ in range(50):  # generous page cap, guards against a cyclic Link header
        body, nxt = _get(url, token)
        tags.update(body.get("tags") or [])
        if not nxt:
            break
        url = nxt if nxt.startswith("http") else f"https://{host}{nxt}"
    return tags


def tags_for(image: str) -> set[str] | str | None:
    """Return the tag set for host/path, or None if the registry is unsupported."""
    if image in _tag_cache:
        return _tag_cache[image]

    host, _, path = image.partition("/")
    if host == "ghcr.io":
        auth = f"https://ghcr.io/token?scope=repository:{path}:pull&service=ghcr.io"
        listing = f"https://ghcr.io/v2/{path}/tags/list"
    elif host in ("docker.io", "registry-1.docker.io", "index.docker.io"):
        if "/" not in path:
            path = f"library/{path}"
        auth = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{path}:pull"
        listing = f"https://registry-1.docker.io/v2/{path}/tags/list"
    else:
        _tag_cache[image] = None
        return None

    try:
        token = _get(auth)[0].get("token")
        tags = _all_tags(listing, host if host != "docker.io" else "registry-1.docker.io", token)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError):
        # 403/404/network: the repo may be private or renamed. Either way we
        # cannot judge its tags -- report it as unverifiable, never as missing.
        tags = UNREADABLE
    _tag_cache[image] = tags
    return tags


# image: <repo>:${VAR:-<tag>}
IMAGE_RE = re.compile(r"image:\s*(?P<image>[^:$\s]+):\$\{[A-Z0-9_]+:-(?P<tag>[^}]+)\}")
# OCIRepository: url: oci://<repo> ... ref: tag: ${VAR:-<tag>}
OCI_RE = re.compile(
    r"url:\s*oci://(?P<image>\S+)\s*\n\s*ref:\s*\n\s*tag:\s*\$\{[A-Z0-9_]+:-(?P<tag>[^}]+)\}"
)
# Crossplane package refs -- `package: ghcr.io/org/pkg:${VAR:-v1.2.3}` and the
# provider list entries `- xpkg.../provider-helm:${VAR:-v1.4.0}`. Renovate
# rewrites these defaults through its own customManager, so they are exposed to
# exactly the extractVersion "v"-stripping this script exists to catch -- but
# neither pattern above matches a `package:` key, so until now they were the one
# family of substituted tags nothing verified. xpkg.* is reported as skipped
# (only ghcr.io and docker.io are queried); the ghcr.io ones are checked.
# The `-` branch is anchored to a real YAML list marker at start of line: a
# bare `-` also matches the one inside `${VAR:-default}`, which turns
# `imageName: ${RAG_PG_IMAGE:-ghcr.io/org/img}:${RAG_PG_IMAGE_TAG:-16}` into a
# lookup for the repository `ghcr.io/org/img}`. `}` is excluded from the image
# charset for the same reason.
PACKAGE_RE = re.compile(
    r"(?:package:|^\s*-)\s*(?P<image>(?:xpkg\.[^:$\s}]+|ghcr\.io/[^:$\s}]+))"
    r":\$\{[A-Z0-9_]+:-(?P<tag>[^}]+)\}",
    re.MULTILINE,
)


def main(roots: list[str]) -> int:
    missing, skipped, unreadable, checked = [], [], [], 0

    for root in roots:
        for f in sorted(Path(root).rglob("*.yaml")):
            text = f.read_text()
            for rx in (IMAGE_RE, OCI_RE, PACKAGE_RE):
                for m in rx.finditer(text):
                    image, tag = m.group("image"), m.group("tag")
                    if "/" not in image:               # bare docker hub name
                        image = f"docker.io/library/{image}"
                    elif image.count("/") == 1 and "." not in image.split("/")[0]:
                        image = f"docker.io/{image}"
                    line = text[: m.start()].count("\n") + 1

                    tags = tags_for(image)
                    if tags is None:
                        skipped.append(f"  {f}:{line}  {image}:{tag}  (registry not queried)")
                        continue
                    if tags is UNREADABLE:
                        unreadable.append(f"  {f}:{line}  {image}:{tag}  (private, renamed or gone)")
                        continue
                    checked += 1
                    if tag not in tags:
                        near = sorted(t for t in tags if t.lstrip("v").startswith(tag.lstrip("v")[:3]))
                        hint = f"  did you mean: {', '.join(near[-3:])}" if near else ""
                        missing.append(f"  {f}:{line}  {image}:{tag} does not exist{hint}")

    if skipped:
        print("Skipped (only ghcr.io and docker.io are queried):")
        print("\n".join(sorted(set(skipped))))
        print()

    if unreadable:
        print("Could not read these repositories -- tags unverified:")
        print("\n".join(sorted(set(unreadable))))
        print()

    if missing:
        print(f"Tags that do not exist ({len(missing)} of {checked} checked):")
        print("\n".join(missing))
        print()
        print("A default that resolves to nothing fails at deploy time, not here.")
        return 1

    print(f"OK: all {checked} substituted image tags exist in their registry.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["apps", "infra", "cicd"]))
