#!/usr/bin/env python3
"""
AI日报 自动管道 — 完整编排脚本
===============================
1. 扫描 HuggingFace 最新 GGUF 模型
2. 自动生成中文摘要和风险评估
3. 自动审核（基于启发式规则）
4. 生成电子杂志 HTML
5. 推送到 GitHub Pages
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/tmp/ai-daily-repo")

from scraper.gguf_scraper import scrape_today_models, save_pending_models
from review.model_review import (
    init_database, approve_model, get_approved_models_for_date,
    export_csv, log_digest, check_duplicate, upsert_model
)
from review.chinese_summary import generate_chinese_summary
from renderer.magazine_renderer import generate_magazine_html, generate_index_page
from publisher.publisher import publish_to_github

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-daily.auto")

DATE_FORMAT = "%Y-%m-%d"


def auto_review_model(model_info: dict) -> dict:
    tags = model_info.get("tags", [])
    downloads = model_info.get("downloads", 0)
    likes = model_info.get("likes", 0)
    trending = model_info.get("trending_score", 0)

    risk_level = "low"
    notes = ""

    risky_tags = ["uncensored", "abliterated", "heretic", "nsfw", "adult"]
    for tag in tags:
        if tag.lower() in risky_tags:
            risk_level = "high"
            notes = "模型包含不安全内容或去对齐标记，建议高级用户使用"
            break

    medium_tags = ["roleplay", "creative-writing", "chat"]
    if risk_level == "low":
        for tag in tags:
            if tag.lower() in medium_tags:
                risk_level = "medium"
                notes = "角色扮演/创意写作模型"
                break

    if downloads == 0 and likes == 0 and trending == 0:
        notes = "新模型，尚无社区反馈" if not notes else notes + "，尚无社区反馈"

    chinese_summary = generate_chinese_summary(model_info)

    return {
        "approve": True,
        "chinese_summary": chinese_summary,
        "chinese_description": chinese_summary,
        "risk_level": risk_level,
        "notes": notes or "AI自动审核通过",
    }


def main():
    today = datetime.now(timezone.utc).strftime(DATE_FORMAT)
    logger.info(f"=== AI Daily Pipeline — {today} ===")

    # Step 1: Initialize database
    logger.info("[1/5] Initializing database...")
    init_database()

    # Step 2: Scrape new GGUF models
    logger.info("[2/5] Scraping HuggingFace for latest GGUF models...")
    models = scrape_today_models(today)

    if not models:
        logger.warning("No new GGUF models found for today.")
        # Still generate an empty digest
        models = []
    else:
        logger.info(f"Found {len(models)} new GGUF models.")

    # Step 3: Auto-review and approve
    logger.info("[3/5] Auto-reviewing models...")
    approved_models = []
    review_results = []

    for model_info in models:
        repo_id = model_info["repo_id"]

        # Check duplicate
        for gguf in model_info.get("gguf_files", []):
            if check_duplicate(repo_id, gguf.get("quantization", "")):
                logger.info(f"  Skipping duplicate: {repo_id} ({gguf['quantization']})")
                continue

        # Auto-review
        review = auto_review_model(model_info)
        review_results.append({
            "repo_id": repo_id,
            "approved": review["approve"],
            "risk_level": review["risk_level"],
            "notes": review["notes"],
        })

        if review["approve"]:
            # Add review metadata to model info
            model_info["chinese_summary"] = review["chinese_summary"]
            model_info["chinese_description"] = review["chinese_description"]
            model_info["risk_level"] = review["risk_level"]
            model_info["review_notes"] = review["notes"]

            # Approve and save
            try:
                approve_model(model_info, today)
                upsert_model(model_info)
                approved_models.append(model_info)
                logger.info(f"  Approved: {repo_id} (risk: {review['risk_level']})")
            except Exception as e:
                logger.error(f"  Failed to approve {repo_id}: {e}")

    logger.info(f"Approved {len(approved_models)} models out of {len(models)} found.")

    # Step 4: Generate magazine HTML
    logger.info("[4/5] Generating magazine HTML...")
    dist_dir = Path("/tmp/ai-daily-repo/dist")
    dist_dir.mkdir(parents=True, exist_ok=True)

    html_path = dist_dir / f"digest-{today}.html"
    if approved_models:
        generate_magazine_html(approved_models, today, str(html_path))
    else:
        # Generate empty-state HTML
        generate_magazine_html([], today, str(html_path))

    logger.info(f"Generated: {html_path}")

    # Export CSV
    export_csv(today)

    # Update index page
    history = []
    for f in sorted(dist_dir.glob("digest-*.html")):
        d = f.stem.replace("digest-", "")
        history.append({"date": d, "path": str(f)})
    generate_index_page(history, str(dist_dir / "index.html"))

    # Log digest
    log_digest(today, len(approved_models), len(approved_models), str(html_path))

    # Step 5: Publish to GitHub Pages
    logger.info("[5/5] Publishing to GitHub Pages...")
    success = publish_to_github(today, str(html_path))

    if success:
        logger.info(f"✅ Published! View at: https://suifei.github.io/ai-daily-gguf-digest/digest-{today}.html")
    else:
        logger.error(f"❌ Failed to publish to GitHub Pages.")

    # Summary
    logger.info("=" * 50)
    logger.info(f"PIPELINE SUMMARY — {today}")
    logger.info(f"  Models scraped:      {len(models)}")
    logger.info(f"  Models approved:     {len(approved_models)}")
    logger.info(f"  Risk levels:         "
                f"high={sum(1 for r in review_results if r['risk_level']=='high')}, "
                f"medium={sum(1 for r in review_results if r['risk_level']=='medium')}, "
                f"low={sum(1 for r in review_results if r['risk_level']=='low')}")
    logger.info(f"  HTML generated:      {html_path}")
    logger.info(f"  GitHub Pages:        {'Published ✅' if success else 'Failed ❌'}")
    logger.info("=" * 50)

    # Print summary to stdout for cron delivery
    print("\n" + "=" * 60)
    print(f"  AI日报自动管道完成 — {today}")
    print("=" * 60)
    print(f"  扫描模型数:   {len(models)}")
    print(f"  审核通过数:   {len(approved_models)}")
    print(f"  高风险:       {sum(1 for r in review_results if r['risk_level']=='high')}")
    print(f"  中风险:       {sum(1 for r in review_results if r['risk_level']=='medium')}")
    print(f"  低风险:       {sum(1 for r in review_results if r['risk_level']=='low')}")
    print(f"  HTML输出:     {html_path}")
    print(f"  GitHub Pages: {'已推送 ✅' if success else '推送失败 ❌'}")
    print("=" * 60)

    if approved_models:
        print("\n审核通过的模型:")
        for m in approved_models:
            risk = m.get("risk_level", "?")
            print(f"  • {m['model_name']} ({m['repo_id']}) — 风险:{risk} — "
                  f"下载:{m.get('downloads',0):,} 点赞:{m.get('likes',0):,}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
