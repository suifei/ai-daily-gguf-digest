#!/usr/bin/env python3
"""
热门模型榜单采集器
采集HuggingFace最热门的模型（不限GGUF），中文化展示
"""
import math
import os
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Proxy configuration
PROXY_URL = "http://localhost:8080"
os.environ["HTTPS_PROXY"] = PROXY_URL
os.environ["HTTP_PROXY"] = PROXY_URL

OUTPUT_DIR = Path(__file__).parent.parent / "dist"
HOT_RANKING_FILE = OUTPUT_DIR / "hot-ranking.json"

# 热门模型知识库 - 提供详细的中文介绍
MODEL_KNOWLEDGE_BASE = {
    "Qwen/Qwen3-0.6B": {
        "name_cn": "Qwen3-0.6B",
        "family": "Qwen3",
        "developer": "阿里巴巴通义实验室",
        "description": "Qwen3系列的超轻量级模型，仅0.6B参数，适合边缘设备和移动端部署。在保持良好性能的同时，实现了极高的推理速度。",
        "highlights": [
            "仅0.6B参数，极致轻量",
            "适合边缘设备和IoT场景",
            "推理速度极快，延迟极低",
            "多语言支持（中、英、日、韩等）",
            "64K超长上下文窗口"
        ],
        "use_cases": ["端侧推理", "移动应用", "IoT设备", "实时翻译"],
        "related_news": "Qwen3系列发布了多个尺寸，覆盖从0.6B到235B的全尺寸范围，是2025年最具影响力的开源模型家族之一。"
    },
    "Qwen/Qwen3-8B": {
        "name_cn": "Qwen3-8B",
        "family": "Qwen3",
        "developer": "阿里巴巴通义实验室",
        "description": "Qwen3系列的8B参数模型，在性能和效率之间取得优秀平衡。支持MoE架构，激活参数仅3.5B，推理成本大幅降低。",
        "highlights": [
            "8B总参数，3.5B激活参数（MoE架构）",
            "64K上下文窗口",
            "多语言能力强（26+语言）",
            "代码生成和数学推理出色",
            "推理成本降低60%"
        ],
        "use_cases": ["通用对话", "代码生成", "多语言翻译", "文档分析"],
        "related_news": "Qwen3-8B采用混合注意力机制和MoE架构，在MMLU、GSM8K等基准测试中超越多数同尺寸模型。"
    },
    "facebook/opt-125m": {
        "name_cn": "OPT-125M",
        "family": "OPT",
        "developer": "Meta",
        "description": "Meta开源的OPT系列中最小规模的模型，125M参数。作为文本生成模型的基线参考，广泛用于研究和教育场景。",
        "highlights": [
            "125M参数，极致小巧",
            " decoder-only架构",
            "广泛用于NLP教学研究",
            "支持多种语言",
            "可作为微调基线模型"
        ],
        "use_cases": ["教学演示", "研究基线", "文本分类", "简单生成"],
        "related_news": "OPT系列是Meta在2022年推出的开源 decoder-only 语言模型家族，推动了开源LLM的发展。"
    }
}

