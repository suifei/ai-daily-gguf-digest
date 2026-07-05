"""
AI日报 电子杂志HTML渲染引擎
============================
生成具有翻页效果、目录导航、上一期/下一期的电子杂志风格HTML日报。
"""

import os
import json
import re
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
    
    # Build model entries HTML
    model_entries = ""
    for idx, model in enumerate(models):
        model_entries += build_model_entry(model, idx, date_str)
    
    # Build TOC entries
    toc_entries = ""
    for model in models:
        safe_id = model["repo_id"].replace("/", "-").replace("_", "-").lower()
        model_name = model.get("model_name", model["repo_id"])
        toc_entries += f'<li><a href="#model-{safe_id}">{model_name}</a></li>\n'
    
    title = f"AI日报 GGUF模型快报 {date_str}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Build TOC nav links
    toc_prev = f'<a href="/ai-daily-gguf-digest/digest-{prev_date}.html">← 上一期 ({prev_date})</a>' if prev_date else '<span>← 更早</span>'
    toc_next = f'<a href="/ai-daily-gguf-digest/digest-{next_date}.html">下一期 ({next_date}) →</a>' if next_date else '<span>更晚 →</span>'
    
    # Build issue nav links
    issue_prev = f'<a href="/ai-daily-gguf-digest/digest-{prev_date}.html">← 上一期: {prev_date}</a>' if prev_date else '<span class="disabled">← 上一期</span>'
    issue_next = f'<a href="/ai-daily-gguf-digest/digest-{next_date}.html">下一期: {next_date} →</a>' if next_date else '<span class="disabled">下一期 →</span>'
    
    # Empty state placeholder
    empty_state = '<p class="empty-state">今日暂无新模型发现。</p>' if not models else ''
    
    # Count total digests
    total_issues = len(get_digest_history())
    
    html = MAGAZINE_TEMPLATE % (
        title,                          # %s title
        date_str,                       # %s date_str  
        len(models),                    # %s model_count
        generated_at,                   # %s generated_at
        issue_prev,                     # %s issue-nav-prev
        total_issues,                   # %s issue-counter
        issue_next,                     # %s issue-nav-next
        toc_entries,                    # %s toc-list (sticky)
        toc_prev,                       # %s toc-nav-prev
        toc_next,                       # %s toc-nav-next
        toc_entries,                    # %s toc-list (mobile)
        toc_prev,                       # %s toc-nav-prev (mobile)
        toc_next,                       # %s toc-nav-next (mobile)
        model_entries,                  # %s model-cards
        empty_state,                    # %s empty-state
        date_str,                       # %s footer-date
    )
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Generated magazine HTML: {output_path} ({len(models)} models)")
    return output_path


