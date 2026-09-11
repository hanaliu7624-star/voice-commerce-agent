# Synthetic E-commerce Environment

## 1. 目标

建立一个完全虚拟、可控、可复现的电商业务环境，为 Agent 提供真实业务查询场景。

数据全部为 Synthetic Data。

不包含任何真实用户个人信息。

---

# 2. 核心实体

```text
Customer
Product
Order
Payment
Shipment
Refund
Support Ticket
```

---

# 3. Customer

```text
customer_id
name
language
country
created_at
```

---

# 4. Product

```text
product_id
name
category
price
currency
stock
status
```

Status：

```text
ACTIVE
INACTIVE
OUT_OF_STOCK
```

---

# 5. Order

```text
order_id
customer_id
product_id
quantity
amount
currency
status
created_at
shipped_at
delivered_at
cancelled_at
```

Status：

```text
PENDING
CONFIRMED
SHIPPED
DELIVERED
CANCELLED
RETURNED
```

规则：

```text
DELIVERED
→ delivered_at != NULL
```

```text
CANCELLED
→ cancelled_at != NULL
```

---

# 6. Payment

```text
payment_id
order_id
customer_id
amount
currency
method
status
created_at
completed_at
```

Status：

```text
PENDING
SUCCESS
FAILED
REFUNDED
```

Payment Method：

```text
CARD
WALLET
BANK_TRANSFER
CASH_ON_DELIVERY
```

---

# 7. Shipment

```text
shipment_id
order_id
carrier
tracking_number
status
estimated_delivery_date
actual_delivery_date
```

Status：

```text
PROCESSING
SHIPPED
IN_TRANSIT
OUT_FOR_DELIVERY
DELIVERED
DELAYED
```

---

# 8. Refund

```text
refund_id
order_id
customer_id
amount
currency
status
reason
created_at
completed_at
```

Status：

```text
REQUESTED
PROCESSING
COMPLETED
REJECTED
```

---

# 9. Support Ticket

```text
ticket_id
customer_id
order_id
issue_type
description
priority
status
created_at
resolved_at
```

Priority：

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Status：

```text
OPEN
IN_PROGRESS
RESOLVED
CLOSED
```

---

# 10. 必须设计的 Edge Cases

Synthetic Data 不能只是随机生成正常订单。

必须主动设计：

### Case 1 — 延迟订单

```text
order_status = SHIPPED
shipment_status = DELAYED
```

用户：

> Why is my order late?

---

### Case 2 — 支付失败

```text
payment_status = FAILED
order_status = PENDING
```

用户：

> Why did my payment fail?

---

### Case 3 — 退款处理中

```text
payment_status = REFUNDED
refund_status = PROCESSING
```

用户：

> Where is my refund?

---

### Case 4 — 已取消订单

```text
order_status = CANCELLED
```

用户：

> Can you tell me when my order will arrive?

Agent 应识别：

> 订单已经取消，不应该给出配送时间。

---

### Case 5 — 多订单

同一个用户拥有：

```text
ORD001
ORD002
ORD003
```

用户：

> Where is my latest order?

Agent 必须先判断：

```text
latest order
```

而不能随意返回任意订单。

---

# 11. 数据生成

使用：

```text
scripts/generate_data.py
```

支持：

```bash
python scripts/generate_data.py --seed 42
```

V1 建议：

```text
Customers       100
Products        200
Orders          1,000
Payments        1,000
Shipments       800
Refunds         300
Tickets         300
```

---

# 12. 数据可复现

保存：

```text
DATASET_VERSION
SEED
GENERATOR_VERSION
```

例如：

```json
{
  "dataset_version": "1.0",
  "seed": 42
}
```

确保 Evaluation 可以重复执行。

---

# 13. 数据库

V1：

```text
SQLite
```

原因：

- 本地无需部署数据库
- 开源项目容易运行
- 支持完整 SQL
- 适合 Demo 和 Evaluation

数据库结构：

```text
customers
products
orders
payments
shipments
refunds
support_tickets
```

---

# 14. 数据安全原则

仓库禁止提交：

- 真实姓名
- 手机号
- 邮箱
- 地址
- 银行卡信息
- 真实订单

所有数据均为虚拟数据。