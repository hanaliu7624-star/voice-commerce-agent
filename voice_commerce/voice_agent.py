"""LiveKit console 语音壳：ASR → CommerceAgent → TTS。

不改查单 / RAG 逻辑。用户说完一句后，直接调用现有 CommerceAgent.ask，
再把答案念出来。LiveKit 的 LLM 不参与业务回答。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    StopResponse,
    cli,
)
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins import openai, silero

from voice_commerce.config import (
    DEFAULT_CUSTOMER_ID,
    LLM_API_KEY,
    LLM_BASE_URL,
    require_api_key,
)
from voice_commerce.db import require_db
from voice_commerce.graph import CommerceAgent

logger = logging.getLogger("voice_commerce.voice")

STT_MODEL = os.getenv("STT_MODEL", "whisper-1")
TTS_MODEL = os.getenv("TTS_MODEL", "tts-1")
TTS_VOICE = os.getenv("TTS_VOICE", "alloy")


class VoiceCommerceAgent(Agent):
    def __init__(self, customer_id: str) -> None:
        super().__init__(
            instructions=(
                "你是电商语音客服的播报层。不要自行回答业务问题；"
                "所有订单、物流、退款、政策问题都由内部客服 Agent 处理。"
            ),
            llm=None,
        )
        self._customer_id = customer_id
        self._commerce = CommerceAgent(customer_id=customer_id)

    async def on_enter(self) -> None:
        await self.session.say(
            f"你好，我是电商客服助手。当前账号 {self._customer_id} 已登录。"
            "可以帮你查订单、物流、支付和退款。请直接说问题。"
        )

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        text = (new_message.text_content or "").strip()
        if not text:
            raise StopResponse()

        logger.info("user_utterance=%s", text)
        result = await asyncio.to_thread(self._commerce.ask, text)
        logger.info(
            "intent=%s action=%s order_id=%s trace=%s",
            result.intent,
            result.action,
            result.entities.get("order_id"),
            result.trace_id,
        )
        answer = (result.final_answer or "").strip() or "我这边暂时没有查到可用信息，请再说一遍。"
        await self.session.say(answer)
        raise StopResponse()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


def _build_session(vad) -> AgentSession:
    api_key = require_api_key()
    return AgentSession(
        vad=vad,
        stt=openai.STT(
            model=STT_MODEL,
            language="zh",
            base_url=LLM_BASE_URL,
            api_key=api_key,
        ),
        tts=openai.TTS(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            base_url=LLM_BASE_URL,
            api_key=api_key,
        ),
        llm=None,
    )


server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    require_db()
    customer_id = os.getenv("DEFAULT_CUSTOMER_ID", DEFAULT_CUSTOMER_ID)
    session = _build_session(ctx.proc.userdata["vad"])
    await session.start(agent=VoiceCommerceAgent(customer_id=customer_id), room=ctx.room)


def _smoke(query: str, customer_id: str) -> int:
    """不启麦克风：验证 CommerceAgent 接线 +（可选）TTS 合成。"""
    require_db()
    require_api_key()
    agent = CommerceAgent(customer_id=customer_id)
    result = agent.ask(query)
    print(f"intent={result.intent} action={result.action} order_id={result.entities.get('order_id')}")
    print(f"trace={result.trace_id}")
    print(result.final_answer)

    # 冒烟：确认 STT/TTS 插件能用当前网关初始化；TTS 合成一句短文本。
    async def _tts_ping() -> None:
        tts = openai.TTS(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
        )
        frame = await tts.synthesize("订单查询完成。").collect()
        print(f"tts_smoke_ok samples={frame.samples_per_channel} rate={frame.sample_rate} model={TTS_MODEL}")

    try:
        asyncio.run(_tts_ping())
    except Exception as exc:  # noqa: BLE001 — 冒烟要打印网关错误，不吞掉原因
        print(f"tts_smoke_failed: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--smoke":
        parser = argparse.ArgumentParser(description="语音壳冒烟（无麦克风）")
        parser.add_argument("--smoke", action="store_true")
        parser.add_argument("--query", default="我的最新订单在哪里？")
        parser.add_argument("--customer", default=DEFAULT_CUSTOMER_ID)
        args = parser.parse_args(argv)
        raise SystemExit(_smoke(args.query, args.customer))

    # LiveKit CLI：python -m voice_commerce.voice_agent console [--text]
    cli.run_app(server)


if __name__ == "__main__":
    main()
