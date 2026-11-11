# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess
import sys


def run_git(args):
    """Run git commands and return output as text."""
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    return result.stdout.strip()


def commit_exists(commit_sha):
    """Check if the commit actually exisets in the repository."""
    ZERO_SHA = "0" * 40
    if not commit_sha or commit_sha == ZERO_SHA:
        return False
    res = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        capture_output=True,
    )
    return res.returncode == 0


def use_default_branch_merge_base(default_branch, head_sha):
    """Find the merge base with the default branch."""
    print(f"Using merge base with {default_branch}.")
    subprocess.run(["git", "fetch", "--no-tags", "origin", default_branch], capture_output=True)
    merge_base = run_git(["merge-base", head_sha, f"origin/{default_branch}"])
    return merge_base


def main():
    # 1. Fetch environment variables from GitHub Actions
    base_sha = os.environ.get("BASE_SHA", "")
    default_branch = os.environ.get("DEFAULT_BRANCH", "main")
    dockerfile = os.environ.get("DOCKERFILE", "")
    force_build = os.environ.get("FORCE_BUILD", "false").lower() == "true"
    head_sha = os.environ.get("HEAD_SHA", "")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    ref_name = os.environ.get("GITHUB_REF_NAME", "")

    # 2. Check force build option
    if force_build:
        print("Force build is enabled, proceeding with build.")
        set_output("skip", "false")
        sys.exit(0)

    if not dockerfile:
        print("Dockerfile path is missing, proceeding with build.")
        set_output("skip", "false")
        sys.exit(0)

    dockerfile_dir = os.path.dirname(dockerfile) or "."

    # 3. Ensure HEAD_SHA exists
    if not commit_exists(head_sha):
        print(f"Head SHA {head_sha} is unavailable, using checked out HEAD.")
        head_sha = run_git(["rev-parse", "HEAD"])

    # 4. Handle different GitHub events
    if event_name in ["pull_request", "merge_group"]:
        if not commit_exists(base_sha):
            print(f"Base SHA unavailable for {event_name}.")
            base_sha = use_default_branch_merge_base(default_branch, head_sha)

    elif event_name == "push":
        if ref_name == default_branch:
            if not commit_exists(base_sha):
                print("No usable base SHA available for default branch push, proceeding with build.")
                set_output("skip", "false")
                sys.exit(0)
        else:
            base_sha = use_default_branch_merge_base(default_branch, head_sha)
    else:
        if not commit_exists(base_sha):
            print(f"No usable base SHA available for {event_name}, proceeding with build.")
            set_output("skip", "false")
            sys.exit(0)

    if not commit_exists(base_sha):
        print("No usable base SHA available, proceeding with build.")
        set_output("skip", "false")
        sys.exit(0)

    # 5. Actual check for changes using git diff
    result = subprocess.run(
        ["git", "diff", "--name-only", base_sha, head_sha, "--", dockerfile_dir],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Git diff failed, proceeding with build.")
        set_output("skip", "false")
        sys.exit(0)

    if not result.stdout.strip():
        print(f"No changes in {dockerfile_dir}, skipping build for {dockerfile}.")
        set_output("skip", "true")
    else:
        print(f"Changes detected in {dockerfile_dir}, proceeding with build for {dockerfile}.")
        set_output("skip", "false")

def set_output(name, value):
    """Write outputs using the modern GitHub Actions format."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}")


if __name__ == "__main__":
    main()
