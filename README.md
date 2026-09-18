# Voice Commerce Agent

开源电商语音客服 Agent。中文、云 API、本地 SQLite 模拟业务。文字核（意图路由 / RAG / Tools）与 LiveKit 语音壳共用同一套 `CommerceAgent`。

## 原则

- RAG 负责规则，Tool 负责事实
- 模型不得编造 Tool 未返回的业务数据
- 用户只能查询自己的订单
- 每次回答写入 `traces/` JSON，可追溯 intent → 检索/工具 → 答案
- 语音壳只做 ASR/TTS，不改写业务答案

## 准备

```powershell
cd D:\ai\电商语音ai
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev,voice]"
copy .env.example .env
```

在 `.env` 填入云 API Key。默认走 OpenAI 兼容接口。文字模型用 `LLM_MODEL` / `EMBEDDING_MODEL`；语音复用同一 `LLM_BASE_URL` / `LLM_API_KEY`，并配置 `STT_MODEL=whisper-1` / `TTS_MODEL=tts-1`（网关需支持 `audio/transcriptions` 与 `audio/speech`）。

## 文字

```powershell
python scripts/generate_data.py --seed 42
python -m voice_commerce.cli --rebuild-index
python -m voice_commerce.cli --customer CUS10001
```

单轮：

```powershell
python -m voice_commerce.cli --query "我的最新订单在哪里？"
```

评测（会调用 LLM）：

```powershell
python eval/run_eval.py
```

不依赖模型的数据/工具测试：

```powershell
pytest -q
```

## 语音（LiveKit console）

无麦克风冒烟（跑一轮客服 + TTS 合成探针）：

```powershell
python -m voice_commerce.voice_agent --smoke --query "我的最新订单在哪里？"
```

本机麦克风 / 扬声器：

```powershell
python -m voice_commerce.voice_agent console
```

纯文本进语音管线（不采麦，适合排查）：

```powershell
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

交互里输入 `/trace` 查看上一轮追溯，`/quit` 退出。
