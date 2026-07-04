#!/usr/bin/env python3
"""
AI日报 GGUF量化模型快报 — 主入口脚本
====================================
每小时扫描一次 HuggingFace，发现新模型后存入待审核区。
每晚20:00（北京时间）生成并发布日报。

用法:
    python3 main.py --scan          # 扫描新模型
    python3 main.py --approve <repo_id>  # 审核并批准单个模型
    python3 main.py --approve-all   # 批准所有待审模型
    python3 main.py --publish       # 生成并发布日报
    python3 main.py --full          # 完整流程：扫描 + 审核 + 发布
"""

import sys
import os
import json
import argparse
import logging
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, "/tmp/ai-daily-repo")

from scraper.gguf_scraper import scrape_today_models, save_pending_models
from review.model_review import (
    init_database, load_pending_models, approve_model,
    get_approved_models_for_date, export_csv, log_digest,
    check_duplicate, upsert_model
)
from renderer.magazine_renderer import generate_magazine_html, generate_index_page
from publisher.publisher import publish_to_github, setup_git_repo

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-daily.main")

DATE_FORMAT = "%Y-%m-%d"


def cmd_scan(args):
    """Scan HuggingFace for new GGUF models."""
    logger.info("=" * 60)
    logger.info("🔍 STARTING SCAN: Looking for new GGUF models")
    logger.info("=" * 60)
    
    date_str = datetime.now(timezone.utc).strftime(DATE_FORMAT)
    
    models = scrape_today_models(date_str)
    
    if not models:
        logger.info("No new GGUF models found.")
        return []
    
    # Save to pending directory
    output_path = save_pending_models(models, date_str)
    
    logger.info(f"\n✅ Scan complete: {len(models)} new models found")
    logger.info(f"📁 Saved to: {output_path}")
    
    for m in models:
        logger.info(f"  • {m['model_name']} ({m['repo_id']}) — {len(m.get('gguf_files', []))} variants")
    
    return models


