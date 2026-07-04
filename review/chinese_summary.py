"""
AI日报 模型翻译与摘要模块
==========================
对审核通过的模型进行：
1. 英文描述翻译为中文
2. 基于模型元数据生成500字以内的能力介绍
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("ai-daily.translate")

# 常用LLM模型的能力知识库（用于生成高质量摘要）
MODEL_KNOWLEDGE_BASE = {
    "llama": {
        "family": "Meta Llama系列",
        "capability_template": "该模型属于{family}，参数量为{params}，支持{ctx}上下文窗口。采用{arch}架构，擅长自然语言理解、代码生成、多轮对话和逻辑推理。GGUF量化格式使其可在消费级硬件上高效运行。",
    },
    "qwen": {
        "family": "阿里巴巴通义千问系列",
        "capability_template": "该模型属于{family}，参数量为{params}，在中文和英文双语任务上表现优异。擅长长文本理解、代码生成、数学计算和知识问答。GGUF量化版本可在本地设备流畅运行。",
    },
    "mistral": {
        "family": "Mistral AI系列",
        "capability_template": "该模型属于{family}，采用滑动注意力机制(Sliding Window Attention)，参数量为{params}，支持{ctx}上下文。擅长代码生成、指令遵循和多语言任务。",
    },
    "deepseek": {
        "family": "深度求索(DeepSeek)系列",
        "capability_template": "该模型属于{family}，采用MoE(Mixture of Experts)架构，激活参数{params}，总参数{total_params}。擅长编程、数学推理和多语言任务，推理效率高。",
    },
    "nemotron": {
        "family": "NVIDIA Nemotron系列",
        "capability_template": "该模型由NVIDIA开发，参数量为{params}，注重隐私保护和安全性。擅长通用对话、知识问答和内容生成。",
    },
    "phi": {
        "family": "Microsoft Phi系列",
        "capability_template": "该模型由微软开发，采用知识蒸馏技术，参数量{params}。在极小参数下实现强大性能，擅长推理、代码和数学任务。",
    },
    "gemma": {
        "family": "Google Gemma系列",
        "capability_template": "该模型由Google开发，基于Gemini技术研究，参数量为{params}。擅长多语言理解、代码生成和对话任务，开源友好。",
    },
    "hermes": {
        "family": "Nous Research Hermes系列",
        "capability_template": "该模型基于{base_model}微调，采用Hermes指令微调框架，参数量{params}。擅长指令遵循、角色扮演、函数调用和结构化输出。",
    },
}

# 量化版本说明
QUANT_GUIDE = {
    "Q2_K": "极低精度量化，模型体积最小，速度最快，但损失较多精度",
    "Q3_K_S": "超小尺寸量化，适合资源受限设备",
    "Q3_K_M": "中等尺寸量化，精度与体积的较好平衡",
    "Q3_K_L": "较大尺寸量化，接近原始模型精度",
    "Q4_0": "传统4-bit量化，兼容性好",
    "Q4_1": "比Q4_0精度略高",
    "Q4_K_M": "推荐的4-bit量化，精度与效率的优秀平衡",
    "Q4_K_S": "小型K量化4-bit",
    "Q5_0": "5-bit高精度量化",
    "Q5_1": "5-bit量化，精度更高",
    "Q5_K_M": "推荐的5-bit量化，接近FP16精度",
    "Q5_K_S": "小型5-bit K量化",
    "Q6_K": "6-bit超高精度量化，几乎无损",
    "Q8_0": "8-bit量化，接近原始FP16精度",
    "FP16": "半浮点精度，最大体积最高质量",
    "FP32": "单浮点精度，仅供研究用途",
}


def get_model_family(repo_id: str, tags: list) -> str:
    """Detect model family from repo_id and tags."""
    repo_lower = repo_id.lower()
    for family in MODEL_KNOWLEDGE_BASE:
        if family in repo_lower:
            return family
    for tag in tags:
        tag_lower = tag.lower()
        for family in MODEL_KNOWLEDGE_BASE:
            if family in tag_lower:
                return family
    return "unknown"


def extract_params(model_info: dict) -> str:
    """Extract parameter count from model info."""
    desc = model_info.get("description", "") or ""
    card = model_info.get("card_data", {}) or {}
    
    # Try to find parameter count in description
    import re
    # Look for patterns like "7B", "8B", "70B", "1.5B" etc.
    match = re.search(r'(\d+\.?\d*)\s*[Bb]', desc)
    if match:
        return match.group(1) + "B"
    
    # Check card data
    if isinstance(card, dict):
        for key in ["model_name", "model_author"]:
            if key in card:
                val = card[key]
                if isinstance(val, str):
                    match = re.search(r'(\d+\.?\d*)\s*[Bb]', val)
                    if match:
                        return match.group(1) + "B"
    
    return "未知"


def extract_context_length(model_info: dict) -> str:
    """Extract context length from model info."""
    desc = model_info.get("description", "") or ""
    import re
    
    # Look for patterns like "8K", "32K", "128K", "131072" etc.
    patterns = [
        r'(\d+)\s*K',
        r'(\d{4,6})\s*(?:context|token)',
        r'max\s*context\s*(?:length)?[:\s]*(\d+)',
    ]
    for pat in patterns:
        match = re.search(pat, desc, re.IGNORECASE)
        if match:
            val = match.group(1)
            if int(val) < 10000:
                return val + "K" if len(val) <= 3 else f"{int(val)//1000}K"
            return val
    
    return "未知"


def translate_description(desc: str) -> str:
    """
    Translate model description to Chinese.
    Since we can't call an external translation API directly,
    we use a heuristic approach: identify key patterns and translate.
    
    In production, this should call an LLM or translation service.
    """
    if not desc:
        return ""
    
    # For now, return the original with a note
    # The AI reviewer will provide the actual Chinese translation during approval
    return desc


def generate_chinese_summary(model_info: dict) -> str:
    """
    Generate a Chinese summary of the model's capabilities (~500 chars).
    
    This is called during the AI review step. The AI reviewer can
    refine or replace this auto-generated summary.
    """
    repo_id = model_info.get("repo_id", "")
    model_name = model_info.get("model_name", "")
    tags = model_info.get("tags", [])
    family_key = get_model_family(repo_id, tags)
    
    params = extract_params(model_info)
    ctx = extract_context_length(model_info)
    
    # Build summary
    parts = []
    
    # Model identification
    parts.append(f"**{model_name}**")
    
    # Family info
    if family_key != "unknown":
        family_info = MODEL_KNOWLEDGE_BASE[family_key]
        template = family_info["capability_template"]
        parts.append(template.format(
            family=family_info["family"],
            params=params,
            ctx=ctx,
            arch="多头注意力+Transformer",
        ))
    else:
        parts.append(f"该模型参数量约{params}，支持{ctx}上下文窗口。")
    
    # Tags analysis
    if tags:
        capability_tags = []
        for tag in tags:
            tag_map = {
                "text-generation": "文本生成",
                "chat": "对话",
                "roleplay": "角色扮演",
                "creative-writing": "创意写作",
                "code": "代码生成",
                "math": "数学推理",
                "reasoning": "逻辑推理",
                "uncensored": "无限制",
                "abliterated": "abliterated（去除对齐限制）",
                "llama": "Llama基座",
                "llama-3": "Llama 3",
                "llama-3.1": "Llama 3.1",
                "llama-3.2": "Llama 3.2",
                "llama-3.3": "Llama 3.3",
                "qwen": "通义千问",
                "mistral": "Mistral",
                "phi": "Phi",
                "gemma": "Gemma",
                "function-calling": "函数调用",
                "instruction-tuned": "指令微调",
                "multilingual": "多语言",
            }
            if tag in tag_map:
                capability_tags.append(tag_map[tag])
        
        if capability_tags:
            parts.append(f"擅长领域：{', '.join(capability_tags)}。")
    
    # Quantization guide
    gguf_files = model_info.get("gguf_files", [])
    if gguf_files:
        quants = [f.get("quantization", "") for f in gguf_files]
        if quants:
            # Recommend the best quant
            recommended = "Q4_K_M"
            for rq in ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0", "Q4_K_S", "Q5_K_S", "Q4_0", "Q3_K_M"]:
                if rq in quants:
                    recommended = rq
                    break
            
            parts.append(f"提供{len(quants)}种量化规格(Q2~Q8)，推荐{recommended}版本在精度与体积间取得最佳平衡。")
            
            # Show size range
            sizes = [f.get("size_human", "") for f in gguf_files]
            if sizes:
                parts.append(f"文件大小范围：{min(sizes)} ~ {max(sizes)}。")
    
    # Downloads & popularity
    downloads = model_info.get("downloads", 0)
    likes = model_info.get("likes", 0)
    if downloads > 0:
        parts.append(f"已在HuggingFace获得{downloads:,}次下载，{likes:,}个点赞。")
    
    # Join and truncate to ~500 chars
    summary = " ".join(parts)
    
    # If too long, trim intelligently
    if len(summary) > 500:
        summary = summary[:497] + "..."
    
    return summary


def create_review_prompt(model_info: dict) -> str:
    """
    Create a prompt for the AI reviewer to assess this model.
    This tells the AI what to look at and what to decide.
    """
    repo_id = model_info.get("repo_id", "")
    model_name = model_info.get("model_name", "")
    author = model_info.get("author", "")
    tags = model_info.get("tags", [])
    downloads = model_info.get("downloads", 0)
    likes = model_info.get("likes", 0)
    gguf_files = model_info.get("gguf_files", [])
    
    # Build quantization summary
    quant_summary = "\n".join([
        f"  - {f['quantization']}: {f['size_human']} ({f['filename']})"
        for f in gguf_files
    ])
    
    prompt = f"""## 待审核模型

