# Voice Commerce Agent — 系统架构

## 1. 总体架构

```text
                         用户
                          │
                     🎙 语音输入
                          │
                          ▼
                     ASR / STT
                          │
                          ▼
                       文本
                          │
                          ▼
                  Intent Router
                          │
                          ▼
                 Agent Controller
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
         RAG             Tool        Human Escalation
          │               │
          ▼               ▼
     Knowledge Base   Synthetic DB
          │               │
          └───────┬───────┘
                  ▼
           Response Generator
                  │
                  ▼
                 TTS
                  │
                  ▼
              🔊 语音回复
```

---

# 2. ASR Layer

负责：

```text
Speech → Text
```

例如：

```text
"What happened to my order?"
```

转换成：

```text
What happened to my order?
```

ASR Provider 必须可替换。

---

# 3. Intent Router

将用户问题转换成结构化 Intent。

输出：

```json
{
  "intent": "order_tracking",
  "entities": {
    "order_id": null
  },
  "confidence": 0.95,
  "action": "TOOL"
}
```

---

# 4. Agent Controller

根据 Intent 决定：

```text
RAG
TOOL
RAG + TOOL
CLARIFICATION
ESCALATION
FALLBACK
```

例如：

### 政策类

```text
"Can I return an item?"
→ RAG
```

### 用户数据类

```text
"Where is my order?"
→ TOOL
```

### 混合类

```text
"Why hasn't my refund arrived yet?"
→ TOOL + RAG
```

---

# 5. RAG Layer

用于：

```text
Return Policy
Refund Policy
Shipping Policy
Payment Policy
Cancellation Policy
Customer Service Policy
```

流程：

```text
Query
 ↓
Embedding
 ↓
Vector Search
 ↓
Top-K
 ↓
Context
 ↓
LLM
```

检索结果必须保留：

```text
document_id
score
content
```

用于后续 Evaluation。

---

# 6. Tool Layer

工具只负责真实业务数据。

## Order

```text
get_order(order_id)
get_customer_orders(customer_id)
```

## Delivery

```text
get_delivery_status(order_id)
```

## Payment

```text
get_payment_status(order_id)
```

## Refund

```text
get_refund_status(order_id)
```

## Support

```text
create_support_ticket(customer_id, issue)
```

---

# 7. Synthetic E-commerce Environment

Agent 不连接真实电商系统。

使用：

```text
Customers
Products
Orders
Payments
Shipments
Refunds
Support Tickets
```

作为模拟业务环境。

---

# 8. Conversation Memory

保存短期上下文：

```json
{
  "active_intent": "order_tracking",
  "active_order_id": "ORD10025"
}
```

用于处理：

> Where is my order?

↓

> When will it arrive?

---

# 9. Guardrails

必须包括：

### 数据隔离

用户只能查询自己的订单。

### 防止幻觉

Tool 没有返回的信息不得生成。

### 写操作保护

涉及写操作时必须二次确认。

### Escalation

风险或不确定问题进入人工流程。

---

# 10. Agent Trace

每一次执行都生成：

```text
User Query
↓
Intent
↓
Entities
↓
Retrieved Documents
↓
Tool Call
↓
Tool Arguments
↓
Tool Result
↓
Final Answer
```

这是 Evaluation 的基础。

---

# 11. 模块化原则

Agent Core 不直接写死：

```text
order
refund
shipping
payment
```

业务配置放在：

```text
domain/
```

未来可以增加：

```text
travel
telecom
insurance
```

但 V1 只实现 E-commerce。