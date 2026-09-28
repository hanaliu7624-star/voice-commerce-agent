# Voice Commerce Agent

开源电商语音客服 Agent。中文、云 API、本地 SQLite 模拟业务。文字核（意图路由 / RAG / Tools）与网页对话框、LiveKit console 共用同一套 `CommerceAgent`。

## 原则

- RAG 负责规则，Tool 负责事实
- 模型不得编造 Tool 未返回的业务数据
- 用户只能查询自己的订单
- 每次回答写入 `traces/` JSON，可追溯 intent → 检索/工具 → 答案
- 语音壳只做 ASR/TTS，不改写业务答案

## ASR / TTS 是什么（白话）

这两件事只负责**声音和文字互转**，不负责查订单：

| 名词 | 人话 |
|---|---|
| **ASR / STT** | 把麦克风录音听写成文字（本项目用云端 `whisper-1`） |
| **TTS** | 把客服文字念成可播放的声音（本项目用云端 `tts-1`） |

网页路径：浏览器录音 → 上传到本机 FastAPI → Whisper 听写 → `CommerceAgent.ask` → TTS → 浏览器播放。  
麦克风需要 **localhost** 或 **HTTPS**（浏览器安全策略）；局域网 HTTP 可能不给麦，可改用文字。

## 准备

```bash
cd /path/to/voice-commerce-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -e ".[dev,web]"
# 若要用 LiveKit 本机 console，再装: pip install -e ".[voice]"
cp .env.example .env        # Windows: copy .env.example .env
```

在 `.env` 填入云 API Key。文字用 `LLM_MODEL` / `EMBEDDING_MODEL`；语音复用 `LLM_BASE_URL` / `LLM_API_KEY`，并配置 `STT_MODEL=whisper-1` / `TTS_MODEL=tts-1`。

## 网页对话框（推荐体验）

```bash
python scripts/generate_data.py --seed 42
python -m voice_commerce.cli --rebuild-index
python -m voice_commerce.web
```

浏览器打开 [http://127.0.0.1:7860](http://127.0.0.1:7860)：

- 打字发送，或**按住「按住说话」**录音、松开发送
- 回复会自动语音播报（可勾选「静音播报」）
- 气泡下方显示 `intent` / `trace`，可对照 `traces/` 目录

同一 WiFi 下同事可访问 `http://你的电脑局域网IP:7860`（本机防火墙需放行 7860）。  
**这是 Demo，不要无防护裸奔公网。** 若要临时给外网朋友试：本机先启动网页，再用 [ngrok](https://ngrok.com/) 等工具把 7860 映射成 HTTPS 链接（麦克风在 HTTPS 下可用）。

## 文字 CLI

```bash
python -m voice_commerce.cli --customer CUS10001
python -m voice_commerce.cli --query "我的最新订单在哪里？"
```

评测：`python eval/run_eval.py`  
单元测试：`pytest -q`

## 语音（LiveKit console，可选）

```bash
pip install -e ".[voice]"
python -m voice_commerce.voice_agent --smoke --query "我的最新订单在哪里？"
python -m voice_commerce.voice_agent console
python -m voice_commerce.voice_agent console --text
```

## 演示账号

用户 `CUS10001` 张三，固定订单：

| 订单 | 场景 |
|---|---|
| ORD10001 | 已发货，物流 DELAYED |
| ORD10002 | 最新单，支付 FAILED |
| ORD10003 | 已签收，退款 PROCESSING |
| ORD10004 | 已取消（问送达时间必须拒绝给 ETA） |
| ORD10005 | 历史已完成订单 |

CLI 里输入 `/trace` 查看上一轮追溯，`/quit` 退出。
