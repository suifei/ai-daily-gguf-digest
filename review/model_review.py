"""
AI日报 模型审核与数据库管理模块
================================
管理模型的审核流程、去重、增量更新和CSV数据库。
"""

import os
import json
import csv
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ai-daily.review")

DB_PATH = "/tmp/ai-daily-repo/data/database/models.db"
CSV_PATH = "/tmp/ai-daily-repo/data/database/models.csv"
PENDING_DIR = "/tmp/ai-daily-repo/data/pending"
APPROVED_DIR = "/tmp/ai-daily-repo/data/approved"


def init_database():
    """Initialize SQLite database for model tracking."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Models table: tracks all known models
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            repo_id TEXT PRIMARY KEY,
            model_name TEXT,
            author TEXT,
            description TEXT,
            tags TEXT,
            pipeline_tag TEXT,
            library_name TEXT,
            model_family TEXT,
            downloads INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            trending_score REAL DEFAULT 0,
            hf_url TEXT,
            first_seen TEXT,
            last_updated TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    # GGUF variants table: each quantization variant is a row
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gguf_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            filename TEXT NOT NULL,
            quantization TEXT NOT NULL,
            size_bytes INTEGER,
            size_human TEXT,
            download_url TEXT,
            browser_url TEXT,
            FOREIGN KEY (repo_id) REFERENCES models(repo_id)
        )
    """)
    
    # Daily digest log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS digest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            model_count INTEGER,
            new_count INTEGER,
            updated_count INTEGER,
            html_path TEXT,
            published BOOLEAN DEFAULT FALSE,
            created_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def load_pending_models(date_str: str) -> list[dict]:
    """Load pending models from JSON file for a given date."""
    pending_file = Path(PENDING_DIR) / f"{date_str}_models.json"
    if not pending_file.exists():
        logger.warning(f"No pending models for {date_str}: {pending_file}")
        return []
    
    with open(pending_file, "r", encoding="utf-8") as f:
        models = json.load(f)
    
    logger.info(f"Loaded {len(models)} pending models for {date_str}")
    return models


def check_duplicate(repo_id: str, quantization: str) -> bool:
    """Check if a model+quant combination already exists in the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM gguf_variants WHERE repo_id = ? AND quantization = ?",
            (repo_id, quantization)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        logger.error(f"Duplicate check error: {e}")
        return False


def upsert_model(model_info: dict) -> dict:
    """
    Insert or update a model in the database.
    
    Args:
        model_info: Model information dict from scraper
    
    Returns:
        Status dict with 'new' or 'updated' count
    """
    repo_id = model_info["repo_id"]
    now = datetime.now(timezone.utc).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tags_json = json.dumps(model_info.get("tags", []))
    
    # Upsert main model record
    cursor.execute("""
        INSERT INTO models (
            repo_id, model_name, author, description, tags,
            pipeline_tag, library_name, model_family,
            downloads, likes, trending_score, hf_url,
            first_seen, last_updated, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_id) DO UPDATE SET
            model_name = excluded.model_name,
            author = excluded.author,
            description = excluded.description,
            tags = excluded.tags,
            pipeline_tag = excluded.pipeline_tag,
            library_name = excluded.library_name,
            model_family = excluded.model_family,
            downloads = excluded.downloads,
            likes = excluded.likes,
            trending_score = excluded.trending_score,
            hf_url = excluded.hf_url,
            last_updated = excluded.last_updated,
            status = excluded.status
    """, (
        repo_id,
        model_info.get("model_name", ""),
        model_info.get("author", ""),
        model_info.get("description", ""),
        tags_json,
        model_info.get("pipeline_tag", ""),
        model_info.get("library_name", ""),
        model_info.get("model_family", ""),
        model_info.get("downloads", 0),
        model_info.get("likes", 0),
        model_info.get("trending_score", 0),
        model_info.get("hf_url", ""),
        now,
        now,
        "approved",
    ))
    
    # Upsert GGUF variants
    new_count = 0
    for gguf in model_info.get("gguf_files", []):
        quant = gguf.get("quantization", "Unknown")
        
        cursor.execute("""
            INSERT INTO gguf_variants (
                repo_id, model_name, filename, quantization,
                size_bytes, size_human, download_url, browser_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
        """, (
            repo_id,
            model_info.get("model_name", ""),
            gguf.get("filename", ""),
            quant,
            gguf.get("size_bytes", 0),
            gguf.get("size_human", ""),
            gguf.get("download_url", ""),
            gguf.get("browser_url", ""),
        ))
        
        if cursor.rowcount > 0:
            new_count += 1
    
    conn.commit()
    conn.close()
    
    return {"new_variants": new_count}


def approve_model(model_info: dict, date_str: str) -> str:
    """
    Approve a model and save to approved directory.
    
    Args:
        model_info: Model information dict
        date_str: Date string YYYY-MM-DD
    
    Returns:
        Path to saved approved model file
    """
    os.makedirs(APPROVED_DIR, exist_ok=True)
    
    # Add approval metadata
    model_info["approved_at"] = datetime.now(timezone.utc).isoformat()
    model_info["approved_date"] = date_str
    
    output_file = os.path.join(APPROVED_DIR, f"{model_info['repo_id'].replace('/', '_')}_{date_str}.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(model_info, f, indent=2, ensure_ascii=False)
    
    # Also upsert to database
    upsert_model(model_info)
    
    logger.info(f"Approved: {model_info['repo_id']} -> {output_file}")
    return output_file


def get_approved_models_for_date(date_str: str) -> list[dict]:
    """Get all approved models for a specific date from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.*, 
               GROUP_CONCAT(gv.quantization || '(' || gv.size_human || ')', ', ') as quant_summary
        FROM models m
        LEFT JOIN gguf_variants gv ON m.repo_id = gv.repo_id
        WHERE m.last_updated LIKE ?
        GROUP BY m.repo_id
        ORDER BY m.likes DESC
    """, (f"%{date_str}%",))
    
    models = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return models


def export_csv(date_str: str, output_path: str | None = None) -> str:
    """Export approved models to CSV."""
    if output_path is None:
        output_path = CSV_PATH
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    models = get_approved_models_for_date(date_str)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Date", "Repo ID", "Model Name", "Author", "Description",
            "Quantizations", "Size", "Downloads", "Likes",
            "HF URL", "Scraped At"
        ])
        
        for model in models:
            writer.writerow([
                date_str,
                model["repo_id"],
                model["model_name"],
                model["author"],
                model["description"][:200] if model["description"] else "",
                model.get("quant_summary", ""),
                "",  # Size varies per variant
                model["downloads"],
                model["likes"],
                model["hf_url"],
                model.get("last_updated", ""),
            ])
    
    logger.info(f"Exported {len(models)} models to CSV: {output_path}")
    return output_path


def log_digest(date_str: str, model_count: int, new_count: int, html_path: str):
    """Log a daily digest entry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO digest_log (date, model_count, new_count, html_path, published, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (date_str, model_count, new_count, html_path, True, datetime.now(timezone.utc).isoformat()))
    
    conn.commit()
    conn.close()
    logger.info(f"Digest logged: {date_str} ({model_count} models)")


def get_digest_history() -> list[dict]:
    """Get history of all published digests."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM digest_log 
        WHERE published = 1 
        ORDER BY date DESC
    """)
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_database()
    print("Database initialized successfully.")
    print(f"DB path: {DB_PATH}")
    
    # Show history
    history = get_digest_history()
    print(f"\nDigest history: {len(history)} entries")
