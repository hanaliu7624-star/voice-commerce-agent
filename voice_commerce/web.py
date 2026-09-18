"""网页对话框：文字 + 浏览器麦克风 → CommerceAgent → TTS。

启动：
  python -m voice_commerce.web
然后打开 http://127.0.0.1:7860
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from voice_commerce.config import DEFAULT_CUSTOMER_ID
from voice_commerce.db import require_db
from voice_commerce.graph import CommerceAgent
from voice_commerce.speech import synthesize_speech_base64, transcribe_audio

logger = logging.getLogger("voice_commerce.web")

STATIC_DIR = Path(__file__).resolve().parent / "static"

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "7860"))

app = FastAPI(title="Voice Commerce Agent", version="0.2.0")

# session_id -> CommerceAgent
_sessions: dict[str, CommerceAgent] = {}


class SessionRequest(BaseModel):
    customer_id: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    customer_id: str
    greeting: str


class ChatRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1)
    speak: bool = True


class TurnResponse(BaseModel):
    session_id: str
    customer_id: str
    transcript: str | None = None
    answer: str
    intent: str
    action: str
    order_id: str | None = None
    trace_id: str
    confidence: float | None = None
    audio_base64: str | None = None
    audio_mime: str | None = None


def _get_agent(session_id: str) -> CommerceAgent:
    agent = _sessions.get(session_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="会话不存在，请刷新页面重新开始。")
    return agent


def _turn_payload(
    session_id: str,
    agent: CommerceAgent,
    result: Any,
    *,
    transcript: str | None = None,
    speak: bool = True,
) -> TurnResponse:
    answer = (result.final_answer or "").strip() or "我这边暂时没有查到可用信息，请再说一遍。"
    audio_b64 = None
    audio_mime = None
    if speak:
        try:
            audio_b64 = synthesize_speech_base64(answer)
            audio_mime = "audio/mpeg"
        except Exception as exc:  # noqa: BLE001 — Demo：TTS 失败仍返回文字
            logger.warning("TTS failed: %s", exc)
            audio_b64 = None
            audio_mime = None
    return TurnResponse(
        session_id=session_id,
        customer_id=agent.customer_id,
        transcript=transcript,
        answer=answer,
        intent=result.intent,
        action=result.action,
        order_id=result.entities.get("order_id"),
        trace_id=result.trace_id,
        confidence=getattr(result, "confidence", None),
        audio_base64=audio_b64,
        audio_mime=audio_mime,
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/session", response_model=SessionResponse)
def create_session(body: SessionRequest | None = None) -> SessionResponse:
    require_db()
    customer_id = (body.customer_id if body else None) or DEFAULT_CUSTOMER_ID
    session_id = uuid.uuid4().hex
    agent = CommerceAgent(customer_id=customer_id)
    _sessions[session_id] = agent
    greeting = (
        f"你好，我是电商客服助手。当前账号 {customer_id} 已登录。"
        "可以帮你查订单、物流、支付和退款。请打字或按住麦克风说话。"
    )
    return SessionResponse(session_id=session_id, customer_id=customer_id, greeting=greeting)


@app.post("/api/chat", response_model=TurnResponse)
def chat(body: ChatRequest) -> TurnResponse:
    require_db()
    agent = _get_agent(body.session_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="请输入问题。")
    try:
        result = agent.ask(text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat failed")
        raise HTTPException(status_code=502, detail=f"客服处理失败：{exc}") from exc
    return _turn_payload(body.session_id, agent, result, speak=body.speak)


@app.post("/api/voice", response_model=TurnResponse)
async def voice(
    session_id: str = Form(...),
    speak: bool = Form(True),
    audio: UploadFile = File(...),
) -> TurnResponse:
    require_db()
    agent = _get_agent(session_id)
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="没有收到录音，请重试。")
    filename = audio.filename or "audio.webm"
    try:
        transcript = transcribe_audio(raw, filename=filename, language="zh")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"语音识别失败：{exc}") from exc
    if not transcript:
        raise HTTPException(status_code=400, detail="没听清，请再说一遍。")
    try:
        result = agent.ask(transcript)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("voice ask failed")
        raise HTTPException(status_code=502, detail=f"客服处理失败：{exc}") from exc
    return _turn_payload(session_id, agent, result, transcript=transcript, speak=speak)


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="静态页面缺失。")
    return FileResponse(index_path)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    import logging

    import uvicorn

    from voice_commerce.config import ENV_PATH, LLM_API_KEY, require_api_key

    logging.basicConfig(level=logging.INFO)
    logging.info("项目 .env 路径: %s (存在=%s)", ENV_PATH, ENV_PATH.is_file())
    logging.info("LLM_API_KEY 已加载: %s (长度=%s)", bool(LLM_API_KEY), len(LLM_API_KEY or ""))
    require_api_key()  # 启动时立刻失败，避免打开网页后才报错
    require_db()
    uvicorn.run(
        "voice_commerce.web:app",
        host=WEB_HOST,
        port=WEB_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
