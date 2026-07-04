"""
AI日报 电子杂志HTML渲染引擎
============================
生成具有翻页效果、目录导航、上一期/下一期的电子杂志风格HTML日报。
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ai-daily.renderer")

OUTPUT_DIR = "/tmp/ai-daily-repo/dist"


def generate_magazine_html(models: list[dict], date_str: str, output_path: str) -> str:
    """
    Generate a magazine-style HTML page for a daily digest.
    
    Args:
        models: List of approved model dicts
        date_str: Date string YYYY-MM-DD
        output_path: Where to save the HTML file
    
    Returns:
        Path to the generated HTML file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Get digest history for prev/next navigation
    history = get_digest_history()
    digest_dates = sorted([h["date"] for h in history if h["date"] != date_str])
    
    current_idx = -1
    for i, d in enumerate(digest_dates):
        if d < date_str:
            current_idx = i
    
    prev_date = digest_dates[current_idx] if current_idx >= 0 else None
    next_date = digest_dates[current_idx + 1] if current_idx + 1 < len(digest_dates) else None
    
    # Build model cards HTML
    model_cards = ""
    for idx, model in enumerate(models):
        model_cards += build_model_card(model, idx, date_str)
    
    # Build TOC entries
    toc_entries = ""
    for idx, model in enumerate(models):
        safe_id = model["repo_id"].replace("/", "-").replace("_", "-").lower()
        toc_entries += f'<a href="#model-{safe_id}" class="toc-link">{model["model_name"]}</a>\n'
    
    title = f"AI日报 GGUF模型快报 {date_str}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Build TOC nav links
    toc_prev = f'<a href="../digest-{prev_date}.html" class="toc-nav-link">← 上一期 ({prev_date})</a>' if prev_date else '<span class="toc-nav-blank">← 更早</span>'
    toc_next = f'<a href="../digest-{next_date}.html" class="toc-nav-link">下一期 ({next_date}) →</a>' if next_date else '<span class="toc-nav-blank">更晚 →</span>'
    
    # Build issue nav links
    issue_prev = f'<a href="../digest-{prev_date}.html" class="issue-link prev-issue">← 上一期: {prev_date}</a>' if prev_date else '<span class="issue-link prev-issue disabled">← 上一期</span>'
    issue_next = f'<a href="../digest-{next_date}.html" class="issue-link next-issue">下一期: {next_date} →</a>' if next_date else '<span class="issue-link next-issue disabled">下一期 →</span>'
    
    # Empty state placeholder
    empty_state = '<div class="empty-state"><h2>📭 今日暂无新模型</h2><p>今天没有发现新的 GGUF 量化模型。</p></div>' if not models else ''
    
    # Count total digests
    total_issues = len(get_digest_history())
    
    html = MAGAZINE_TEMPLATE % (
        title,                          # %s title
        date_str[:4],                   # %s year
        date_str[5:],                   # %s month-day
        len(models),                    # %s model_count
        generated_at,                   # %s generated_at
        date_str,                       # %s nav-date
        toc_entries,                    # %s toc-list
        toc_prev,                       # %s toc-nav-prev
        toc_next,                       # %s toc-nav-next
        issue_prev,                     # %s issue-nav-prev
        total_issues,                   # %s issue-counter
        issue_next,                     # %s issue-nav-next
        model_cards,                    # %s model-cards
        empty_state,                    # %s empty-state
        date_str,                       # %s footer-date
    )
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Generated magazine HTML: {output_path} ({len(models)} models)")
    return output_path


def build_model_card(model: dict, index: int, date_str: str) -> str:
    """Build HTML for a single model card."""
    repo_id = model["repo_id"]
    safe_id = repo_id.replace("/", "-").replace("_", "-").lower()
    author = model.get("author", "")
    description = model.get("description", "")
    downloads = model.get("downloads", 0)
    likes = model.get("likes", 0)
    trending = model.get("trending_score", 0)
    tags = model.get("tags", [])
    pipeline = model.get("pipeline_tag", "")
    
    # Build GGUF variants table
    variants_html = ""
    for gguf in model.get("gguf_files", []):
        variants_html += f"""
        <tr class="variant-row">
            <td class="quant-badge">{gguf['quantization']}</td>
            <td>{gguf['size_human']}</td>
            <td><a href="{gguf['browser_url']}" target="_blank" class="file-link">📄 {gguf['filename']}</a></td>
            <td><a href="{gguf['download_url']}" target="_blank" class="dl-link">⬇️ Download</a></td>
        </tr>"""
    
    # Tags display
    tags_html = ""
    for tag in tags[:8]:
        if tag != "gguf":
            tags_html += f'<span class="tag">{tag}</span>'
    
    return f"""
    <article class="model-page" id="model-{safe_id}">
        <div class="model-header">
            <span class="model-number">{index + 1}</span>
            <h2 class="model-title">{model['model_name']}</h2>
            <p class="model-author">by {author}</p>
        </div>
        
        <div class="model-meta">
            <span class="meta-item">⬇️ {downloads:,} downloads</span>
            <span class="meta-item">❤️ {likes:,} likes</span>
            <span class="meta-item">📈 Trending: {trending:.1f}</span>
            {f'<span class="meta-item">🏷️ {pipeline}</span>' if pipeline else ''}
        </div>
        
        <div class="model-description">
            <p>{description[:300]}{'...' if len(description) > 300 else ''}</p>
        </div>
        
        <div class="model-tags">
            {tags_html}
        </div>
        
        <div class="variants-section">
            <h3>📦 GGUF Variants</h3>
            <table class="variants-table">
                <thead>
                    <tr>
                        <th>Quantization</th>
                        <th>Size</th>
                        <th>File</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {variants_html}
                </tbody>
            </table>
        </div>
        
        <div class="model-links">
            <a href="{model['hf_url']}" target="_blank" class="primary-link">View on Hugging Face ↗</a>
        </div>
    </article>"""


