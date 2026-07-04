"""
AI日报 发布模块
==============
将生成的HTML日报推送到GitHub Pages。
"""

import os
import subprocess
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ai-daily.publisher")

REPO_DIR = "/tmp/ai-daily-repo"
REMOTE_URL = "https://github.com/suifei/ai-daily-gguf-digest.git"
BRANCH = "gh-pages"


def _git(cmd_args, cwd=None):
    """Run a git command and return (success, stdout, stderr)."""
    result = subprocess.run(
        cmd_args, capture_output=True, text=True, cwd=cwd or REPO_DIR, timeout=60
    )
    return result.returncode == 0, result.stdout, result.stderr


def publish_to_github(date_str: str, html_path: str) -> bool:
    """
    Publish daily digest to GitHub Pages.

    Strategy: use the existing repo, checkout/create gh-pages branch,
    add the dist contents, commit and push.

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

        # Copy index.html
        index_src = os.path.join(dist_dir, "index.html")
        if os.path.exists(index_src):
            shutil.copy2(index_src, os.path.join(dist_dir, "index.html"))

        # Work from the dist directory for git operations
        os.chdir(dist_dir)

        # Ensure git is initialized in dist dir
        ok, _, err = _git(["git", "rev-parse", "--is-inside-work-tree"], cwd=dist_dir)
        if not ok:
            logger.info("Initializing git in dist directory...")
            subprocess.run(["git", "init"], cwd=dist_dir, capture_output=True, check=True)
            _git(["git", "config", "user.email", "ai-daily@noreply.local"], cwd=dist_dir)
            _git(["git", "config", "user.name", "AI Daily Bot"], cwd=dist_dir)

        # Fetch gh-pages from origin
        _git(["git", "fetch", "origin", "gh-pages"], cwd=dist_dir)

        # Checkout or create gh-pages branch
        ok, _, err = _git(["git", "show-ref", "--verify", "--heads", "gh-pages"], cwd=dist_dir)
        if ok:
            logger.info("Checking out existing gh-pages branch...")
            _git(["git", "checkout", "gh-pages"], cwd=dist_dir)
        else:
            logger.info("Creating new gh-pages branch...")
            _git(["git", "checkout", "-b", "gh-pages", "origin/main"], cwd=dist_dir)

        # Add, commit, push
        _git(["git", "add", "."], cwd=dist_dir)
        status_ok, status_out, _ = _git(["git", "status", "--porcelain"], cwd=dist_dir)
        if status_ok and status_out.strip():
            # There are changes
            pass

        commit_msg = f"📰 AI日报 {date_str}\n\n自动发布当日GGUF量化模型快报"
        _git(["git", "commit", "-m", commit_msg], cwd=dist_dir)

        ok, out, err = _git(["git", "push", "origin", "gh-pages"], cwd=dist_dir)
        if not ok:
            logger.error(f"Push failed: {err}")
            # Try force push (in case of conflicts)
            logger.info("Retrying with force push...")
            ok, out, err = _git(["git", "push", "-f", "origin", "gh-pages"], cwd=dist_dir)
            if not ok:
                logger.error(f"Force push also failed: {err}")
                return False

        logger.info(f"✅ Published to GitHub Pages: https://suifei.github.io/ai-daily-gguf-digest/{filename}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git error: {e.stderr}")
        return False
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