def build_model_entry(model: dict, index: int, date_str: str) -> str:
    """Build HTML for a single model entry (journal style, no cards/tables)."""
    repo_id = model["repo_id"]
    safe_id = repo_id.replace("/", "-").replace("_", "-").lower()
    author = model.get("author", "")
    model_name = model.get("model_name", repo_id)
    
    # Use Chinese description if available
    chinese_desc = model.get("chinese_description", "") or model.get("description", "")
    chinese_summary = model.get("chinese_summary", "")
    risk_level = model.get("risk_level", "low")
    review_notes = model.get("review_notes", "")
    
    downloads = model.get("downloads", 0)
    likes = model.get("likes", 0)
    tags = model.get("tags", [])
    
    # Risk indicator
    risk_class = "low" if risk_level == "low" else ("medium" if risk_level == "medium" else "high")
    risk_label = "低风险" if risk_level == "low" else ("中等风险" if risk_level == "medium" else "高风险")
    risk_badge = f'<span class="risk-indicator {risk_class}">{risk_label}</span>'
    
    # Build quantification spec list (poetry-style, no table)
    specs_html = ""
    gguf_files = model.get("gguf_files", [])
    if gguf_files:
        specs_items = []
        for gi, gguf in enumerate(gguf_files):
            quant = gguf.get("quantization", "Unknown")
            size = gguf.get("size_human", "N/A")
            filename = gguf.get("filename", "unknown.gguf")
            browser_url = gguf.get("browser_url", "")
            specs_items.append(f'''<li>
                <span class="spec-quant">{quant}</span>
                <span class="spec-dot">·</span>
                <span class="spec-size">{size}</span>
                <span class="spec-dot">·</span>
                <a href="{browser_url}" target="_blank" class="spec-link" data-copy title="复制链接">{filename}</a>
            </li>''')
        specs_html = '<ul class="spec-list">' + ''.join(specs_items) + '</ul>'
    
    # Tags display
    tags_html = ""
    for tag in tags[:10]:
        if tag not in ("gguf", "diffusers", "safetensors", "pytorch", "transformers"):
            tags_html += f'<span class="tag">{tag}</span>'
    
    # Description - parse markdown if present
    desc_text = chinese_summary if chinese_summary else chinese_desc
    if desc_text:
        desc_text = desc_text[:500] + ('...' if len(desc_text) > 500 else '')
        desc_html = _parse_markdown(desc_text)
    else:
        desc_html = ""
    
    # Benchmark section (if available)
    benchmark_html = ""
    benchmark_data = model.get("benchmark")
    if benchmark_data:
        benchmark_html = _build_benchmark_section(benchmark_data)
    
    # Review notes
    notes_html = ""
    if review_notes:
        notes_html = f'<p class="review-note">审核备注: {review_notes}</p>'
    
    return f'''
    <article class="model-entry" id="model-{safe_id}">
        <h2 class="model-name">{model_name}</h2>
        <p class="model-author">by {author} · {downloads:,} 下载 · {likes:,} 赞</p>
        
        {risk_badge}
        
        {f'<div class="tag-list">{tags_html}</div>' if tags_html else ''}
        
        {f'<div class="model-description">{desc_html}</div>' if desc_html else ''}
        
        {specs_html if specs_html else ''}
        
        {benchmark_html}
        
        {notes_html}
        
        <div class="model-links">
            <a href="{model.get('hf_url', '')}" target="_blank">在 HuggingFace 查看 ↗</a>
        </div>
    </article>'''


