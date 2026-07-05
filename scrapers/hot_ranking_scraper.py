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
    # Qwen系列
    "Qwen/Qwen3-0.6B": {
        "name_cn": "Qwen3-0.6B",
        "family": "Qwen3",
        "developer": "阿里巴巴通义实验室",
        "description": "Qwen3系列的超轻量级模型，仅0.6B参数，适合边缘设备和移动端部署。在保持良好性能的同时，实现了极高的推理速度。",
        "highlights": ["仅0.6B参数，极致轻量", "适合边缘设备和IoT场景", "推理速度极快，延迟极低", "多语言支持（中、英、日、韩等）", "64K超长上下文窗口"],
        "use_cases": ["端侧推理", "移动应用", "IoT设备", "实时翻译"],
        "related_news": "Qwen3系列发布了多个尺寸，覆盖从0.6B到235B的全尺寸范围，是2025年最具影响力的开源模型家族之一。"
    },
    "Qwen/Qwen3-8B": {
        "name_cn": "Qwen3-8B",
        "family": "Qwen3",
        "developer": "阿里巴巴通义实验室",
        "description": "Qwen3系列的8B参数模型，在性能和效率之间取得优秀平衡。支持MoE架构，激活参数仅3.5B，推理成本大幅降低。",
        "highlights": ["8B总参数，3.5B激活参数（MoE架构）", "64K上下文窗口", "多语言能力强（26+语言）", "代码生成和数学推理出色", "推理成本降低60%"],
        "use_cases": ["通用对话", "代码生成", "多语言翻译", "文档分析"],
        "related_news": "Qwen3-8B采用混合注意力机制和MoE架构，在MMLU、GSM8K等基准测试中超越多数同尺寸模型。"
    },
    # GLM系列
    "THUDM/glm-4-9b-chat": {
        "name_cn": "GLM-4-9B-Chat",
        "family": "GLM4",
        "developer": "清华大学智谱AI",
        "description": "智谱AI开源的GLM-4系列聊天模型，9B参数规模。采用混合注意力机制和混合MoE架构，支持256K超长上下文窗口。",
        "highlights": ["9B参数，性能卓越", "256K上下文窗口", "混合MoE架构", "支持多语言", "强大的指令遵循能力"],
        "use_cases": ["对话系统", "文本生成", "代码编写", "逻辑推理"],
        "related_news": "GLM-4是智谱AI在2024年推出的新一代开源模型，性能接近GPT-4水平。"
    },
    "THUDM/glm-4-9b": {
        "name_cn": "GLM-4-9B",
        "family": "GLM4",
        "developer": "清华大学智谱AI",
        "description": "智谱AI开源的GLM-4基础模型，9B参数。采用混合注意力机制和混合MoE架构，支持256K超长上下文窗口。",
        "highlights": ["9B参数，性能卓越", "256K上下文窗口", "混合MoE架构", "支持多语言", "强大的指令遵循能力"],
        "use_cases": ["文本生成", "代码编写", "逻辑推理", "知识问答"],
        "related_news": "GLM-4是智谱AI在2024年推出的新一代开源模型，性能接近GPT-4水平。"
    },
    # Llama系列
    "meta-llama/Llama-3.1-8B-Instruct": {
        "name_cn": "Llama-3.1-8B-Instruct",
        "family": "Llama3.1",
        "developer": "Meta",
        "description": "Meta开源的Llama 3.1系列中的8B指令微调模型。采用混合注意力机制和混合MoE架构，支持128K上下文窗口。",
        "highlights": ["8B参数，效率高", "128K上下文窗口", "多语言支持", "代码生成能力强", "开源可商用"],
        "use_cases": ["对话系统", "文本生成", "代码编写", "知识问答"],
        "related_news": "Llama 3.1是Meta在2024年推出的新一代开源大模型，性能全面超越前代。"
    },
    "meta-llama/Llama-3.1-70B": {
        "name_cn": "Llama-3.1-70B",
        "family": "Llama3.1",
        "developer": "Meta",
        "description": "Meta开源的Llama 3.1系列中的70B大模型。采用混合注意力机制和混合MoE架构，支持128K上下文窗口。",
        "highlights": ["70B参数，性能强大", "128K上下文窗口", "多语言支持", "代码生成能力强", "开源可商用"],
        "use_cases": ["复杂推理", "代码生成", "长文档分析", "专业领域问答"],
        "related_news": "Llama 3.1是Meta在2024年推出的新一代开源大模型，性能全面超越前代。"
    },
    # Mistral系列
    "mistralai/Mistral-7B-Instruct-v0.3": {
        "name_cn": "Mistral-7B-Instruct-v0.3",
        "family": "Mistral",
        "developer": "Mistral AI",
        "description": "Mistral AI开源的7B指令微调模型。采用滑动窗口注意力机制，支持32K上下文窗口，推理速度快。",
        "highlights": ["7B参数，效率高", "32K上下文窗口", "滑动窗口注意力", "推理速度快", "多语言支持"],
        "use_cases": ["对话系统", "文本生成", "代码编写", "知识问答"],
        "related_news": "Mistral 7B是当时开源领域性价比最高的模型之一。"
    },
    "mistralai/Mixtral-8x7B-Instruct-v0.1": {
        "name_cn": "Mixtral-8x7B-Instruct",
        "family": "Mixtral",
        "developer": "Mistral AI",
        "description": "Mistral AI开源的混合专家（MoE）模型，8个7B子模型。稀疏激活机制使得推理成本大幅降低。",
        "highlights": ["8x7B MoE架构", "稀疏激活，效率高", "45B激活参数", "32K上下文窗口", "多语言支持"],
        "use_cases": ["对话系统", "文本生成", "代码编写", "知识问答"],
        "related_news": "Mixtral是首个开源的MoE架构大模型，性能接近Llama-3-70B。"
    },
    # Gemma系列
    "google/gemma-2-2b-it": {
        "name_cn": "Gemma-2-2B-IT",
        "family": "Gemma2",
        "developer": "Google",
        "description": "Google开源的Gemma 2系列中的2B指令微调模型。采用Decoder-only架构，支持8K上下文窗口。",
        "highlights": ["2B参数，极致轻量", "8K上下文窗口", "Decoder-only架构", "多语言支持", "推理速度快"],
        "use_cases": ["端侧推理", "移动应用", "简单对话", "文本分类"],
        "related_news": "Gemma 2是Google在2024年推出的新一代开源模型系列，覆盖2B到27B多个尺寸。"
    },
    "google/gemma-2-9b-it": {
        "name_cn": "Gemma-2-9B-IT",
        "family": "Gemma2",
        "developer": "Google",
        "description": "Google开源的Gemma 2系列中的9B指令微调模型。采用Decoder-only架构，支持8K上下文窗口。",
        "highlights": ["9B参数，性价比高", "8K上下文窗口", "Decoder-only架构", "多语言支持", "推理速度快"],
        "use_cases": ["对话系统", "文本生成", "代码编写", "知识问答"],
        "related_news": "Gemma 2是Google在2024年推出的新一代开源模型系列，覆盖2B到27B多个尺寸。"
    },
    # Phi系列
    "microsoft/phi-2": {
        "name_cn": "Phi-2",
        "family": "Phi",
        "developer": "Microsoft",
        "description": "Microsoft开源的Phi-2模型，2.7B参数。采用合成数据训练方法，在较小参数量下实现卓越性能。",
        "highlights": ["2.7B参数，性能出众", "合成数据训练", "多语言支持", "推理速度快", "适合边缘部署"],
        "use_cases": ["端侧推理", "移动应用", "简单对话", "文本分类"],
        "related_news": "Phi系列证明了小模型通过高质量数据可以达到接近大模型的性能。"
    },
    "microsoft/phi-3-mini-4k-instruct": {
        "name_cn": "Phi-3-Mini-4K",
        "family": "Phi3",
        "developer": "Microsoft",
        "description": "Microsoft开源的Phi-3系列迷你模型，3.8B参数。支持4K上下文窗口，采用高质量合成数据训练。",
        "highlights": ["3.8B参数，性价比高", "4K上下文窗口", "高质量合成数据", "多语言支持", "推理速度快"],
        "use_cases": ["对话系统", "文本生成", "代码编写", "知识问答"],
        "related_news": "Phi-3是Microsoft在2024年推出的新一代小模型系列，性能超越许多更大参数的模型。"
    },
    # OPT系列
    "facebook/opt-125m": {
        "name_cn": "OPT-125M",
        "family": "OPT",
        "developer": "Meta",
        "description": "Meta开源的OPT系列中最小规模的模型，125M参数。作为文本生成模型的基线参考，广泛用于研究和教育场景。",
        "highlights": ["125M参数，极致小巧", "Decoder-only架构", "广泛用于NLP教学研究", "支持多种语言", "可作为微调基线模型"],
        "use_cases": ["教学演示", "研究基线", "文本分类", "简单生成"],
        "related_news": "OPT系列是Meta在2022年推出的开源Decoder-only语言模型家族，推动了开源LLM的发展。"
    },
    # Falcon系列
    "tiiuae/falcon-7b": {
        "name_cn": "Falcon-7B",
        "family": "Falcon",
        "developer": "Technology Innovation Institute",
        "description": "TII开源的Falcon系列7B模型。采用FlashAttention技术和多头注意力机制，支持128K上下文窗口。",
        "highlights": ["7B参数，效率高", "128K上下文窗口", "FlashAttention加速", "多语言支持", "开源可商用"],
        "use_cases": ["对话系统", "文本生成", "代码编写", "知识问答"],
        "related_news": "Falcon是当时开源领域性能最强的模型之一，超越了Llama-2-13B。"
    },
    # DeepSeek系列
    "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct": {
        "name_cn": "DeepSeek-Coder-V2-Lite",
        "family": "DeepSeekCoder",
        "developer": "DeepSeek",
        "description": "DeepSeek开源的代码专用模型V2 Lite版本。采用MoE架构，在代码生成任务上表现卓越。",
        "highlights": ["代码生成专家", "MoE架构，效率高", "支持多种编程语言", "128K上下文窗口", "开源可商用"],
        "use_cases": ["代码生成", "代码补全", "代码翻译", "Bug检测"],
        "related_news": "DeepSeek-Coder系列在HumanEval等代码基准测试中表现优异，超越了许多更大参数的模型。"
    },
    # Yandex系列
    "yandex-community/yandexgpt-lite": {
        "name_cn": "YandexGPT-Lite",
        "family": "YandexGPT",
        "developer": "Yandex",
        "description": "Yandex开源的YandexGPT轻量级模型。针对俄语和英语优化，支持对话和文本生成任务。",
        "highlights": ["俄语优化", "轻量级部署", "多语言支持", "对话生成", "开源可商用"],
        "use_cases": ["俄语对话", "文本生成", "客服系统", "内容创作"],
        "related_news": "YandexGPT是Yandex在2024年推出的开源模型系列，专注于俄语和多语言场景。"
    },
    # Baichuan系列
    "baichuan-inc/Baichuan2-7B-Chat": {
        "name_cn": "Baichuan2-7B-Chat",
        "family": "Baichuan2",
        "developer": "百川智能",
        "description": "百川智能开源的Baichuan2系列7B聊天模型。针对中文场景优化，支持长文本生成。",
        "highlights": ["7B参数，中文优化", "长文本生成", "对话能力强", "开源可商用", "多场景适用"],
        "use_cases": ["中文对话", "文本生成", "知识问答", "内容创作"],
        "related_news": "Baichuan2是百川智能在2024年推出的第二代开源模型系列，中文能力显著提升。"
    },
    # InternLM系列
    "internlm/internlm2-7b": {
        "name_cn": "InternLM2-7B",
        "family": "InternLM2",
        "developer": "上海人工智能实验室",
        "description": "上海人工智能实验室开源的InternLM2系列7B模型。针对中文场景优化，支持长文本和代码生成。",
        "highlights": ["7B参数，中文优化", "长文本支持", "代码生成", "开源可商用", "多场景适用"],
        "use_cases": ["中文对话", "文本生成", "代码编写", "知识问答"],
        "related_news": "InternLM系列是上海AI Lab开源的重要模型系列，中文能力处于开源模型前列。"
    },
    # Zhipu系列
    "zai-org/GLM-5.2": {
        "name_cn": "GLM-5.2",
        "family": "GLM5",
        "developer": "智谱AI",
        "description": "智谱AI开源的GLM-5系列模型，5.2B参数。采用混合注意力机制和混合MoE架构，支持超长上下文窗口。",
        "highlights": ["5.2B参数，性价比高", "混合MoE架构", "超长上下文窗口", "中文能力卓越", "多语言支持"],
        "use_cases": ["中文对话", "文本生成", "代码编写", "知识问答", "逻辑推理"],
        "related_news": "GLM-5是智谱AI在2025年推出的新一代开源模型系列，中文能力持续领先。"
    },
    # Qwen3.5系列
    "ReliquaryForge/qwen3.5-2b-reliquary": {
        "name_cn": "Qwen3.5-2B-Reliquary",
        "family": "Qwen3.5",
        "developer": "阿里巴巴通义实验室",
        "description": "Qwen3.5系列的2B参数模型，专为边缘设备优化。在保持良好性能的同时，实现了极高的推理速度。",
        "highlights": ["2B参数，极致轻量", "适合边缘设备", "推理速度极快", "中文能力优秀", "多语言支持"],
        "use_cases": ["端侧推理", "移动应用", "实时对话", "文本分类"],
        "related_news": "Qwen3.5系列是Qwen3的升级版，在中文理解和生成能力上有显著提升。"
    },
    # Qwen3.6系列
    "Qwen/Qwen3.6-35B-A3B": {
        "name_cn": "Qwen3.6-35B-A3B",
        "family": "Qwen3.6",
        "developer": "阿里巴巴通义实验室",
        "description": "Qwen3.6系列的35B参数模型，激活参数仅3.5B。采用MoE架构，在性能和效率之间取得优秀平衡。",
        "highlights": ["35B总参数，3.5B激活", "MoE架构，高效率", "中文能力卓越", "代码生成强", "多语言支持"],
        "use_cases": ["复杂推理", "代码生成", "长文档分析", "专业领域问答"],
        "related_news": "Qwen3.6系列是Qwen3的进一步升级，性能全面超越前代。"
    },
    # Gemma-4系列
    "yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF": {
        "name_cn": "Gemma-4-12B-Coder",
        "family": "Gemma4",
        "developer": "Google",
        "description": "基于Google Gemma-4-12B模型，经过Fable5 Composer 2.5数据集微调的代码专用模型。擅长代码生成和补全。",
        "highlights": ["12B参数，代码专家", "Fable5微调", "代码生成能力强", "支持多语言编程", "开源可商用"],
        "use_cases": ["代码生成", "代码补全", "代码翻译", "Bug检测"],
        "related_news": "Gemma-4是Google在2025年推出的新一代开源模型系列，代码能力显著提升。"
    },
    # Huihui-Ornith系列
    "huihui-ai/Huihui-Ornith-1.0-35B-abliterated-GGUF": {
        "name_cn": "Huihui-Ornith-35B",
        "family": "Ornith",
        "developer": "Huihui-AI",
        "description": "基于Llama-3.1-70B的abliterated模型，去除RLHF限制后释放更强的创造力和自由度。35B参数规模。",
        "highlights": ["35B参数", "ABLITERATED技术", "去除安全限制", "创造力更强", "适合研究"],
        "use_cases": ["创意写作", "角色扮演", "学术研究", "自由对话"],
        "related_news": "ABLITERATED是一种通过数学方法移除RLHF影响的技术，让模型恢复原始能力。"
    },
    # LTX视频模型
    "Abiray/LTX2.3-10Eros-1.3-GGUF": {
        "name_cn": "LTX2.3-10Eros",
        "family": "LTX",
        "developer": "Abiray",
        "description": "LTX视频生成模型的10Eros变体，1.3B参数。专为图像到视频生成任务优化，支持高质量视频合成。",
        "highlights": ["1.3B参数", "图像转视频", "高质量视频生成", "开源可商用", "边缘设备友好"],
        "use_cases": ["视频生成", "图像动画化", "内容创作", "广告制作"],
        "related_news": "LTX系列是开源视频生成模型的代表作之一，在视频质量上接近闭源模型。"
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
    """Enrich model data with Chinese knowledge base and HF API details."""
    model_id = model_data.get('modelId', '')
    knowledge = MODEL_KNOWLEDGE_BASE.get(model_id, {})
    
    # Get card data from HF API response
    card_data = model_data.get('cardData', {})
    pipeline_tag = model_data.get('pipeline_tag', '')
    tags = model_data.get('tags', [])
    
    # Extract useful info from cardData
    library_name = card_data.get('library_name', '') if isinstance(card_data, dict) else ''
    model_name = card_data.get('model_name', '') if isinstance(card_data, dict) else ''
    model_creator = card_data.get('model_creator', '') if isinstance(card_data, dict) else ''
    base_model = card_data.get('base_model', '') if isinstance(card_data, dict) else ''
    
    # Build a simple description from available data
    simple_desc = ""
    if model_name:
        simple_desc = f"{model_name}"
    if model_creator:
        simple_desc += f"，由{model_creator}开发"
    if library_name:
        simple_desc += f"，使用{library_name}框架"
    if base_model:
        simple_desc += f"，基于{base_model}模型"
    if pipeline_tag:
        simple_desc += f"，用于{pipeline_tag}任务"
    
    enriched = {
        "model_id": model_id,
        "name": model_data.get('modelName', model_id.split('/')[-1]),
        "name_cn": knowledge.get('name_cn', model_id.split('/')[-1]),
        "family": knowledge.get('family', ''),
        "developer": knowledge.get('developer', model_creator or model_id.split('/')[0] if '/' in model_id else ''),
        "description": knowledge.get('description', simple_desc),
        "highlights": knowledge.get('highlights', []),
        "use_cases": knowledge.get('use_cases', []),
        "related_news": knowledge.get('related_news', ''),
        "downloads": model_data.get('downloads', 0),
        "likes": model_data.get('likes', 0),
        "tags": tags,
        "created_at": model_data.get('createdAt', ''),
        "last_modified": model_data.get('lastModified', ''),
        "pipeline_tag": pipeline_tag,
        "hf_card_data": card_data,
        "hf_url": f"https://huggingface.co/{model_id}",
        "trending_rank": 0,
        "trending_score": 0,
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
