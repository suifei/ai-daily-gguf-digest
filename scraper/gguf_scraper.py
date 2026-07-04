"""
AI日报 GGUF 爬虫模块
=====================
从 HuggingFace 搜索最新的 GGUF 量化模型。
支持代理访问，自动解析模型元数据。
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

import requests

logger = logging.getLogger("ai-daily.scraper")

# HuggingFace API endpoints
HF_API_BASE = "https://huggingface.co/api"
HF_MODELS_ENDPOINT = f"{HF_API_BASE}/models"

# Proxy configuration for accessing HuggingFace from China
PROXY_HTTP = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "http://localhost:8080"
PROXY_HTTPS = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "http://localhost:8080"
PROXIES = {
    "http": PROXY_HTTP,
    "https": PROXY_HTTPS,
}

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "AI-Daily-GGUF-Scraper/1.0",
}


def search_gguf_models(
    limit: int = 50,
    sort: str = "lastModified",
    direction: int = -1,
    tags: list[str] | None = None,
    search: str = "",
) -> list[dict]:
    """
    Search HuggingFace for the latest GGUF models.
    
    Args:
        limit: Number of results to return (max 100)
        sort: Sort field - 'lastModified', 'createdAt', 'downloads', 'likes'
        direction: -1 for descending, 1 for ascending
        tags: Filter by tags (e.g., ['gguf', 'text-generation'])
        search: Free-text search query
    
    Returns:
        List of model metadata dictionaries
    """
    params = {
        "sort": sort,
        "direction": direction,
        "limit": min(limit, 100),
        "full": "false",
        "config": "false",
    }
    
    if tags:
        params["tags"] = tags
    
    if search:
        params["search"] = search
    
    try:
        logger.info(f"Searching HuggingFace for GGUF models: limit={params['limit']}, sort={sort}")
        resp = requests.get(HF_MODELS_ENDPOINT, params=params, headers=HEADERS, proxies=PROXIES, timeout=30)
        resp.raise_for_status()
        models = resp.json()
        logger.info(f"Found {len(models)} models")
        return models
    except requests.exceptions.ProxyError as e:
        logger.warning(f"Proxy error, retrying without proxy: {e}")
        try:
            resp = requests.get(HF_MODELS_ENDPOINT, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            models = resp.json()
            logger.info(f"Found {len(models)} models (no proxy)")
            return models
        except Exception as e2:
            logger.error(f"Failed without proxy too: {e2}")
            raise
    except Exception as e:
        logger.error(f"Error searching models: {e}")
        raise


def get_model_details(repo_id: str) -> dict:
    """
    Get detailed information for a specific model.
    
    Args:
        repo_id: HuggingFace model repo ID (e.g., 'meta-llama/Llama-3.1-8B')
    
    Returns:
        Full model metadata dictionary
    """
    url = f"{HF_API_BASE}/models/{repo_id}"
    try:
        resp = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Error fetching details for {repo_id}: {e}")
        return {}


def get_model_siblings(repo_id: str) -> list[dict]:
    """
    Get the list of files (siblings) for a model repo.
    
    Args:
        repo_id: HuggingFace model repo ID
    
    Returns:
        List of file metadata dictionaries
    """
    url = f"{HF_API_BASE}/models/{repo_id}/tree/main"
    try:
        resp = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Error fetching siblings for {repo_id}: {e}")
        return []


def parse_gguf_files(siblings: list[dict]) -> list[dict]:
    """
    Parse GGUF variant files from model siblings.
    
    Args:
        siblings: List of file metadata from HuggingFace
    
    Returns:
        List of GGUF file info dicts with size, quantization level, download URL
    """
    gguf_files = []
    for sibling in siblings:
        filename = sibling.get("path", "")
        if not filename.lower().endswith(".gguf"):
            continue
        
        size_bytes = sibling.get("size", 0)
        rfile_url = sibling.get("rurl", "")
        
        # Determine quantization level from filename
        quant = extract_quantization(filename)
        
        gguf_files.append({
            "filename": filename,
            "quantization": quant,
            "size_bytes": size_bytes,
            "size_human": format_size(size_bytes),
            "download_url": rfile_url,
            "browser_url": f"https://huggingface.co/{sibling.get('repo', {}).get('id', '')}/blob/main/{filename}",
        })
    
    return gguf_files


def extract_quantization(filename: str) -> str:
    """
    Extract quantization level from GGUF filename.
    
    Examples:
        model-Q4_K_M.gguf -> Q4_K_M
        model-q8_0.gguf -> q8_0
        model-fp16.gguf -> FP16
    """
    base = os.path.basename(filename).lower()
    
    quant_map = {
        "q2_k": "Q2_K",
        "q3_k_s": "Q3_K_S",
        "q3_k_m": "Q3_K_M",
        "q3_k_l": "Q3_K_L",
        "q4_0": "Q4_0",
        "q4_1": "Q4_1",
        "q4_k_m": "Q4_K_M",
        "q4_k_s": "Q4_K_S",
        "q5_0": "Q5_0",
        "q5_1": "Q5_1",
        "q5_k_m": "Q5_K_M",
        "q5_k_s": "Q5_K_S",
        "q6_k": "Q6_K",
        "q8_0": "Q8_0",
        "q8_1": "Q8_1",
        "f16": "FP16",
        "f32": "FP32",
        "bf16": "BF16",
    }
    
    for key, value in quant_map.items():
        if key in base:
            return value
    
    return "Unknown"


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"


import math

def extract_model_info(model: dict) -> dict:
    """
    Extract comprehensive model information from HuggingFace model metadata.
    
    Args:
        model: Raw model dict from HuggingFace API
    
    Returns:
        Structured model info dict
    """
    repo_id = model.get("id", "")
    tags = model.get("tags", [])
    pipeline_tag = model.get("pipeline_tag", "")
    library_name = model.get("library_name", "")
    
    # Get card data / model index for more details
    card_data = model.get("cardData", {}) or {}
    model_index = card_data.get("model-index", [{}])[0] if card_data.get("model-index") else {}
    
    model_name = model.get("modelId", model.get("id", "").split("/")[-1])
    author = model.get("author", "")
    
    # Parse model family from tags
    model_family = ""
    for tag in tags:
        if tag.startswith("base_model:") or tag.startswith("derived_model:"):
            model_family = tag.split(":")[-1]
            break
    
    # Extract key metrics
    downloads = model.get("downloads", 0)
    likes = model.get("likes", 0)
    trending = model.get("trendingScore", 0)
    
    # Last modified time
    last_modified = model.get("lastModified", "")
    created_at = model.get("created_at", "")
    
    # Description
    description = model.get("description", "") or card_data.get("model_description", "") or ""
    
    # HuggingFace URL
    hf_url = f"https://huggingface.co/{repo_id}"
    
    return {
        "repo_id": repo_id,
        "model_name": model_name,
        "author": author,
        "tags": tags,
        "pipeline_tag": pipeline_tag,
        "library_name": library_name,
        "model_family": model_family,
        "downloads": downloads,
        "likes": likes,
        "trending_score": trending,
        "last_modified": last_modified,
        "created_at": created_at,
        "description": description[:500] if description else "",  # Truncate for storage
        "hf_url": hf_url,
        "card_data": card_data,
    }


def scrape_today_models(date_str: str | None = None) -> list[dict]:
    """
    Main scraping function: find all new GGUF models.
    
    Args:
        date_str: Date filter YYYY-MM-DD. If None, uses today.
    
    Returns:
        List of model info dicts with GGUF file details
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    logger.info(f"=== Scraping GGUF models for {date_str} ===")
    
    # Step 1: Search for GGUF-tagged models, sorted by last modified
    models = search_gguf_models(
        limit=100,
        sort="lastModified",
        direction=-1,
        tags=["gguf"],
    )
    
    results = []
    today_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    yesterday_dt = today_dt.replace(day=max(1, today_dt.day - 1))
    
    for model in models:
        last_mod = model.get("lastModified", "")
        # Filter: models from today or yesterday (to catch edge cases)
        if last_mod:
            mod_dt = datetime.fromisoformat(last_mod.replace("Z", "+00:00"))
            if mod_dt.date() > today_dt.date():
                continue
            if mod_dt.date() < yesterday_dt.date():
                continue
        
        model_info = extract_model_info(model)
        repo_id = model_info["repo_id"]
        
        # Step 2: Get GGUF files for this model
        siblings = get_model_siblings(repo_id)
        gguf_files = parse_gguf_files(siblings)
        
        if not gguf_files:
            continue  # No GGUF files found
        
        model_info["gguf_files"] = gguf_files
        model_info["scraped_at"] = datetime.now(timezone.utc).isoformat()
        model_info["scrape_date"] = date_str
        
        results.append(model_info)
        logger.info(f"  Found: {repo_id} ({len(gguf_files)} GGUF variants)")
    
    logger.info(f"Total GGUF models found: {len(results)}")
    return results


def save_pending_models(models: list[dict], date_str: str) -> str:
    """
    Save scraped models to pending review directory.
    
    Args:
        models: List of model info dicts
        date_str: Date string YYYY-MM-DD
    
    Returns:
        Path to the saved JSON file
    """
    pending_dir = Path("/tmp/ai-daily-repo/data/pending")
    pending_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = pending_dir / f"{date_str}_models.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(models)} models to {output_file}")
    return str(output_file)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    models = scrape_today_models()
    if models:
        output = save_pending_models(models, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        print(f"\nModels saved to: {output}")
        print(f"Total models: {len(models)}")
    else:
        print("No new GGUF models found.")
