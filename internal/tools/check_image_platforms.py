#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Check that container images used by the demo are published for all
platforms the demo is built on and runs on.

CI builds images on amd64 runners. Builder stages pin
`FROM --platform=${BUILDPLATFORM}`, so CI only ever pulls their amd64
variant: a builder image without arm64 passes CI but breaks `make build` on
arm64 hosts such as Apple Silicon. This check inspects the manifests directly
(no pulls or builds) to catch that before merge.

Checked images:
    - every `FROM` image in a Dockerfile
    - every `*_IMAGE=` entry in .env (third-party images run by compose)

Usage:
    check_image_platforms.py
        Check every tracked Dockerfile and every .env image.
    check_image_platforms.py --base REF [--head REF]
        Check only what changed between the two refs: modified Dockerfiles,
        and .env image entries whose value changed.
    check_image_platforms.py FILE ...
        Check the given Dockerfiles.

Uses `docker buildx imagetools`, `podman` or `skopeo`, whichever is available
(override with IMAGE_INSPECT_TOOL=docker|podman|skopeo).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

REQUIRED_PLATFORMS = ("linux/amd64", "linux/arm64")
ENV_FILE = ".env"

INDEX_MEDIA_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}

FROM_RE = re.compile(
    r"^\s*FROM\s+(?:--platform=\S+\s+)?(?P<ref>\S+)(?:\s+AS\s+(?P<stage>\S+))?\s*$",
    re.IGNORECASE,
)
ENV_IMAGE_RE = re.compile(r"^(?P<key>[A-Z0-9_]+_IMAGE)=(?P<ref>\S+)\s*$")
DOCKERFILE_RE = re.compile(r"(^|/)Dockerfile[^/]*$")


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def commit_exists(ref):
    if not ref or set(ref) == {"0"}:
        return False
    return subprocess.run(
        ["git", "cat-file", "-e", f"{ref}^{{commit}}"], capture_output=True
    ).returncode == 0


def tracked_dockerfiles():
    return [p for p in git("ls-files").splitlines() if DOCKERFILE_RE.search(p)]


def changed_dockerfiles(base, head):
    # --diff-filter=d: a deleted Dockerfile has nothing left to check.
    changed = git("diff", "--name-only", "--diff-filter=d", base, head)
    return [p for p in changed.splitlines() if DOCKERFILE_RE.search(p)]


def env_images(text):
    """Return {key: (ref, line number)} for `*_IMAGE=` entries."""
    images = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = ENV_IMAGE_RE.match(line)
        if m and "$" not in m.group("ref"):
            images[m.group("key")] = (m.group("ref"), lineno)
    return images


def read_at(ref, path):
    """Return a file's content at a git ref, or "" if it did not exist."""
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True
    )
    return proc.stdout if proc.returncode == 0 else ""