def get_digest_history() -> list[dict]:
    """Get digest history from existing HTML files in dist."""
    dist_dir = Path(OUTPUT_DIR)
    if not dist_dir.exists():
        return []
    
    history = []
    for html_file in sorted(dist_dir.glob("digest-*.html")):
        # Extract date from filename
        date_str = html_file.stem.replace("digest-", "")
        history.append({
            "date": date_str,
            "path": str(html_file),
        })
    
    return sorted(history, key=lambda x: x["date"])


# ============================================================
# MAGAZINE HTML TEMPLATE
# ============================================================

MAGAZINE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>%s</title>
    <link rel="stylesheet" href="../static/magazine.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <!-- Magazine Cover -->
    <header class="magazine-cover">
        <div class="cover-content">
            <div class="cover-brand">
                <span class="brand-icon">🤖</span>
                <h1 class="brand-title">AI日报</h1>
                <span class="brand-subtitle">GGUF 量化模型快报</span>
            </div>
            <div class="cover-date">
                <span class="date-year">%s</span>
                <span class="date-separator">/</span>
                <span class="date-month-day">%s</span>
            </div>
            <div class="cover-stats">
                <span class="stat-item">📊 %s 个新模型</span>
                <span class="stat-divider">·</span>
                <span class="stat-item">🔄 自动采集</span>
                <span class="stat-divider">·</span>
                <span class="stat-item">📡 HuggingFace</span>
            </div>
            <div class="cover-footer">
                <p>Powered by AI · 每小时自动扫描 · 每日发布</p>
                <p class="generated-at">生成时间: %s</p>
            </div>
        </div>
    </header>

    <!-- Navigation Bar -->
    <nav class="magazine-nav">
        <div class="nav-inner">
            <button class="nav-btn prev-btn" onclick="scrollPage(-1)" title="上一页">◀</button>
            <button class="nav-btn toc-toggle" onclick="toggleTOC()" title="目录">☰ 目录</button>
            <span class="nav-date">%s</span>
            <button class="nav-btn next-btn" onclick="scrollPage(1)" title="下一页">▶</button>
        </div>
    </nav>

    <!-- Table of Contents Sidebar -->
    <aside class="toc-sidebar" id="tocSidebar">
        <div class="toc-header">
            <h3>📋 本期目录</h3>
            <button class="toc-close" onclick="toggleTOC()">✕</button>
        </div>
        <div class="toc-list">
%s
        </div>
        <div class="toc-nav">
%s
%s
        </div>
    </aside>

    <!-- Overlay for mobile TOC -->
    <div class="toc-overlay" id="tocOverlay" onclick="toggleTOC()"></div>

    <!-- Main Content -->
    <main class="magazine-content">
        <!-- Issue Navigation -->
        <div class="issue-nav">
%s
            <span class="issue-counter">第 %s 期</span>
%s
        </div>

        <!-- Model Cards -->
%s

        <!-- Empty State -->
%s
    </main>

    <!-- Footer -->
    <footer class="magazine-footer">
        <div class="footer-inner">
            <p>📰 AI日报 GGUF量化模型快报 · %s</p>
            <p>数据来源: <a href="https://huggingface.co/models?search=gguf" target="_blank">HuggingFace</a> · 自动化采集与审核</p>
            <p>项目地址: <a href="https://github.com/suifei/ai-daily-gguf-digest" target="_blank">GitHub</a></p>
        </div>
    </footer>

    <script src="../static/magazine.js"></script>
</body>
</html>"""


def generate_index_page(history: list[dict], output_path: str) -> str:
    """Generate the main index page listing all digests."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    entries_html = ""
    for entry in sorted(history, key=lambda x: x["date"], reverse=True):
        date = entry["date"]
        html_path = f"digest-{date}.html"
        entries_html += f"""
        <a href="{html_path}" class="digest-entry">
            <span class="entry-date">{date}</span>
            <span class="entry-arrow">→</span>
        </a>"""
    
    html = INDEX_TEMPLATE.format(entries=entries_html)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Generated index page: {output_path}")
    return output_path


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI日报 GGUF量化模型快报 - 目录</title>
    <link rel="stylesheet" href="static/magazine.css">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
</head>
<body class="index-page">
    <header class="index-header">
        <h1>📰 AI日报 GGUF量化模型快报</h1>
        <p>每日自动发现、整理和发布最新开源LLM GGUF量化模型</p>
        <a href="https://github.com/suifei/ai-daily-gguf-digest" target="_blank" class="github-link">⭐ GitHub</a>
    </header>
    
    <main class="index-main">
        <h2>往期快报</h2>
        <div class="digest-list">
            {entries}
        </div>
    </main>
    
    <footer class="index-footer">
        <p>🤖 由AI驱动 · 每小时自动扫描 · 每日发布</p>
    </footer>
</body>
</html>"""
