# 📰 AI日报 GGUF量化模型快报

> **每日自动发现、整理和发布最新开源LLM GGUF量化模型**

<div align="center">

![AI日报](https://img.shields.io/badge/AI日报-GGUF-blue)
![HuggingFace](https://img.shields.io/badge/HuggingFace-GGUF-orange)
![GitHub Pages](https://img.shields.io/badge/Pages-在线查看-success)
![自动化](https://img.shields.io/badge/自动化-每小时扫描-green)

**📖 在线阅读**: [suifei.github.io/ai-daily-gguf-digest](https://suifei.github.io/ai-daily-gguf-digest)

</div>

---

## ✨ 项目简介

**AI日报 GGUF量化模型快报** 是一个全自动化的开源AI模型追踪系统。我们每小时扫描 HuggingFace 上最新的 GGUF 量化模型，经过 AI 审核后，每天晚间生成精美的电子杂志风格快报，发布到 GitHub Pages。

### 核心功能

- 🔍 **自动发现** — 每小时扫描 HuggingFace，追踪最新 GGUF 量化模型
- 🤖 **AI 审核** — 每个模型经过 AI 审核把关，确保收录质量
- 📦 **多规格记录** — 自动记录每种量化版本（Q2~Q8）、文件大小、下载链接
- 📰 **电子杂志** — 精美排版，支持目录导航、翻页浏览、上期/下期切换
- 🚀 **全自动发布** — 自动生成、审核、发布到 GitHub Pages 静态站

### 收录内容

每期刊载：
- 最新发布的 LLM 模型 GGUF 量化版本
- 每种量化规格的下载链接和文件大小
- 模型的下载量、点赞数、标签等元数据
- 模型能力描述和适用场景

---

## 🗞️ 往期快报

| 日期 | 期数 | 模型数量 | 阅读 |
|------|------|----------|------|
| *每晚20:00（北京时间）更新* | | | |

> 💡 快报每晚自动发布，点击目录页查看所有历史期刊

---

## ⚙️ 工作流程

```
┌──────────────────────────────────────────────────────────┐
│                    自动化流水线                             │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ⏰ 每小时整点                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌────────────┐   │
│  │  扫描HF API  │───▶│  发现新模型  │───▶│  存入待审区  │   │
│  └─────────────┘    └─────────────┘    └─────┬──────┘   │
│                                               │          │
│  👤 AI 审核（可随时手动触发）                     │          │
│                                               ▼          │
│                                        ┌─────────────┐   │
│                                        │  审核通过    │   │
│                                        └──────┬──────┘   │
│                                               │           │
│  ⏰ 北京时间 20:00 (UTC 12:00)                 ▼           │
│  ┌─────────────────────────────────────────────────┐     │
│  │  生成电子杂志 HTML → 推送到 GitHub Pages          │     │
│  └─────────────────────────────────────────────────┘     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 数据采集 | HuggingFace API + Python requests |
| 数据存储 | SQLite + CSV |
| 渲染引擎 | 原生 HTML/CSS/JS（暗色主题电子杂志风格） |
| 静态托管 | GitHub Pages |
| 自动化 | Python 脚本 + Cron Job |
| 网络代理 | 支持 HTTP 代理访问 HuggingFace |

---

## 📂 项目结构

```
ai-daily-gguf-digest/
├── scraper/              # HuggingFace 爬虫模块
│   ├── gguf_scraper.py   # 核心爬虫逻辑
│   └── __init__.py
├── review/               # 模型审核与数据库
│   ├── model_review.py   # 审核、去重、CSV导出
│   └── __init__.py
├── renderer/             # 电子杂志渲染引擎
│   ├── magazine_renderer.py  # HTML模板生成
│   └── __init__.py
├── publisher/            # GitHub Pages 发布
│   ├── publisher.py      # Git推送自动化
│   └── __init__.py
├── static/               # 静态资源
│   ├── magazine.css      # 电子杂志样式
│   └── magazine.js       # 交互脚本
├── templates/            # HTML 模板
├── data/                 # 数据存储
│   ├── pending/          # 待审核模型
│   ├── approved/         # 已审核模型
│   └── database/         # SQLite + CSV
├── dist/                 # 生成的日报 HTML
│   ├── index.html        # 目录首页
│   └── digest-YYYY-MM-DD.html  # 每日快报
├── config/               # 配置文件
│   └── settings.json
├── logs/                 # 运行日志
├── main.py               # 主入口脚本
└── README.md
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- GitHub CLI (`gh`)
- HTTP 代理（如需访问 HuggingFace）

### 安装依赖

```bash
pip3 install requests
```

### 运行方式

```bash
# 完整流程：扫描 + 审核 + 发布
python3 main.py --full

# 仅扫描新模型
python3 main.py --scan

# 批准所有待审模型
python3 main.py --approve-all

# 发布日报
python3 main.py --publish

# 审核单个模型
python3 main.py --approve meta-llama/Llama-3.2-3B
```

---

## 📡 定时任务

### 每小时扫描（北京时间 20:00~07:00）

```bash
# 添加到 crontab
0 12-23 * * * cd /path/to/ai-daily && python3 main.py --scan >> logs/scan.log 2>&1
```

### 每晚发布（北京时间 20:00）

```bash
# 添加到 crontab
0 12 * * * cd /path/to/ai-daily && python3 main.py --publish >> logs/publish.log 2>&1
```

---

## 🎨 阅读指南

电子杂志支持以下交互：

| 操作 | 方式 |
|------|------|
| 翻页 | 点击 ◀ ▶ 按钮，或使用 ← → 方向键 |
| 目录 | 点击 ☰ 打开侧边目录，点击条目跳转 |
| 关闭目录 | 点击 ✕、遮罩层，或按 `Esc` |
| 上一期/下一期 | 目录底部导航链接 |
| 进度条 | 页面顶部显示阅读进度 |
| 模型卡片 | 悬停高亮，点击链接跳转 HuggingFace |

---

## 📊 数据说明

- **数据来源**: [HuggingFace Models](https://huggingface.co/models?search=gguf)
- **更新频率**: 每小时扫描，每日发布
- **收录标准**: 开源 LLM 的 GGUF 量化版本，经 AI 审核确认
- **去重机制**: 同一模型的同版本量化不会重复收录

---

## 📝 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

模型数据版权归各自原作者所有。

---

## 🙏 致谢

- [HuggingFace](https://huggingface.co/) — 开放的AI模型平台
- [GGUF](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md) — GGML 量化格式
- [GitHub Pages](https://pages.github.com/) — 静态站点托管

---

<div align="center">

**Made with 🤖 by AI · Powered by Hermes Agent**

[📖 查看快报](https://suifei.github.io/ai-daily-gguf-digest) · [⭐ Star](https://github.com/suifei/ai-daily-gguf-digest) · [🐛 Issues](https://github.com/suifei/ai-daily-gguf-digest/issues)

</div>