**模型名称**: {model_name}
**仓库ID**: {repo_id}
**作者**: {author}
**标签**: {', '.join(tags)}
**下载量**: {downloads:,}
**点赞数**: {likes:,}

### GGUF量化规格
{quant_summary}

### 原始描述
{model_info.get('description', '无')[:500] or '（无描述）'}

---

请完成以下审核任务：

1. **决定是否收录**：该模型是否有价值收录进日报？（是/否）
2. **中文翻译**：将模型描述翻译为中文
3. **能力介绍**：撰写一段500字以内的中文能力介绍，包括：
   - 模型基本信息（家族、参数量、架构特点）
   - 擅长领域和能力
   - 量化版本推荐建议
   - 适用场景

4. **风险评估**：是否存在安全问题（如unabliterated、恶意注入等）

请以JSON格式回复：
```json
{{
  "approve": true/false,
  "chinese_description": "中文翻译",
  "chinese_summary": "500字以内的能力介绍",
  "risk_level": "low/medium/high",
  "notes": "审核备注"
}}
```"""
    
    return prompt


def save_review_result(model_info: dict, review: dict) -> dict:
    """
    Save the AI review result into the model info.
    
    Args:
        model_info: Original model info from scraper
        review: Review result dict with keys:
            - approve: bool
            - chinese_description: str
            - chinese_summary: str
            - risk_level: str
            - notes: str
    
    Returns:
        Updated model_info dict
    """
    model_info["review"] = review
    
    if review.get("approve"):
        # Replace English description with Chinese
        model_info["description"] = review.get("chinese_description", model_info.get("description", ""))
        model_info["chinese_summary"] = review.get("chinese_summary", "")
        model_info["risk_level"] = review.get("risk_level", "low")
        model_info["review_notes"] = review.get("notes", "")
    
    return model_info


if __name__ == "__main__":
    # Test with sample data
    sample = {
        "repo_id": "test/Model-1",
        "model_name": "Test Model",
        "tags": ["llama", "text-generation", "chat"],
        "description": "A llama-based model for text generation and chat.",
        "downloads": 1000,
        "likes": 50,
        "gguf_files": [
            {"quantization": "Q4_K_M", "size_human": "4.2 GB", "filename": "model-Q4_K_M.gguf"},
            {"quantization": "Q8_0", "size_human": "8.1 GB", "filename": "model-Q8_0.gguf"},
        ],
    }
    
    summary = generate_chinese_summary(sample)
    print("Generated Summary:")
    print(summary)
    print(f"\nLength: {len(summary)} chars")
    
    prompt = create_review_prompt(sample)
    print("\nReview Prompt:")
    print(prompt[:500] + "...")