def fetch_trending_models(sort_by="downloads", limit=50, pipeline_tag=None):
    """Fetch trending models from HuggingFace API via curl with proxy."""
    params = f"sort={sort_by}&direction=-1&limit={limit}&full=true"
    if pipeline_tag:
        params += f"&pipeline_tag={pipeline_tag}"
    
    try:
        result = subprocess.run(
            ['curl', '-x', PROXY_URL, '-s', 
             f'https://huggingface.co/api/models?{params}'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"curl failed: {result.stderr[:200]}")
            return []
        
        models = json.loads(result.stdout)
        logger.info(f"Fetched {len(models)} models sorted by {sort_by}")
        return models
        
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return []

def enrich_model_with_knowledge(model_data: dict) -> dict:
    """Enrich model data with Chinese knowledge base."""
    model_id = model_data.get('modelId', '')
    knowledge = MODEL_KNOWLEDGE_BASE.get(model_id, {})
    
    enriched = {
        "model_id": model_id,
        "name": model_data.get('modelName', model_id.split('/')[-1]),
        "name_cn": knowledge.get('name_cn', model_id.split('/')[-1]),
        "family": knowledge.get('family', ''),
        "developer": knowledge.get('developer', ''),
        "description": knowledge.get('description', ''),
        "highlights": knowledge.get('highlights', []),
        "use_cases": knowledge.get('use_cases', []),
        "related_news": knowledge.get('related_news', ''),
        "downloads": model_data.get('downloads', 0),
        "likes": model_data.get('likes', 0),
        "tags": model_data.get('tags', []),
        "created_at": model_data.get('createdAt', ''),
        "last_modified": model_data.get('lastModified', ''),
        "pipeline_tag": model_data.get('pipeline_tag', ''),
        "hf_url": f"https://huggingface.co/{model_id}",
        "trending_rank": 0,  # Will be set later
        "trending_score": 0,  # Combined score for ranking
    }
    
    return enriched

def calculate_trending_score(model: dict) -> float:
    """Calculate a trending score based on downloads, likes, and recency."""
    downloads = model.get('downloads', 0)
    likes = model.get('likes', 0)
    created = model.get('createdAt', '')
    
    # Normalize downloads (log scale)
    log_downloads = math.log10(downloads + 1)
    
    # Normalize likes (log scale)
    log_likes = math.log10(likes + 1)
    
    # Recency bonus (models created/updated recently get bonus)
    recency_bonus = 0
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            days_since = (datetime.now(timezone.utc) - created_dt).days
            if days_since < 30:
                recency_bonus = 10
            elif days_since < 90:
                recency_bonus = 5
        except:
            pass
    
    # Trending score = weighted combination
    trending_score = log_downloads * 0.6 + log_likes * 0.3 + recency_bonus
    
    return round(trending_score, 4)

def get_top_models_by_metric(models: list, metric="downloads", top_n=30):
    """Get top N models by a specific metric."""
    sorted_models = sorted(models, key=lambda x: x.get(metric, 0), reverse=True)
    return sorted_models[:top_n]

def scrape_hot_ranking():
    """Main function to scrape and generate hot ranking."""
    logger.info("Starting hot ranking scrape...")
    
    # Fetch models sorted by different metrics
    all_models = []
    
    # Get top models by downloads
    logger.info("Fetching top models by downloads...")
    download_models = fetch_trending_models(sort_by="downloads", limit=100)
    all_models.extend(download_models)
    
    # Get top models by likes
    logger.info("Fetching top models by likes...")
    like_models = fetch_trending_models(sort_by="likes", limit=100)
    all_models.extend(like_models)
    
    # Get top models by recent downloads
    logger.info("Fetching top models by recent downloads...")
    recent_models = fetch_trending_models(sort_by="lastModified", limit=100)
    all_models.extend(recent_models)
    
    # Deduplicate by model ID
    unique_models = {}
    for model in all_models:
        model_id = model.get('modelId', '')
        if model_id and model_id not in unique_models:
            unique_models[model_id] = model
    
    logger.info(f"Total unique models: {len(unique_models)}")
    
    # Calculate trending scores and sort
    scored_models = []
    for model_id, model_data in unique_models.items():
        trending_score = calculate_trending_score(model_data)
        model_data['trending_score'] = trending_score
        scored_models.append(model_data)
    
    # Sort by trending score
    scored_models.sort(key=lambda x: x['trending_score'], reverse=True)
    
    # Enrich with knowledge base
    hot_ranking = []
    for rank, model_data in enumerate(scored_models[:30], 1):
        trending_score = model_data.get('trending_score', 0)
        enriched = enrich_model_with_knowledge(model_data)
        enriched['trending_rank'] = rank
        enriched['trending_score'] = round(trending_score, 4)
        hot_ranking.append(enriched)
    
    # Save to file
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HOT_RANKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(hot_ranking, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved hot ranking to {HOT_RANKING_FILE}")
    logger.info(f"Top 5 models:")
    for model in hot_ranking[:5]:
        logger.info(f"  #{model['trending_rank']} {model['name_cn']} ({model['downloads']:,} downloads)")
    
    return hot_ranking

if __name__ == "__main__":
    scrape_hot_ranking()