def collect_env(base, head):
    """Return {image ref: [(.env, line), ...]}, limited to changes if base is set."""
    current = env_images(read_at(head, ENV_FILE) if base else _read(ENV_FILE))
    previous = env_images(read_at(base, ENV_FILE)) if base else {}
    images = {}
    for key, (ref, lineno) in current.items():
        if base and previous.get(key, (None,))[0] == ref:
            continue
        images.setdefault(ref, []).append((ENV_FILE, lineno))
    return images


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def collect_dockerfiles(paths, git_ref=None):
    """Return {image ref: [(path, line), ...]} for external base images.

    Files are read at `git_ref` when given, otherwise from the working tree.

    Skips references to earlier build stages, `scratch`, and references built
    from build args (they cannot be resolved without the build context).
    """
    images = {}
    skipped = []
    for path in paths:
        stages = set()
        text = read_at(git_ref, path) if git_ref else _read(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = FROM_RE.match(line)
            if not m:
                continue
            ref = m.group("ref")
            if m.group("stage"):
                stages.add(m.group("stage").lower())
            if ref.lower() in stages or ref.lower() == "scratch":
                continue
            if "$" in ref:
                skipped.append((path, lineno, ref))
                continue
            images.setdefault(ref, []).append((path, lineno))
    return images, skipped


def normalize(ref):
    """Fully qualify a reference and drop the tag when a digest is pinned.

    `podman manifest inspect` rejects tag+digest references, and the digest
    alone identifies the image anyway.
    """
    name, _, digest = ref.partition("@")
    if digest:
        last = name.rsplit("/", 1)[-1]
        if ":" in last:
            name = name[: len(name) - len(last)] + last.split(":", 1)[0]
    first = name.split("/", 1)[0]
    if "/" not in name:
        name = "docker.io/library/" + name
    elif "." not in first and ":" not in first and first != "localhost":
        name = "docker.io/" + name
    return f"{name}@{digest}" if digest else name


def pick_tool():
    tool = os.environ.get("IMAGE_INSPECT_TOOL")
    if tool:
        return tool
    if shutil.which("docker") and subprocess.run(
        ["docker", "buildx", "version"], capture_output=True
    ).returncode == 0:
        return "docker"
    for candidate in ("podman", "skopeo"):
        if shutil.which(candidate):
            return candidate
    sys.exit("error: need docker (with buildx), podman or skopeo to inspect images")


def fetch_manifest(tool, ref):
    cmd = {
        "docker": ["docker", "buildx", "imagetools", "inspect", "--raw", ref],
        "podman": ["podman", "manifest", "inspect", ref],
        "skopeo": ["skopeo", "inspect", "--raw", f"docker://{ref}"],
    }[tool]
    last_error = ""
    for attempt in range(3):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        last_error = (proc.stderr or proc.stdout).strip()
        time.sleep(2 ** attempt)
    raise RuntimeError(last_error)


def platforms_of(manifest):
    """Return the platforms in an image index, or None for a single image."""
    media_type = manifest.get("mediaType", "")
    if media_type not in INDEX_MEDIA_TYPES and "manifests" not in manifest:
        return None
    found = set()
    for entry in manifest.get("manifests", []):
        platform = entry.get("platform") or {}
        # Attestation manifests (provenance, SBOM) are listed as unknown/unknown.
        if platform.get("os", "unknown") == "unknown":
            continue
        found.add(f"{platform.get('os')}/{platform.get('architecture')}")
    return found


def check(tool, ref):
    try:
        manifest = fetch_manifest(tool, normalize(ref))
    except Exception as e:  # noqa: BLE001 - report any lookup failure
        return f"could not inspect image: {e}"
    platforms = platforms_of(manifest)
    if platforms is None:
        return (
            "is a single-platform image; a multi-platform index with "
            + " and ".join(REQUIRED_PLATFORMS)
            + " is required"
        )
    missing = [p for p in REQUIRED_PLATFORMS if p not in platforms]
    if missing:
        return (
            "is missing " + ", ".join(missing)
            + " (has: " + ", ".join(sorted(platforms)) + ")"
        )
    return None


def merge(*maps):
    merged = {}
    for m in maps:
        for ref, places in m.items():
            merged.setdefault(ref, []).extend(places)
    return merged


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--base", help="only check what changed between this git ref and --head"
    )
    parser.add_argument("--head", default="HEAD", help="default: HEAD")
    parser.add_argument("files", nargs="*", help="Dockerfiles to check")
    args = parser.parse_args(argv)

    base = args.base
    if base and not commit_exists(base):
        print(f"Base {base!r} is not an available commit; checking everything.")
        base = None

    if args.files:
        dockerfiles, env = args.files, {}
    elif base:
        dockerfiles, env = changed_dockerfiles(base, args.head), collect_env(base, args.head)
    else:
        dockerfiles, env = tracked_dockerfiles(), collect_env(None, None)

    from_images, skipped = collect_dockerfiles(
        dockerfiles, args.head if base and not args.files else None
    )
    images = merge(from_images, env)

    scope = f"changes since {base[:12]}" if base else "all files"
    print(f"Scope: {scope}")
    for path in dockerfiles:
        print(f"  {path}")
    if env:
        print(f"  {ENV_FILE} ({sum(len(v) for v in env.values())} image entries)")
    if not images:
        print("No images to check.")
        return 0

    for path, lineno, ref in skipped:
        print(f"skip {path}:{lineno}: {ref} uses a build arg")

    tool = pick_tool()
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(images, pool.map(lambda r: check(tool, r), images)))

    failures = 0
    for ref, problem in sorted(results.items()):
        if problem is None:
            print(f"ok   {ref}")
            continue
        for path, lineno in images[ref]:
            failures += 1
            message = f"{ref} {problem}"
            if in_actions:
                print(f"::error file={path},line={lineno}::{message}")
            print(f"FAIL {path}:{lineno}: {message}")

    print(f"\nChecked {len(images)} images with {tool}: {failures} problem(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
