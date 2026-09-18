from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

# 先读项目根目录 .env；再读当前工作目录（防止从别的目录启动时漏读）
load_dotenv(ENV_PATH)
load_dotenv(Path.cwd() / ".env")

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


def _read_api_key() -> str:
    """读取 API Key。兼容 LLM_API_KEY / OPENAI_API_KEY，并去掉首尾空格与引号。"""
    raw = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    return raw.strip().strip('"').strip("'")


LLM_BASE_URL = normalize_openai_base_url(
    os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
)
LLM_API_KEY = _read_api_key()
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")


def require_api_key() -> str:
    key = _read_api_key()
    if key:
        return key

    env_exists = ENV_PATH.is_file()
    cwd_env = Path.cwd() / ".env"
    tips = [
        f"未设置 LLM_API_KEY。",
        f"程序在找：{ENV_PATH}",
        f"该文件存在：{'是' if env_exists else '否'}",
    ]
    if cwd_env.resolve() != ENV_PATH.resolve():
        tips.append(f"当前工作目录 .env：{cwd_env}（存在：{'是' if cwd_env.is_file() else '否'}）")
    if not env_exists:
        tips.append("请在项目根目录执行：copy .env.example .env  （或 cp .env.example .env）")
        tips.append("注意：文件名必须是 .env，不是 .env.txt，也不是只改了 .env.example。")
    else:
        tips.append("已找到 .env，但里面没有有效的 LLM_API_KEY=... 行。")
        tips.append("请确认等号右边有 Key、没有多余空格；改完后必须重启网页服务。")
    raise RuntimeError(" ".join(tips))
