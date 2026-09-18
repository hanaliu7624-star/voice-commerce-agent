"""云端 ASR / TTS 辅助：不依赖 LiveKit，供网页与其它入口复用。"""

from __future__ import annotations

import base64
import io
import os
from typing import BinaryIO

from openai import OpenAI

from voice_commerce.config import LLM_API_KEY, LLM_BASE_URL, require_api_key

STT_MODEL = os.getenv("STT_MODEL", "whisper-1")
TTS_MODEL = os.getenv("TTS_MODEL", "tts-1")
TTS_VOICE = os.getenv("TTS_VOICE", "alloy")


def _client() -> OpenAI:
    return OpenAI(api_key=require_api_key(), base_url=LLM_BASE_URL)


def transcribe_audio(
    data: bytes | BinaryIO,
    *,
    filename: str = "audio.webm",
    language: str = "zh",
) -> str:
    """把录音字节转成中文文字（OpenAI 兼容 audio/transcriptions）。"""
    require_api_key()
    if isinstance(data, (bytes, bytearray)):
        file_obj: BinaryIO = io.BytesIO(bytes(data))
    else:
        file_obj = data
    # SDK 需要 (filename, file) 才能带扩展名推断格式
    result = _client().audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, file_obj),
        language=language,
    )
    text = getattr(result, "text", None) or str(result)
    return text.strip()


def synthesize_speech(text: str) -> bytes:
    """把文字合成 mp3 字节（OpenAI 兼容 audio/speech）。"""
    require_api_key()
    cleaned = (text or "").strip()
    if not cleaned:
        cleaned = "暂无内容。"
    # 语音播报过长时截断，避免超时；业务答案本身已要求短句
    if len(cleaned) > 800:
        cleaned = cleaned[:800] + "……"
    response = _client().audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=cleaned,
        response_format="mp3",
    )
    return response.content


def audio_to_base64(audio: bytes) -> str:
    return base64.b64encode(audio).decode("ascii")


def synthesize_speech_base64(text: str) -> str:
    return audio_to_base64(synthesize_speech(text))
