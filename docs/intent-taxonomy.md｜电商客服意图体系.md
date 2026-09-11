# Voice Commerce Agent — Intent Taxonomy

## 1. Intent 分类

V1 分成 5 个大类：

```text
Order
Delivery
Payment
Refund / Return
Support
```

---

# 2. Order

### order_tracking

用户查询订单目前在哪里。

```text
Action = TOOL
Tool = get_order()
```

### order_status

用户询问订单当前状态。

```text
Action = TOOL
```

### order_history

查询历史订单。

```text
Action = TOOL
```

### order_cancellation

询问能否取消订单。

```text
Action = RAG + TOOL
```

---

# 3. Delivery

### delivery_status

查询物流状态。

```text
Action = TOOL
```

### delivery_eta

查询预计到达时间。

```text
Action = TOOL
```

### delivery_delay

询问配送为什么延迟。

```text
Action = TOOL + RAG
```

---

# 4. Payment

### payment_status

查询订单支付状态。

```text
Action = TOOL
```

### payment_failed

查询支付失败问题。

```text
Action = TOOL
```

### payment_policy

询问支付规则。

```text
Action = RAG
```

---

# 5. Refund / Return

### return_policy

询问退货规则。

```text
Action = RAG
```

### refund_policy

询问退款规则。

```text
Action = RAG
```

### refund_status

查询退款状态。

```text
Action = TOOL
```

### return_status

查询退货状态。

```text
Action = TOOL
```

---

# 6. Support

### complaint

用户投诉。

```text
Action = ESCALATION
```

### human_support

用户要求人工客服。

```text
Action = ESCALATION
```

### create_support_ticket

创建客服工单。

```text
Action = TOOL
```

---

# 7. 通用 Intent

### greeting

```text
Action = DIRECT
```

### help

```text
Action = DIRECT
```

### clarification

信息不足。

```text
Action = CLARIFICATION
```

### fallback

无法判断意图。

```text
Action = FALLBACK
```

---

# 8. Intent 判断原则

## 用户自己的数据优先于政策

> Where is my order?

→ `order_tracking`

而不是：

> shipping_policy

---

## 政策问题使用 RAG

> Can I return an item after 30 days?

→ `return_policy`

---

## 查询 + 解释使用 Tool + RAG

> Why is my refund still pending?

→ 查询退款状态  
→ 查询退款处理规则  
→ 综合回答

---

## 投诉直接转人工

> I want to complain about this order.

→ `complaint`

---

# 9. Intent Output

```json
{
  "intent": "order_tracking",
  "confidence": 0.95,
  "entities": {
    "order_id": null
  },
  "action": "TOOL"
}
```

---

# 10. Confidence

V1：

```text
>= 0.85
→ 执行

0.60–0.85
→ Clarification

< 0.60
→ Fallback / Escalation
```

阈值后续根据 Benchmark 调整。