def cmd_approve(args, model_info: dict, chinese_summary: str = "", chinese_desc: str = "", risk_level: str = "low", notes: str = ""):
    """Approve a single model.
    
    Args:
        model_info: Raw model info from scraper
        chinese_summary: AI-generated Chinese capability summary (~500 chars)
        chinese_desc: Chinese translation of description
        risk_level: 'low', 'medium', 'high'
        notes: Review notes
    """
    date_str = datetime.now(timezone.utc).strftime(DATE_FORMAT)
    
    repo_id = model_info["repo_id"]
    
    # Check if already approved
    if check_duplicate(repo_id, model_info.get("gguf_files", [{}])[0].get("quantization", "")):
        logger.info(f"⏭️  Already in database: {repo_id}")
        return False
    
    # Add review metadata
    model_info["chinese_summary"] = chinese_summary
    model_info["chinese_description"] = chinese_desc or model_info.get("description", "")
    model_info["risk_level"] = risk_level
    model_info["review_notes"] = notes
    model_info["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    
    # Approve and save
    output = approve_model(model_info, date_str)
    logger.info(f"✅ Approved: {repo_id}")
    return True


def cmd_approve_all(args):
    """Approve all pending models for today.
    
    During approval, AI generates Chinese summaries and translations.
    In practice, the AI reviewer reviews each model and provides
    the chinese_summary, chinese_desc, risk_level, and notes.
    """
    from review.chinese_summary import generate_chinese_summary
    
    date_str = datetime.now(timezone.utc).strftime(DATE_FORMAT)
    
    pending = load_pending_models(date_str)
    
    if not pending:
        logger.info("No pending models to approve.")
        return 0
    
    logger.info(f"📋 {len(pending)} pending models to approve")
    
    approved = 0
    for model in pending:
        try:
            # Auto-generate Chinese summary (AI reviewer refines this)
            chinese_summary = generate_chinese_summary(model)
            logger.info(f"  📝 Summary for {model['model_name']}: {chinese_summary[:80]}...")
            
            if cmd_approve(args, model, chinese_summary=chinese_summary):
                approved += 1
        except Exception as e:
            logger.error(f"Failed to approve {model['repo_id']}: {e}")
    
    logger.info(f"✅ Approved {approved}/{len(pending)} models")
    return approved


def cmd_publish(args):
    """Generate and publish the daily digest."""
    logger.info("=" * 60)
    logger.info("📰 GENERATING DAILY DIGEST")
    logger.info("=" * 60)
    
    date_str = datetime.now(timezone.utc).strftime(DATE_FORMAT)
    
    # Get approved models for today
    models = get_approved_models_for_date(date_str)
    
    if not models:
        logger.info("No approved models for today. Nothing to publish.")
        return False
    
    logger.info(f"📊 {len(models)} approved models for {date_str}")
    
    # Export CSV
    csv_path = export_csv(date_str)
    logger.info(f"📄 CSV exported: {csv_path}")
    
    # Generate magazine HTML
    dist_dir = "/tmp/ai-daily-repo/dist"
    os.makedirs(dist_dir, exist_ok=True)
    
    html_path = os.path.join(dist_dir, f"digest-{date_str}.html")
    generate_magazine_html(models, date_str, html_path)
    logger.info(f"🎨 HTML generated: {html_path}")
    
    # Generate index page
    history = []
    for f in sorted(__import__("glob").glob(os.path.join(dist_dir, "digest-*.html"))):
        d = f.stem.replace("digest-", "")
        history.append({"date": d, "path": str(f)})
    
    index_path = os.path.join(dist_dir, "index.html")
    generate_index_page(history, index_path)
    logger.info(f"📑 Index page generated: {index_path}")
    
    # Log digest
    log_digest(date_str, len(models), len(models), html_path)
    
    # Publish to GitHub
    success = publish_to_github(date_str, html_path)
    
    if success:
        logger.info(f"🚀 PUBLISHED: https://suifei.github.io/ai-daily-gguf-digest/digest-{date_str}.html")
    else:
        logger.error("❌ Failed to publish to GitHub")
    
    return success


def cmd_full(args):
    """Run the full pipeline: scan → approve → publish."""
    logger.info("=" * 60)
    logger.info("🚀 RUNNING FULL PIPELINE")
    logger.info("=" * 60)
    
    # Initialize database
    init_database()
    
    # Step 1: Scan
    models = cmd_scan(args)
    
    if not models:
        logger.info("No new models. Skipping approval and publish.")
        return
    
    # Step 2: Auto-approve (in production, AI reviews manually)
    logger.info("\n" + "=" * 60)
    logger.info("📝 AUTO-APPROVING ALL MODELS")
    logger.info("=" * 60)
    approved = cmd_approve_all(args)
    
    # Step 3: Publish
    if approved > 0:
        logger.info("\n" + "=" * 60)
        logger.info("📰 PUBLISHING DAILY DIGEST")
        logger.info("=" * 60)
        cmd_publish(args)
    else:
        logger.info("No models approved. Skipping publish.")


def main():
    parser = argparse.ArgumentParser(description="AI日报 GGUF量化模型快报")
    parser.add_argument("--scan", action="store_true", help="扫描新模型")
    parser.add_argument("--approve", type=str, metavar="REPO_ID", help="批准单个模型")
    parser.add_argument("--approve-all", action="store_true", help="批准所有待审模型")
    parser.add_argument("--publish", action="store_true", help="生成并发布日报")
    parser.add_argument("--full", action="store_true", help="完整流程：扫描+审核+发布")
    parser.add_argument("--date", type=str, help="指定日期 YYYY-MM-DD")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Ensure database is initialized
    init_database()
    
    if args.scan:
        cmd_scan(args)
    elif args.approve:
        # Load and approve a specific model
        date_str = args.date or datetime.now(timezone.utc).strftime(DATE_FORMAT)
        pending = load_pending_models(date_str)
        for m in pending:
            if m["repo_id"] == args.approve:
                cmd_approve(args, m)
                break
        else:
            logger.error(f"Model {args.approve} not found in pending for {date_str}")
    elif args.approve_all:
        cmd_approve_all(args)
    elif args.publish:
        cmd_publish(args)
    elif args.full:
        cmd_full(args)
    else:
        # Default: full pipeline
        cmd_full(args)


if __name__ == "__main__":
    main()
