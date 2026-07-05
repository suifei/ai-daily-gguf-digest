#!/usr/bin/env python3
"""
热门榜单HTML渲染器
将热门模型数据渲染为报纸风格的HTML页面
"""
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "dist"
HOT_RANKING_HTML = OUTPUT_DIR / "hot-ranking.html"

MAGAZINE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="/ai-daily-gguf-digest/static/magazine.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&family=Noto+Serif+SC:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        /* Hot Ranking Specific Styles */
        .hot-ranking-header {
            text-align: center;
            padding: 4rem 2rem 3rem;
            border-bottom: 1px solid var(--rule);
            max-width: var(--max-width);
            margin: 0 auto;
        }
        
        .hot-ranking-title {
            font-family: var(--serif);
            font-size: 2.4rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }
        
        .hot-ranking-subtitle {
            font-family: var(--sans);
            font-size: 0.95rem;
            font-weight: 300;
            color: var(--text-secondary);
            letter-spacing: 0.08em;
            margin-bottom: 1.5rem;
        }
        
        .hot-ranking-meta {
            font-size: 0.8rem;
            color: var(--text-muted);
            letter-spacing: 0.04em;
        }
        
        .hot-ranking-meta span {
            margin: 0 0.5rem;
        }
        
        .hot-ranking-meta span::before,
        .hot-ranking-meta span::after {
            content: '·';
            margin: 0 0.3rem;
            color: var(--rule);
        }
        
        .hot-ranking-meta span:first-child::before,
        .hot-ranking-meta span:last-child::after {
            content: '';
            margin: 0;
        }
        
        .hot-model-card {
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--rule);
        }
        
        .hot-model-card:last-child {
            border-bottom: none;
        }
        
        .hot-rank-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            background: var(--text-primary);
            color: var(--bg);
            font-family: var(--serif);
            font-size: 1rem;
            font-weight: 700;
            border-radius: 50%;
            margin-right: 1rem;
        }
        
        .hot-model-header {
            display: flex;
            align-items: center;
            margin-bottom: 0.75rem;
        }
        
        .hot-model-name {
            font-family: var(--sans);
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.01em;
        }
        
        .hot-model-stats {
            display: flex;
            gap: 1.5rem;
            margin-bottom: 1rem;
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        
        .hot-model-stats span {
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }
        
        .hot-model-description {
            font-size: 0.92rem;
            line-height: 1.8;
            color: var(--text-secondary);
            margin-bottom: 1.25rem;
        }
        
        .hot-highlights {
            margin-bottom: 1.25rem;
        }
        
        .hot-highlights h4 {
            font-family: var(--sans);
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }
        
        .hot-highlights ul {
            list-style: none;
            padding-left: 0;
        }
        
        .hot-highlights li {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.3rem;
            padding-left: 1rem;
            position: relative;
        }
        
        .hot-highlights li::before {
            content: '•';
            position: absolute;
            left: 0;
            color: var(--text-muted);
        }
        
        .hot-use-cases {
            margin-bottom: 1.25rem;
        }
        
        .hot-use-cases h4 {
            font-family: var(--sans);
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }
        
        .hot-use-cases-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }
        
        .hot-use-case {
            font-family: var(--mono);
            font-size: 0.65rem;
            color: var(--text-muted);
            background: transparent;
            border: 1px solid var(--rule);
            padding: 0.1rem 0.45rem;
            letter-spacing: 0.03em;
        }
        
        .hot-related-news {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-style: italic;
            margin-bottom: 1.25rem;
            padding: 0.75rem 1rem;
            border-left: 2px solid var(--rule);
            background: rgba(0,0,0,0.01);
        }
        
        /* Reviews & News from web search */
        .hot-reviews-news {
            margin-bottom: 1.25rem;
        }
        .hot-reviews-news h4 {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.6rem;
        }
        .hot-review-item {
            padding: 0.6rem 0;
            border-bottom: 1px solid var(--rule);
        }
        .hot-review-item:last-child {
            border-bottom: none;
        }
        .hot-review-item a {
            font-size: 0.9rem;
            font-weight: 500;
            color: #1a5fb4;
            text-decoration: none;
            display: block;
            margin-bottom: 0.25rem;
        }
        .hot-review-item a:hover {
            text-decoration: underline;
            color: #0d3d7a;
        }
        .hot-review-snippet {
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.4;
            margin: 0;
        }
        
        .hot-model-links {
            margin-top: 1.25rem;
        }
        
        .hot-model-links a {
            font-size: 0.78rem;
            color: var(--text-muted);
            text-decoration: none;
            border-bottom: 1px solid var(--rule);
            padding-bottom: 1px;
            transition: color 0.2s ease, border-color 0.2s ease;
        }
        
        .hot-model-links a:hover {
            color: var(--text-primary);
            border-bottom-color: var(--text-primary);
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .hot-ranking-title {
                font-size: 1.8rem;
            }
            
            .hot-model-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .hot-rank-badge {
                margin-bottom: 0.5rem;
            }
        }
    </style>
