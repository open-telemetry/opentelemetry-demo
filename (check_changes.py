import os
import subprocess
import sys
pathlib = __import__('pathlib')

def run_git(args):
    """دالة لتنفيذ أوامر الـ Git وإرجاع الناتج كـ نص"""
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    return result.stdout.strip()

def commit_exists(commit_sha):
    """بديل لدالة commit_exists في الـ Bash"""
    ZERO_SHA = "0" * 40
    if not commit_sha or commit_sha == ZERO_SHA:
        return False
    # التحقق مما إذا كان الـ Commit موجوداً فعلياً في المستودع
    res = subprocess.run(["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"], 
                         capture_output=True)
    return res.returncode == 0

def use_default_branch_merge_base(default_branch, head_sha):
    """إيجاد نقطة التقاء الأفرع (Merge Base)"""
    print(f"Using merge base with {default_branch}.")
    subprocess.run(["git", "fetch", "--no-tags", "origin", default_branch], capture_output=True)
    merge_base = run_git(["merge-base", head_sha, f"origin/{default_branch}"])
    return merge_base if merge_base else head_sha

def main():
    # 1. جلب المتغيرات البيئية من GitHub Actions
    base_sha = os.environ.get("BASE_SHA", "")
    default_branch = os.environ.get("DEFAULT_BRANCH", "main")
    dockerfile = os.environ.get("DOCKERFILE", "")
    force_build = os.environ.get("FORCE_BUILD", "false").lower() == "true"
    head_sha = os.environ.get("HEAD_SHA", "")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    ref_name = os.environ.get("GITHUB_REF_NAME", "")

    dockerfile_dir = os.path.dirname(dockerfile)

    # 2. فحص البناء الإجباري
    if force_build:
        print("Force build is enabled, proceeding with build.")
        set_output("skip", "false")
        sys.exit(0)

    # 3. التأكد من وجود HEAD_SHA
    if not commit_exists(head_sha):
        print(f"Head SHA {head_sha} is unavailable, using checked out HEAD.")
        head_sha = run_git(["rev-parse", "HEAD"])

    # 4. التعامل مع الأحداث المختلفة (Case equivalent)
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

    # 5. الفحص الفعلي للتغييرات عبر git diff
    diff_output = run_git(["diff", "--name-only", base_sha, head_sha, "--", dockerfile_dir])
    
    if not diff_output:
        print(f"No changes in {dockerfile_dir}, skipping build for {dockerfile}.")
        set_output("skip", "true")
    else:
        print(f"Changes detected in {dockerfile_dir}, proceeding with build for {dockerfile}.")
        set_output("skip", "false")

def set_output(name, value):
    """كتابة المخرجات بالطريقة الحديثة لـ GitHub Actions"""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}")

if __name__ == "__main__":
    main()