def _parse_markdown(text: str) -> str:
    """Parse simple markdown to HTML for model descriptions."""
    html = text
    
    # Code blocks (```...```)
    def replace_code_block(match):
        code = match.group(1).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<pre><code>{code}</code></pre>'
    
    html = re.sub(r'```([\s\S]*?)```', replace_code_block, html)
    
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Italic
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # Links [text](url)
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', html)
    
    # Blockquotes
    html = re.sub(r'^>\s?(.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    
    # Unordered lists
    lines = html.split('\n')
    result = []
    in_list = False
    for line in lines:
        if line.strip().startswith('- '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            item = re.sub(r'^-\s?', '', line.strip())
            result.append(f'<li>{item}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)
    if in_list:
        result.append('</ul>')
    
    html = '\n'.join(result)
    
    # Paragraphs: wrap non-tag lines
    paragraphs = re.split(r'\n\n+', html)
    html = ''
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Don't wrap if already a block element
        if p.startswith(('<pre', '<ul', '<li', '<blockquote', '<h', '<div')):
            html += p
        else:
            html += f'<p>{p}</p>'
        html += '\n'
    
    return html.strip()


def _build_benchmark_section(benchmark_data: dict) -> str:
    """Build expandable benchmark section."""
    html_parts = []
    
    if benchmark_data.get("image_url"):
        html_parts.append(f'<img src="{benchmark_data["image_url"]}" alt="Benchmark" loading="lazy">')
    
    if benchmark_data.get("table"):
        table_html = '<table><thead><tr>'
        headers = benchmark_data["table"].get("headers", [])
        for h in headers:
            table_html += f'<th>{h}</th>'
        table_html += '</tr></thead><tbody>'
        
        rows = benchmark_data["table"].get("rows", [])
        for row in rows:
            table_html += '<tr>'
            for cell in row:
                table_html += f'<td>{cell}</td>'
            table_html += '</tr>'
        table_html += '</tbody></table>'
        html_parts.append(table_html)
    
    if not html_parts:
        return ""
    
    content = '\n'.join(html_parts)
    return f'''
    <div class="benchmark-section">
        <button class="benchmark-toggle" onclick="this.nextElementSibling.classList.toggle('visible'); this.textContent = this.nextElementSibling.classList.contains('visible') ? '收起 Benchmark ▲' : '查看 Benchmark ▼'">查看 Benchmark ▼</button>
        <div class="benchmark-content">{content}</div>
    </div>'''


def get_digest_history() -> list[dict]:
    """Get digest history from existing HTML files in dist and root."""
    history = []
    
    # Scan dist directory
    dist_dir = Path(OUTPUT_DIR)
    if dist_dir.exists():
        for html_file in sorted(dist_dir.glob("digest-*.html")):
            date_str = html_file.stem.replace("digest-", "")
            history.append({
                "date": date_str,
                "path": str(html_file),
            })
    
    # Scan root directory (for GitHub Pages legacy build)
    root_dir = Path(OUTPUT_DIR).parent
    for html_file in sorted(root_dir.glob("digest-*.html")):
        date_str = html_file.stem.replace("digest-", "")
        # Avoid duplicates
        if not any(h["date"] == date_str for h in history):
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
    <link rel="stylesheet" href="/ai-daily-gguf-digest/static/magazine.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&family=Noto+Serif+SC:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <!-- Reading Progress Bar -->
    <div class="progress-bar"></div>

    <!-- Masthead / Cover -->
    <header class="masthead">
        <h1 class="masthead-brand">AI日报</h1>
        <p class="masthead-subtitle">GGUF 量化模型快报</p>
        <div class="masthead-date">%s</div>
        <div class="masthead-meta">
            <span>%s 个新模型</span>
            <span>自动采集</span>
            <span>HuggingFace</span>
        </div>
        <p class="masthead-generated">生成时间: %s</p>
    </header>

    <!-- Issue Navigation -->
    <nav class="issue-nav">
        %s
        <span class="issue-counter">第 %s 期</span>
        %s
    </nav>

    <!-- Layout: Sticky TOC + Content -->
    <div class="layout">
        <!-- Sticky TOC -->
        <aside class="toc-sticky">
            <div class="toc-title">目录</div>
            <ul class="toc-list">
%s            </ul>
            <div class="toc-nav">
                %s
                %s
            </div>
        </aside>

        <!-- Mobile TOC Toggle Button -->
        <button class="toc-toggle-btn" onclick="document.querySelector('.toc-panel').classList.toggle('open')" aria-label="目录">☰</button>

        <!-- Mobile TOC Panel -->
        <div class="toc-panel">
            <button class="toc-panel-close" onclick="this.parentElement.classList.remove('open')">✕</button>
            <div class="toc-title">目录</div>
            <ul class="toc-list">
%s            </ul>
            <div class="toc-nav">
                %s
                %s
            </div>
        </div>

        <!-- Main Content -->
        <div class="content">
            <div class="models-grid">
%s
            </div>
%s
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <p>📰 AI日报 GGUF量化模型快报 · %s</p>
        <p>数据来源: <a href="https://huggingface.co/models?search=gguf" target="_blank">HuggingFace</a> · 自动化采集与审核</p>
        <p>项目地址: <a href="https://github.com/suifei/ai-daily-gguf-digest" target="_blank">GitHub</a></p>
    </footer>

    <script src="/ai-daily-gguf-digest/static/magazine.js"></script>
</body>
</html>"""


def generate_index_page(history: list[dict], output_path: str) -> str:
    """Generate the main index page listing all digests."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    entries_html = ""
    for entry in sorted(history, key=lambda x: x["date"], reverse=True):
        date = entry["date"]
        html_path = f"digest-{date}.html"
        repo_prefix = "/ai-daily-gguf-digest/"
        entries_html += f"""
        <li><a href="{repo_prefix}{html_path}">{date}</a></li>"""
    
    html = INDEX_TEMPLATE.format(entries=entries_html)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Generated index page: {output_path}")
    
    return output_path


def update_readme_table(history: list[dict]) -> str:
    """Update the README.md with the latest digest table.
    
    Returns the path to the updated README.md.
    """
    readme_path = Path("/tmp/ai-daily-repo/README.md")
    if not readme_path.exists():
        logger.warning("README.md not found, skipping update")
        return ""
    
    # Read current README
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()
    
    # Build the new table rows
    table_rows = ""
    for entry in sorted(history, key=lambda x: x["date"], reverse=True):
        date = entry["date"]
        html_path = f"digest-{date}.html"
        model_count = entry.get("model_count", "?")
        table_rows += f"| [{date}]({html_path}) | 第 {date.replace('-', '.')} 期 | {model_count} 个模型 | [阅读](https://suifei.github.io/ai-daily-gguf-digest/{html_path}) |\n"
    
    # Replace the table section in README
    # Find the table and replace it
    old_table_pattern = r"(\|\s*日期\s*\|\s*期数\s*\|\s*模型数量\s*\|\s*阅读\s*\|\n\|\s*------\s*\|\s*------\s*\|\s*----------\s*\|\s*------\s*\|)(\n\|\s*\*每晚20:00.*?$)"
    new_table = f"\\1\n{table_rows}\\2"
    
    updated_readme = re.sub(old_table_pattern, new_table, readme_content, flags=re.MULTILINE | re.DOTALL)
    
    # Write updated README
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated_readme)
    
    logger.info(f"Updated README.md with digest table")
    return str(readme_path)

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI日报 GGUF量化模型快报</title>
    <link rel="stylesheet" href="/ai-daily-gguf-digest/static/magazine.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&family=Noto+Serif+SC:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="progress-bar"></div>

    <header class="masthead">
        <h1 class="masthead-brand">AI日报</h1>
        <p class="masthead-subtitle">GGUF 量化模型快报 · 目录</p>
        <div class="masthead-meta">
            <span>每日更新</span>
            <span>自动采集</span>
            <span>HuggingFace</span>
        </div>
        <p class="masthead-generated" style="margin-top: 2rem;">
            <a href="https://github.com/suifei/ai-daily-gguf-digest" target="_blank" style="color: #8A8A8A; text-decoration: none; border-bottom: 1px solid #E5E5E5;">⭐ GitHub 项目地址</a>
        </p>
    </header>
    
    <main class="content" style="max-width: var(--max-width); margin: 0 auto; padding: 2rem;">
        <div style="display: flex; gap: 2rem; margin-bottom: 2rem;">
            <a href="hot-ranking.html" style="flex: 1; text-align: center; padding: 1.5rem; border: 1px solid var(--rule); text-decoration: none; color: var(--text-primary); transition: all 0.2s ease;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔥</div>
                <div style="font-family: var(--serif); font-size: 1.2rem; font-weight: 600; margin-bottom: 0.25rem;">热门模型榜单</div>
                <div style="font-size: 0.8rem; color: var(--text-muted);">HuggingFace 最受欢迎的模型</div>
            </a>
            <a href="https://github.com/suifei/ai-daily-gguf-digest" target="_blank" style="flex: 1; text-align: center; padding: 1.5rem; border: 1px solid var(--rule); text-decoration: none; color: var(--text-primary); transition: all 0.2s ease;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">⭐</div>
                <div style="font-family: var(--serif); font-size: 1.2rem; font-weight: 600; margin-bottom: 0.25rem;">GitHub 项目</div>
                <div style="font-size: 0.8rem; color: var(--text-muted);">查看源代码与文档</div>
            </a>
        </div>
        
        <div class="toc-title" style="margin-bottom: 1.5rem;">往期快报</div>
        <ul class="toc-list" style="border-right: none;">
            {entries}
        </ul>
    </main>
    
    <footer class="footer">
        <p>🤖 由AI驱动 · 每小时自动扫描 · 每日发布</p>
    </footer>
    
    <script src="/ai-daily-gguf-digest/static/magazine.js"></script>
</body>
</html>"""
