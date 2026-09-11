# Voice Commerce Agent

## 1. 项目概述

### 1.1 项目名称

**Voice Commerce Agent**

### 1.2 项目定位

一个开源的电商语音客服 Agent。

用户通过自然语言进行语音提问，Agent 自动完成：

```text
语音输入
→ 语音识别
→ 用户意图识别
→ 知识检索 / 业务数据查询
→ 答案生成
→ 语音回复
```

项目重点研究：

- 语音客服交互
- Agent Workflow
- RAG
- Tool Calling
- Business Rules
- Conversation Memory
- Agent Evaluation

---

# 2. 目标用户

### C 端用户

需要查询订单、物流、退款、退货等信息的消费者。

### B 端用户

希望研究或搭建 AI 客服 Agent 的：

- AI 产品经理
- AI Agent 开发者
- AI 应用研究者
- 电商客服团队

---

# 3. 用户痛点

传统电商客服存在大量重复性问题：

```text
我的订单在哪里？
什么时候送到？
可以取消订单吗？
退款什么时候到账？
这个商品可以退吗？
为什么我的付款失败？
```

这些问题往往具有：

- 高频
- 规则明确
- 数据结构化
- 可自动查询

等特点，因此适合 Agent 自动处理。

---

# 4. 产品目标

V1 实现：

### 4.1 语音问答

用户通过自然语言直接提问。

例如：

> "Where is my order?"

---

### 4.2 意图识别

将用户问题识别成标准 Intent。

例如：

```json
{
  "intent": "order_tracking",
  "confidence": 0.96
}
```

---

### 4.3 知识问答

针对政策类问题使用 RAG。

例如：

> "Can I return an item after 30 days?"

查询：

```text
return_policy
```

---

### 4.4 业务数据查询

针对用户个人信息使用 Tool。

例如：

> "Where is my order?"

调用：

```text
get_order()
```

---

### 4.5 多轮对话

用户：

> Where is my order?

Agent：

> Your order is currently in transit.

用户：

> When will it arrive?

Agent 应理解：

```text
"it" = 当前正在讨论的订单
```

而不是重新开始判断。

---

### 4.6 人工升级

以下情况不应由 Agent 强行回答：

- 用户强烈投诉
- 高风险支付问题
- 无法确定用户意图
- 信息不足
- 需要人工审批
- 用户要求人工客服

---

# 5. V1 支持场景

## Order

- 查询订单
- 查询订单状态
- 查询订单历史
- 取消订单

## Delivery

- 查询物流状态
- 查询预计到达时间
- 配送延迟

## Payment

- 支付失败
- 支付状态
- 支付政策

## Refund / Return

- 退货政策
- 退款政策
- 退款状态
- 退货状态

## Customer Support

- 创建客服工单
- 投诉
- 转人工

---

# 6. 产品边界

V1 不支持：

- 自动退款
- 自动取消真实订单
- 自动修改地址
- 自动支付
- 自动执行不可逆操作

Tool 默认只提供：

```text
READ
```

能力。

涉及写操作时：

```text
Agent
→ 用户确认
→ Tool
→ 执行
```

V1 可以先不实现真实写操作。

---

# 7. 核心信息来源

Agent 使用三种信息来源：

## Knowledge Base

回答稳定的业务规则：

```text
退货政策
退款政策
配送规则
支付政策
售后规则
```

## Business Tools

回答动态用户信息：

```text
订单
物流
支付
退款
```

## Human Escalation

处理：

```text
投诉
高风险
不确定
超出能力边界
```

---

# 8. 最核心产品原则

### 原则 1

**RAG 负责规则，Tool 负责事实。**

### 原则 2

**LLM 不得生成 Tool 中不存在的业务事实。**

### 原则 3

**LLM 不得自行改变业务规则。**

### 原则 4

**信息不足时必须询问或升级。**

### 原则 5

**Agent 的结果必须可追溯。**

每次回答都能够追溯：

```text
Intent
→ Knowledge
→ Tool
→ Data
→ Final Answer
```

---

# 9. V1 成功标准

完整实现：

```text
✓ Voice Input
✓ ASR
✓ Intent Routing
✓ RAG
✓ Tool Calling
✓ Synthetic E-commerce Environment
✓ Conversation Memory
✓ Guardrails
✓ Human Escalation
✓ TTS
✓ Agent Evaluation
```

并支持：

```text
本地运行
数据可重复生成
Benchmark 可重复执行
Agent Trace 可查看
```