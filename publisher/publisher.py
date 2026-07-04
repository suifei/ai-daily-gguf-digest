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


def publish_to_github(date_str: str, html_path: str) -> bool:
    """
    Publish daily digest to GitHub Pages.
    
    Args:
        date_str: Date string YYYY-MM-DD
        html_path: Path to the generated HTML file
    
    Returns:
        True if successful
    """
    try:
        # Copy HTML to dist folder
        dist_dir = os.path.join(REPO_DIR, "dist")
        os.makedirs(dist_dir, exist_ok=True)
        
        filename = f"digest-{date_str}.html"
        dest_path = os.path.join(dist_dir, filename)
        
        # Copy the HTML file
        import shutil
        shutil.copy2(html_path, dest_path)
        logger.info(f"Copied {html_path} -> {dest_path}")
        
        # Copy static assets
        static_src = os.path.join(REPO_DIR, "static")
        static_dst = os.path.join(dist_dir, "static")
        if os.path.exists(static_src):
            if os.path.exists(static_dst):
                shutil.rmtree(static_dst)
            shutil.copytree(static_src, static_dst)
            logger.info("Copied static assets")
        
        # Git add, commit, push
        os.chdir(dist_dir)
        
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        
        commit_msg = f"📰 AI日报 {date_str}\n\n自动发布当日GGUF量化模型快报\n{len(os.listdir(dist_dir))} files"
        
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True, text=True)
        
        subprocess.run(["git", "push", "origin", BRANCH], check=True, capture_output=True, text=True)
        
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