</head>
<body>
    <!-- Floating Toolbar -->
    <div class="floating-toolbar">
        <a href="https://github.com/suifei/ai-daily-gguf-digest" class="toolbar-btn github-btn" target="_blank" title="GitHub 仓库" aria-label="GitHub 仓库">
            <svg viewBox="0 0 24 24"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
        </a>
        <a href="./" class="toolbar-btn" title="返回首页" aria-label="返回首页">
            <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
        </a>
        <button class="toolbar-btn" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" title="回到顶部" aria-label="回到顶部">
            <svg viewBox="0 0 24 24"><polyline points="18 15 12 9 6 15"></polyline></svg>
        </button>
        <button class="toolbar-btn" onclick="window.scrollTo({{top:document.body.scrollHeight,behavior:'smooth'}})" title="跳到底部" aria-label="跳到底部">
            <svg viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"></polyline></svg>
        </button>
    </div>

    <!-- Reading Progress Bar -->
    <div class="progress-bar"></div>

    <!-- Hot Ranking Header -->
    <header class="hot-ranking-header">
        <h1 class="hot-ranking-title">🔥 热门模型榜单</h1>
        <p class="hot-ranking-subtitle">HuggingFace 最受欢迎的大模型 · 每日更新</p>
        <div class="hot-ranking-meta">
            <span>{total_models} 个热门模型</span>
            <span>综合下载量与点赞数</span>
            <span>最后更新: {generated_at}</span>
        </div>
    </header>

    <!-- Main Content -->
    <div class="content" style="max-width: var(--max-width); margin: 0 auto; padding: 2rem;">
{cards_html}
    </div>

    <!-- Footer -->
    <footer class="footer">
        <p>🔥 热门模型榜单 · 每日自动更新</p>
        <p>数据来源: <a href="https://huggingface.co/models" target="_blank">HuggingFace</a> · 综合下载量、点赞数和近期热度</p>
        <p>项目地址: <a href="https://github.com/suifei/ai-daily-gguf-digest" target="_blank">GitHub</a></p>
    </footer>

    <script src="/ai-daily-gguf-digest/static/magazine.js"></script>
</body>
</html>"""


def build_hot_model_card(model: dict, index: int) -> str:
    """Build HTML for a single hot model card."""
    rank = model.get('trending_rank', index + 1)
    name_cn = model.get('name_cn', model.get('name', 'Unknown'))
    developer = model.get('developer', '')
    description = model.get('description', '')
    highlights = model.get('highlights', [])
    use_cases = model.get('use_cases', [])
    related_news = model.get('related_news', '')
    downloads = model.get('downloads', 0)
    likes = model.get('likes', 0)
    hf_url = model.get('hf_url', '')
    family = model.get('family', '')
    
    # Rank badge
    rank_badge = f'<div class="hot-rank-badge">{rank}</div>'
    
    # Model header
    model_header = f'''<div class="hot-model-header">
        {rank_badge}
        <h2 class="hot-model-name">{name_cn}</h2>
    </div>'''
    
    # Stats
    stats = f'''<div class="hot-model-stats">
        <span>📥 {downloads:,} 下载</span>
        <span>❤️ {likes:,} 赞</span>
        {'<span>👤 ' + developer + '</span>' if developer else ''}
        {'<span>🏷️ ' + family + '</span>' if family else ''}
    </div>'''
    
    # Description
    description_html = f'<p class="hot-model-description">{description}</p>' if description else ''
    
    # Highlights
    highlights_html = ""
    if highlights:
        highlights_items = ''.join(f'<li>{highlight}</li>' for highlight in highlights)
        highlights_html = f'''<div class="hot-highlights">
            <h4>核心亮点</h4>
            <ul>{highlights_items}</ul>
        </div>'''
    
    # Use cases
    use_cases_html = ""
    if use_cases:
        use_case_items = ''.join(f'<span class="hot-use-case">{case}</span>' for case in use_cases)
        use_cases_html = f'''<div class="hot-use-cases">
            <h4>适用场景</h4>
            <div class="hot-use-cases-list">{use_case_items}</div>
        </div>'''
    
    # Related news (from knowledge base)
    news_html = f'<div class="hot-related-news">{related_news}</div>' if related_news else ''
    
    # Reviews & news links (from web search)
    reviews_news_html = ""
    reviews_news = model.get('reviews_news', [])
    if reviews_news:
        news_links = ''
        for item in reviews_news:
            title = item.get('title', '')
            url = item.get('url', '#')
            snippet = item.get('snippet', '')
            news_links += f'''<div class="hot-review-item">
                <a href="{url}" target="_blank" rel="noopener">{title}</a>
                {f'<p class="hot-review-snippet">{snippet}</p>' if snippet else ''}
            </div>'''
        reviews_news_html = f'''<div class="hot-reviews-news">
            <h4>📰 相关评测与新闻</h4>
            {news_links}
        </div>'''
    
    # Links
    links_html = f'''<div class="hot-model-links">
        <a href="{hf_url}" target="_blank">在 HuggingFace 查看 ↗</a>
    </div>'''
    
    return f'''
    <article class="hot-model-card" id="model-{rank}">
        {model_header}
        {stats}
        {description_html}
        {highlights_html}
        {use_cases_html}
        {news_html}
        {reviews_news_html}
        {links_html}
    </article>'''


def generate_hot_ranking_html(ranking_data: list, output_path: str) -> str:
    """Generate HTML for the hot ranking page."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Build model cards
    cards_html = ""
    for index, model in enumerate(ranking_data):
        cards_html += build_hot_model_card(model, index)
    
    # Metadata
    total_models = len(ranking_data)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = "🔥 热门模型榜单 · AI日报"
    
    # Render template
    html = MAGAZINE_TEMPLATE.replace('{title}', title)
    html = html.replace('{total_models}', str(total_models))
    html = html.replace('{generated_at}', generated_at)
    html = html.replace('{cards_html}', cards_html)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Generated hot ranking HTML: {output_path} ({total_models} models)")
    return output_path


if __name__ == "__main__":
    # Load hot ranking data
    ranking_file = OUTPUT_DIR / "hot-ranking.json"
    if ranking_file.exists():
        with open(ranking_file, 'r', encoding='utf-8') as f:
            ranking_data = json.load(f)
        
        generate_hot_ranking_html(ranking_data, str(HOT_RANKING_HTML))
        print(f"✓ Generated {HOT_RANKING_HTML}")
    else:
        print(f"✗ Hot ranking file not found: {ranking_file}")
