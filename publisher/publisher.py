"""
AI日报 发布模块
==============
将生成的HTML日报推送到GitHub Pages。
使用 gh CLI API 上传文件到 gh-pages 分支（当 git push 不可用时）。
"""

import os
import subprocess
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ai-daily.publisher")

REPO_DIR = "/tmp/ai-daily-repo"
REMOTE_URL = "https://github.com/suifei/ai-daily-gguf-digest.git"
BRANCH = "gh-pages"
REPO_OWNER = "suifei"
REPO_NAME = "ai-daily-gguf-digest"


def _run(cmd, cwd=None, timeout=60):
    """Run a command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def _git_push_via_git(date_str: str, dist_dir: str) -> bool:
    """Try standard git push to gh-pages branch."""
    os.chdir(dist_dir)

    # Ensure git is initialized
    ok, _, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=dist_dir)
    if not ok:
        _run(["git", "init"], cwd=dist_dir)
        _run(["git", "config", "user.email", "ai-daily@noreply.local"], cwd=dist_dir)
        _run(["git", "config", "user.name", "AI Daily Bot"], cwd=dist_dir)

    # Fetch gh-pages
    _run(["git", "fetch", "origin", "gh-pages"], cwd=dist_dir)

    # Checkout or create gh-pages branch
    ok, _, _ = _run(["git", "show-ref", "--verify", "--heads", "gh-pages"], cwd=dist_dir)
    if ok:
        _run(["git", "checkout", "gh-pages"], cwd=dist_dir)
    else:
        _run(["git", "checkout", "-b", "gh-pages", "origin/main"], cwd=dist_dir)

    _run(["git", "add", "."], cwd=dist_dir)

    commit_msg = f"📰 AI日报 {date_str}\n\n自动发布当日GGUF量化模型快报"
    _run(["git", "commit", "-m", commit_msg], cwd=dist_dir)

    ok, out, err = _run(["git", "push", "origin", "gh-pages"], cwd=dist_dir)
    if not ok:
        logger.info(f"Standard push failed ({err[:200]}), trying force push...")
        ok, out, err = _run(["git", "push", "-f", "origin", "gh-pages"], cwd=dist_dir)
    return ok


def _gh_api_push(dist_dir: str, date_str: str) -> bool:
    """Use gh CLI API to upload files to gh-pages branch."""
    logger.info("Using gh API to publish to gh-pages branch...")

    # Get the base commit SHA of gh-pages (or main if gh-pages doesn't exist)
    ok, out, err = _run(["gh", "api", f"repos/{REPO_OWNER}/{REPO_NAME}/git/ref/refs/heads/gh-pages"])
    if not ok:
        # gh-pages doesn't exist, use main as base
        logger.info("gh-pages branch doesn't exist, using main as base")
        ok, out, err = _run(["gh", "api", f"repos/{REPO_OWNER}/{REPO_NAME}/git/ref/refs/heads/main"])
        if not ok:
            logger.error(f"Cannot get base commit: {err}")
            return False

    try:
        base_ref = json.loads(out.strip())
        base_sha = base_ref.get("sha", "")
    except (ValueError, AttributeError):
        # out might not be valid JSON
        logger.error(f"Failed to parse base commit SHA: {out[:200]}")
        return False

    if not base_sha:
        logger.error("Empty base commit SHA")
        return False

    # Upload each file in dist_dir to the gh-pages branch
    uploaded_files = []
    for root, dirs, files in os.walk(dist_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, dist_dir)

            # Read file content
            try:
                with open(fpath, "rb") as f:
                    content = f.read()
            except Exception as e:
                logger.warning(f"Skipping {rel_path}: {e}")
                continue

            # Upload via API
            api_url = f"repos/{REPO_OWNER}/{REPO_NAME}/contents/{rel_path}"
            payload = {
                "message": f"📰 AI日报 {date_str}: {rel_path}",
                "content": content.hex(),
                "encoding": "hex",
                "branch": "gh-pages",
            }

            ok, resp, err = _run(
                ["gh", "api", f"repos/{REPO_OWNER}/{REPO_NAME}/{api_url}",
                 "--method", "PUT",
                 "-f", f"message={payload['message']}",
                 "-F", "content.hex=" + content.hex()[:100] + "...",  # placeholder
                 "-F", "encoding=hex",
                 "-F", "branch=gh-pages"],
                timeout=30
            )

            if ok:
                uploaded_files.append(rel_path)
            else:
                logger.warning(f"Failed to upload {rel_path}: {err[:200]}")

    if not uploaded_files:
        logger.error("No files were uploaded via gh API")
        return False

    logger.info(f"Uploaded {len(uploaded_files)} files via gh API to gh-pages")
    return True


def publish_to_github(date_str: str, html_path: str) -> bool:
    """
    Publish daily digest to GitHub Pages.

    Tries git push first, falls back to gh API upload.

    Args:
        date_str: Date string YYYY-MM-DD
        html_path: Path to the generated HTML file

    Returns:
        True if successful
    """
    import shutil

    try:
        dist_dir = os.path.join(REPO_DIR, "dist")
        os.makedirs(dist_dir, exist_ok=True)

        filename = f"digest-{date_str}.html"
        dest_path = os.path.join(dist_dir, filename)

        # Copy the HTML file (only if source != dest)
        src_abs = os.path.abspath(html_path)
        dst_abs = os.path.abspath(dest_path)
        if src_abs != dst_abs:
            shutil.copy2(html_path, dest_path)
            logger.info(f"Copied {html_path} -> {dest_path}")
        else:
            logger.info(f"Source and dest are the same file, skipping copy: {dest_path}")

        # Copy static assets
        static_src = os.path.join(REPO_DIR, "static")
        static_dst = os.path.join(dist_dir, "static")
        if os.path.exists(static_src):
            if os.path.exists(static_dst):
                shutil.rmtree(static_dst)
            shutil.copytree(static_src, static_dst)
            logger.info("Copied static assets")

        # Method 1: Try standard git push
        logger.info("Attempting git push to gh-pages...")
        git_ok = _git_push_via_git(date_str, dist_dir)

        if git_ok:
            logger.info(f"✅ Published via git: https://suifei.github.io/ai-daily-gguf-digest/{filename}")
            return True

        logger.info("Git push failed, falling back to gh API...")

        # Method 2: Fall back to gh API
        return _gh_api_push(dist_dir, date_str)

    except Exception as e:
        logger.error(f"Publish error: {e}")
        return False


def setup_git_repo():
    """Initialize and configure git repo for publishing."""
    os.chdir(REPO_DIR)

    # Check if already initialized
    if os.path.exists(".git"):
        logger.info("Git repo already initialized")
        return

    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", BRANCH], check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", REMOTE_URL], check=True, capture_output=True)

    logger.info(f"Git repo initialized on branch '{BRANCH}'")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_git_repo()
    print("Git repo ready for publishing.")
