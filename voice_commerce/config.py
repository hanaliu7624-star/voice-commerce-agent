from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
TRACE_DIR = ROOT / "traces"
POLICY_DIR = ROOT / "domain" / "policies"
DB_PATH = DATA_DIR / "ecommerce.db"
INDEX_PATH = DATA_DIR / "policy_index.json"

DATASET_VERSION = "1.0"
GENERATOR_VERSION = "1.0"
DEFAULT_SEED = 42
DEFAULT_CUSTOMER_ID = os.getenv("DEFAULT_CUSTOMER_ID", "CUS10001")

def normalize_openai_base_url(url: str) -> str:
    """OpenAI SDK 会把 /chat/completions 接在 base_url 后面。

    网关首页（无 /v1）会返回 HTML，SDK 就会把响应当成字符串，
    触发 'str' object has no attribute 'choices'。
    """
    cleaned = (url or "").strip().rstrip("/")
    if cleaned.endswith("/v1"):
        return cleaned
    return f"{cleaned}/v1"


LLM_BASE_URL = normalize_openai_base_url(
    os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")


def require_api_key() -> str:
    if not LLM_API_KEY:
        raise RuntimeError("未设置 LLM_API_KEY。请复制 .env.example 为 .env 并填入云 API Key。")
    return LLM_API_KEY
