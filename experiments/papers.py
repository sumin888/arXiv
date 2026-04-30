"""30 arXiv papers across diverse domains used as agent instances in HW8 experiments."""

PAPERS = [
    # ── Transformers / Attention ─────────────────────────────────────────────
    {"id": "1706.03762", "domain": "NLP",        "title": "Attention Is All You Need"},
    {"id": "1810.04805", "domain": "NLP",        "title": "BERT"},
    {"id": "2010.11929", "domain": "Vision",     "title": "An Image is Worth 16x16 Words (ViT)"},
    {"id": "2209.01188", "domain": "Systems",    "title": "FlashAttention"},
    {"id": "2307.08621", "domain": "NLP",        "title": "LongLoRA"},

    # ── Large Language Models ────────────────────────────────────────────────
    {"id": "2005.14165", "domain": "NLP",        "title": "Language Models are Few-Shot Learners (GPT-3)"},
    {"id": "2302.13971", "domain": "NLP",        "title": "LLaMA"},
    {"id": "2307.09288", "domain": "NLP",        "title": "LLaMA 2"},
    {"id": "2204.02311", "domain": "NLP",        "title": "PaLM"},
    {"id": "2205.01068", "domain": "NLP",        "title": "Training Compute-Optimal LLMs (Chinchilla)"},

    # ── Reasoning / Agents ───────────────────────────────────────────────────
    {"id": "2201.11903", "domain": "Reasoning",  "title": "Chain-of-Thought Prompting"},
    {"id": "2210.11610", "domain": "Agents",     "title": "ReAct"},
    {"id": "2210.03629", "domain": "Reasoning",  "title": "Self-Consistency"},
    {"id": "2302.04761", "domain": "Agents",     "title": "Toolformer"},
    {"id": "2203.02155", "domain": "Alignment",  "title": "InstructGPT (RLHF)"},

    # ── Multimodal ───────────────────────────────────────────────────────────
    {"id": "2103.00020", "domain": "Multimodal", "title": "CLIP"},
    {"id": "2304.08485", "domain": "Multimodal", "title": "LLaVA"},
    {"id": "2301.12597", "domain": "Multimodal", "title": "BLIP-2"},
    {"id": "2103.14030", "domain": "Vision",     "title": "Swin Transformer"},
    {"id": "2005.12872", "domain": "Vision",     "title": "DETR"},

    # ── Generative Models ────────────────────────────────────────────────────
    {"id": "2112.10752", "domain": "Generative", "title": "Latent Diffusion Models"},
    {"id": "1406.2661",  "domain": "Generative", "title": "Generative Adversarial Networks (GAN)"},
    {"id": "1312.6114",  "domain": "Generative", "title": "Auto-Encoding Variational Bayes (VAE)"},
    {"id": "2210.09477", "domain": "Generative", "title": "Imagic"},
    {"id": "2211.09800", "domain": "Generative", "title": "InstructPix2Pix"},

    # ── Optimization / Training ──────────────────────────────────────────────
    {"id": "1412.6980",  "domain": "Optimization", "title": "Adam Optimizer"},
    {"id": "1607.06450", "domain": "Optimization", "title": "Layer Normalization"},
    {"id": "1512.03385", "domain": "Vision",     "title": "Deep Residual Learning (ResNet)"},

    # ── Biology / Science ────────────────────────────────────────────────────
    {"id": "2108.01398", "domain": "Biology",    "title": "ESM: Evolutionary Scale Modeling"},
    {"id": "2202.05924", "domain": "Code",       "title": "Competition-Level Code Generation (AlphaCode)"},
]

assert len(PAPERS) == 30, f"Expected 30 papers, got {len(PAPERS)}"

# Three question types used across experiments
QUESTIONS = {
    "factual":       "What is the main contribution of this paper in one sentence?",
    "methodological":"Walk me through the core method or architecture step by step.",
    "comparative":   "How does this work differ from or improve on prior approaches?",
}
