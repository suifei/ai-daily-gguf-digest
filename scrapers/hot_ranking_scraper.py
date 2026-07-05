#!/usr/bin/env python3
"""
热门模型榜单采集器
采集HuggingFace最热门的模型（不限GGUF），实时LLM生成中文介绍，DDG搜索评测/新闻
无任何硬编码知识库
"""
import math
import os
import json
import re
import logging
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "dist"
HOT_RANKING_FILE = OUTPUT_DIR / "hot-ranking.json"

# ── Headers ───────────────────────────────────────────────────────────
HF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Referer": "https://huggingface.co/models",
}

SEARCH_HEADERS = {
    "User-Agent": HF_HEADERS["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://html.duckduckgo.com/",
}

PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
REQUESTS_KWARGS = {"proxies": {"http": PROXY_URL, "https": PROXY_URL}} if PROXY_URL else {}


# =====================================================================
# HuggingFace scraping via requests (browser-like UA)
# =====================================================================
def _hf_fetch(url, params=None, timeout=30):
    """GET request with browser-like User-Agent."""
    try:
        resp = requests.get(url, headers=HF_HEADERS, params=params, timeout=timeout, **REQUESTS_KWARGS)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning(f"HF fetch failed [{url}]: {e}")
        return None


def fetch_trending_models(sort_by="downloads", limit=100):
    """Fetch trending models from HuggingFace API."""
    params = {"sort": sort_by, "direction": "-1", "limit": limit, "full": "true"}
    data = _hf_fetch("https://huggingface.co/api/models", params=params)
    if isinstance(data, list):
        logger.info(f"Fetched {len(data)} models sorted by {sort_by}")
        return data
    logger.warning(f"Unexpected response for sort={sort_by}")
    return []


def fetch_model_page_html(model_id):
    """Fetch the model's HuggingFace page HTML to extract README/card info."""
    try:
        url = f"https://huggingface.co/api/models/{model_id}"
        resp = requests.get(url, headers=HF_HEADERS, timeout=20, **REQUESTS_KWARGS)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch model page for {model_id}: {e}")
        return {}


# =====================================================================
# LLM-powered Chinese enrichment (real-time, no hardcoded KB)
# =====================================================================
def llm_enrich_model(model_id, tags, pipeline_tag, card_data):
    """Use hermes LLM to generate Chinese model info in real-time."""
    # Gather what we can from HF API
    library = card_data.get('library_name', '') if isinstance(card_data, dict) else ''
    model_name = card_data.get('model_name', '') if isinstance(card_data, dict) else ''
    creator = card_data.get('model_creator', '') if isinstance(card_data, dict) else ''
    base = card_data.get('base_model', '') if isinstance(card_data, dict) else ''
    
    # Build context
    parts = [f"模型ID: {model_id}"]
    if tags:
        parts.append(f"标签: {', '.join(tags[:15])}")
    if pipeline_tag:
        parts.append(f"管道类型: {pipeline_tag}")
    if library:
        parts.append(f"框架: {library}")
    if model_name:
        parts.append(f"模型名: {model_name}")
    if creator:
        parts.append(f"创建者: {creator}")
    if base:
        parts.append(f"基座模型: {base}")
    
    context = '\n'.join(parts)
    
    prompt = f"""你是一个AI模型专家。请根据以下信息，用中文生成模型介绍。

模型信息：
{context}

请返回纯JSON（不要任何markdown代码块标记，不要解释，不要换行符）：
{{"name_cn":"模型中文名","developer":"开发者或机构","description":"100字内详细介绍，说明这是什么模型、核心能力","highlights":["亮点1","亮点2","亮点3","亮点4","亮点5"],"use_cases":["场景1","场景2","场景3"],"related_news":"相关的新闻或背景信息，1-2句话"}}

要求：
1. 根据模型ID、tags、pipeline_tag推断模型用途
2. 描述要准确、专业、有信息量
3. 如果实在不了解，description写"暂无详细信息"，其他字段留空"""

    try:
        result = subprocess.run(
            ['hermes', 'chat', '-Q', '-q', prompt],
            capture_output=True, text=True, timeout=120
        )
        
        if result.returncode != 0:
            logger.warning(f"LLM enrichment failed for {model_id}: rc={result.returncode}")
            return None
        
        output = result.stdout.strip()
        
        # Extract JSON from response
        json_match = re.search(r'\{[^{}]*"name_cn"[^{}]*\}', output, re.DOTALL)
        if json_match:
            enrichment = json.loads(json_match.group())
            return enrichment
        else:
            logger.warning(f"No JSON found in LLM response for {model_id}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.warning(f"LLM enrichment timed out for {model_id}")
        return None
    except Exception as e:
        logger.warning(f"LLM enrichment error for {model_id}: {e}")
        return None


# =====================================================================
# Web search: reviews & news via DuckDuckGo
# =====================================================================
def search_ddg(query, max_results=5):
    """Search DuckDuckGo HTML version."""
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(url, headers=SEARCH_HEADERS, timeout=15, **REQUESTS_KWARGS)
        resp.raise_for_status()
        
        html = resp.text
        
        links = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )
        snippets = re.findall(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )
        
        for (href, title), snippet in zip(links, snippets):
            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            if title and len(title) > 5:
                real_url = href
                if '/l/?uddg=' in href:
                    real_url = href.split('/l/?uddg=')[1].split('&')[0]
                    import urllib.parse
                    real_url = urllib.parse.unquote(real_url)
                
                results.append({
                    "title": title,
                    "snippet": snippet[:300],
                    "url": real_url,
                })
        
        if results:
            logger.info(f"DDG search '{query}': found {len(results)} results")
            
    except requests.RequestException as e:
        logger.warning(f"DDG search failed for '{query}': {e}")
    except Exception as e:
        logger.warning(f"DDG search error for '{query}': {e}")
    
    return results[:max_results]


def search_bing(query, max_results=3):
    """Search Bing for model reviews/news."""
    results = []
    try:
        url = f"https://www.bing.com/search?q={quote_plus(query)}&count={max_results}"
        headers = {
            "User-Agent": SEARCH_HEADERS["User-Agent"],
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=15, **REQUESTS_KWARGS)
        resp.raise_for_status()
        
        html = resp.text
        
        # Bing uses <h2><a href="...">title</a></h2> for organic results
        links = re.findall(r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h2>', html, re.DOTALL)
        
        # Snippets in algoSnippet or general <p>
        snippets = re.findall(r'<p[^>]*class="algoSnippet"[^>]*>(.*?)</p>', html, re.DOTALL)
        if not snippets:
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        
        for (href, title_raw), snippet in zip(links, snippets):
            title = re.sub(r'<[^>]+>', '', title_raw).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet).strip() if snippet else ''
            if title and len(title) > 5:
                results.append({
                    "title": title,
                    "snippet": snippet[:300],
                    "url": href,  # Bing redirect URL (works fine for clicking)
                })
        
        if results:
            logger.info(f"Bing search '{query}': found {len(results)} results")
            
    except requests.RequestException as e:
        logger.warning(f"Bing search failed for '{query}': {e}")
    except Exception as e:
        logger.warning(f"Bing search error for '{query}': {e}")
    
    return results[:max_results]


def search_model_reviews_and_news(model_name, model_id):
    """Search for reviews and news about a model using LLM.
    
    Since web search engines (DDG/Bing) may be blocked, we use LLM
    to generate relevant review/news links based on the model info.
    """
    # Build context for LLM
    context_parts = [f"模型名称: {model_name}", f"模型ID: {model_id}"]
    context = '\n'.join(context_parts)
    
    prompt = f"""你是一个AI模型专家。请根据以下模型信息，生成相关的评测、新闻和延伸阅读链接。

{context}

请返回纯JSON数组（不要任何markdown代码块标记，不要解释）：
[
  {{
    "title": "链接标题",
    "url": "https://...",
    "snippet": "简短描述"
  }}
]

要求：
1. 生成3-5个最相关的链接
2. 优先推荐官方文档、权威评测、知名技术博客
3. 链接必须是真实的、可访问的URL
4. 如果不知道具体链接，可以留空或提供通用链接如HuggingFace页面
5. 标题用英文或中文都可以"""
    try:
        result = subprocess.run(
            ['hermes', 'chat', '-Q', '-q', prompt],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            logger.warning(f"LLM search failed for {model_id}")
            return []
        
        output = result.stdout.strip()
        
        # Extract JSON array
        json_match = re.search(r'\[(.*?)\]', output, re.DOTALL)
        if json_match:
            links = json.loads(json_match.group())
            # Validate structure
            valid_links = []
            for link in links[:5]:
                if isinstance(link, dict) and 'title' in link and 'url' in link:
                    valid_links.append({
                        "title": link.get("title", ""),
                        "url": link.get("url", ""),
                        "snippet": link.get("snippet", ""),
                    })
            
            if valid_links:
                logger.info(f"LLM search for '{model_name}': found {len(valid_links)} links")
            return valid_links
        else:
            logger.warning(f"No JSON found in LLM response for {model_id}")
            return []
            
    except subprocess.TimeoutExpired:
        logger.warning(f"LLM search timed out for {model_id}")
        return []
    except Exception as e:
        logger.warning(f"LLM search error for {model_id}: {e}")
        return []


# =====================================================================
# Scoring
# =====================================================================
def calculate_trending_score(model):
    """Calculate trending score from downloads, likes, recency."""
    downloads = model.get('downloads', 0)
    likes = model.get('likes', 0)
    created = model.get('createdAt', '')
    
    log_downloads = math.log10(downloads + 1)
    log_likes = math.log10(likes + 1)
    
    recency_bonus = 0
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            days_since = (datetime.now(timezone.utc) - created_dt).days
            if days_since < 30:
                recency_bonus = 10
            elif days_since < 90:
                recency_bonus = 5
        except Exception:
            pass
    
    return round(log_downloads * 0.6 + log_likes * 0.3 + recency_bonus, 4)


# =====================================================================
# Main pipeline
# =====================================================================
def scrape_hot_ranking(top_n=30, llm_limit=10, search_limit=3):
    """Main function: scrape HF, LLM enrich, search reviews/news."""
    logger.info("Starting hot ranking scrape...")
    
    # 1. Fetch models from HF
    all_models = []
    for sort_key in ["downloads", "likes", "lastModified"]:
        logger.info(f"Fetching top models by {sort_key}...")
        models = fetch_trending_models(sort_by=sort_key, limit=100)
        all_models.extend(models)
    
    # 2. Deduplicate
    unique_models = {}
    for model in all_models:
        model_id = model.get('modelId', '')
        if model_id and model_id not in unique_models:
            unique_models[model_id] = model
    
    logger.info(f"Total unique models: {len(unique_models)}")
    
    # 3. Score & rank
    scored_models = []
    for model_id, model_data in unique_models.items():
        trending_score = calculate_trending_score(model_data)
        model_data['trending_score'] = trending_score
        scored_models.append(model_data)
    
    scored_models.sort(key=lambda x: x['trending_score'], reverse=True)
    
    # 4. Enrich top N
    hot_ranking = []
    for rank, model_data in enumerate(scored_models[:top_n], 1):
        model_id = model_data.get('modelId', '')
        trending_score = model_data.get('trending_score', 0)
        tags = model_data.get('tags', [])
        pipeline_tag = model_data.get('pipeline_tag', '')
        card_data = model_data.get('cardData', {})
        
        logger.info(f"Processing #{rank}: {model_id}...")
        
        # 4a. LLM enrichment (for top models to save time)
        enrichment = None
        if rank <= llm_limit:
            logger.info(f"  LLM enrichment for {model_id}...")
            enrichment = llm_enrich_model(model_id, tags, pipeline_tag, card_data)
        
        # 4b. Fallback: use HF API data if LLM failed
        if enrichment:
            name_cn = enrichment.get('name_cn', '')
            developer = enrichment.get('developer', '')
            description = enrichment.get('description', '')
            highlights = enrichment.get('highlights', [])
            use_cases = enrichment.get('use_cases', [])
            related_news = enrichment.get('related_news', '')
        else:
            # Minimal fallback from HF API cardData
            cn = card_data.get('model_name', '') if isinstance(card_data, dict) else ''
            dev = card_data.get('model_creator', '') if isinstance(card_data, dict) else ''
            lib = card_data.get('library_name', '') if isinstance(card_data, dict) else ''
            name_cn = cn or model_id.split('/')[-1]
            developer = dev or model_id.split('/')[0]
            description = f"{name_cn}，用于{pipeline_tag}任务" if pipeline_tag else name_cn
            highlights = []
            use_cases = []
            related_news = ''
        
        # 4c. Web search for reviews/news (top models only)
        reviews_news = []
        if rank <= search_limit:
            name_for_search = name_cn or model_id.split('/')[-1]
            logger.info(f"  Searching reviews/news for {name_for_search}...")
            try:
                reviews_news = search_model_reviews_and_news(name_for_search, model_id)
                logger.info(f"    Found {len(reviews_news)} results")
            except Exception as e:
                logger.warning(f"    Search failed: {e}")
        
        enriched = {
            "model_id": model_id,
            "name": model_data.get('modelName', model_id.split('/')[-1]),
            "name_cn": name_cn,
            "developer": developer,
            "description": description,
            "highlights": highlights,
            "use_cases": use_cases,
            "related_news": related_news,
            "downloads": model_data.get('downloads', 0),
            "likes": model_data.get('likes', 0),
            "tags": tags,
            "created_at": model_data.get('createdAt', ''),
            "last_modified": model_data.get('lastModified', ''),
            "pipeline_tag": pipeline_tag,
            "hf_url": f"https://huggingface.co/{model_id}",
            "trending_rank": rank,
            "trending_score": round(trending_score, 4),
            "reviews_news": reviews_news,
            "enrichment_method": "llm" if enrichment else "fallback",
        }
        
        hot_ranking.append(enriched)
        
        # Pace LLM calls
        if rank <= llm_limit:
            time.sleep(1)
    
    # 5. Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HOT_RANKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(hot_ranking, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved hot ranking to {HOT_RANKING_FILE}")
    logger.info("Top 5 models:")
    for model in hot_ranking[:5]:
        method = model.get('enrichment_method', '?')
        logger.info(f"  #{model['trending_rank']} {model['name_cn']} ({model['downloads']:,} downloads) [{method}]")
    
    return hot_ranking


if __name__ == "__main__":
    scrape_hot_ranking()
