#!/usr/bin/env python3
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
