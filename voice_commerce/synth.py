from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

from voice_commerce.config import DATASET_VERSION, DB_PATH, DEFAULT_SEED, GENERATOR_VERSION
from voice_commerce.db import connect, init_schema

SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨")
GIVEN = [
    "伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "洋", "艳",
    "勇", "军", "杰", "娟", "涛", "明", "超", "秀英", "霞", "平",
]
PRODUCTS_CATALOG = [
    ("无线降噪耳机", "数码", 299.0),
    ("机械键盘", "数码", 459.0),
    ("智能手表", "数码", 899.0),
    ("运动跑鞋", "服饰", 399.0),
    ("双层玻璃杯", "家居", 59.0),
    ("纯棉T恤", "服饰", 89.0),
    ("电动牙刷", "个护", 199.0),
    ("空气炸锅", "家电", 329.0),
    ("瑜伽垫", "运动", 79.0),
    ("蓝牙音箱", "数码", 159.0),
]
CARRIERS = ["顺丰", "京东物流", "中通", "圆通", "韵达"]
PAY_METHODS = ["CARD", "WALLET", "BANK_TRANSFER", "CASH_ON_DELIVERY"]
ORDER_STATUSES = ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]


def _dt(year: int, month: int, day: int, hour: int = 10) -> str:
    return datetime(year, month, day, hour, 0, 0).strftime("%Y-%m-%dT%H:%M:%S")


def generate(seed: int = DEFAULT_SEED, db_path: Path | None = None) -> Path:
    path = db_path or DB_PATH
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    conn = connect(path)
    init_schema(conn)

    customers = [_demo_customer()]
    for i in range(2, 101):
        customers.append(
            (
                f"CUS{10000 + i}",
                rng.choice(SURNAMES) + rng.choice(GIVEN),
                "zh",
                "CN",
                _dt(2025, rng.randint(1, 12), rng.randint(1, 28)),
            )
        )
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        customers,
    )

    products = []
    for i in range(1, 201):
        name, category, price = PRODUCTS_CATALOG[(i - 1) % len(PRODUCTS_CATALOG)]
        suffix = "" if i <= len(PRODUCTS_CATALOG) else f" {i}"
        status = "ACTIVE" if i % 17 else "OUT_OF_STOCK"
        products.append(
            (
                f"PRD{10000 + i}",
                f"{name}{suffix}",
                category,
                price + (i % 7) * 10,
                "CNY",
                0 if status == "OUT_OF_STOCK" else 20 + i % 50,
                status,
            )
        )
    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)",
        products,
    )

    fixture_orders, fixture_payments, fixture_shipments, fixture_refunds = _demo_fixtures()
    orders = list(fixture_orders)
    payments = list(fixture_payments)
    shipments = list(fixture_shipments)
    refunds = list(fixture_refunds)

    start_id = 10010
    target_orders = 1000
    other_customers = customers[1:]
    while len(orders) < target_orders:
        idx = start_id + len(orders)
        customer = other_customers[rng.randint(0, len(other_customers) - 1)]
        product = products[rng.randint(0, len(products) - 1)]
        created = datetime(2026, rng.randint(1, 8), rng.randint(1, 28), rng.randint(8, 20))
        status = rng.choice(ORDER_STATUSES)
        shipped_at = delivered_at = cancelled_at = None
        amount = round(product[3] * rng.choice([1, 1, 2]), 2)
        if status in {"SHIPPED", "DELIVERED", "RETURNED"}:
            shipped_at = (created + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        if status in {"DELIVERED", "RETURNED"}:
            delivered_at = (created + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%S")
        if status == "CANCELLED":
            cancelled_at = (created + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")
        order_id = f"ORD{idx}"
        orders.append(
            (
                order_id,
                customer[0],
                product[0],
                1,
                amount,
                "CNY",
                status,
                created.strftime("%Y-%m-%dT%H:%M:%S"),
                shipped_at,
                delivered_at,
                cancelled_at,
            )
        )
        pay_status = {
            "PENDING": "PENDING",
            "CONFIRMED": "SUCCESS",
            "SHIPPED": "SUCCESS",
            "DELIVERED": "SUCCESS",
            "CANCELLED": rng.choice(["SUCCESS", "FAILED"]),
            "RETURNED": "REFUNDED",
        }[status]
        payments.append(
            (
                f"PAY{idx}",
                order_id,
                customer[0],
                amount,
                "CNY",
                rng.choice(PAY_METHODS),
                pay_status,
                created.strftime("%Y-%m-%dT%H:%M:%S"),
                None if pay_status in {"PENDING", "FAILED"} else (created + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S"),
            )
        )
        if status in {"SHIPPED", "DELIVERED", "RETURNED"}:
            ship_status = "DELIVERED" if status in {"DELIVERED", "RETURNED"} else rng.choice(
                ["SHIPPED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELAYED"]
            )
            shipments.append(
                (
                    f"SHP{idx}",
                    order_id,
                    rng.choice(CARRIERS),
                    f"SF{idx}{rng.randint(1000, 9999)}",
                    ship_status,
                    (created + timedelta(days=5)).strftime("%Y-%m-%d"),
                    (created + timedelta(days=4)).strftime("%Y-%m-%d") if ship_status == "DELIVERED" else None,
                )
            )
        if status == "RETURNED" or pay_status == "REFUNDED":
            refunds.append(
                (
                    f"RFD{idx}",
                    order_id,
                    customer[0],
                    amount,
                    "CNY",
                    rng.choice(["REQUESTED", "PROCESSING", "COMPLETED"]),
                    "质量问题" if rng.random() < 0.3 else "不想要了",
                    (created + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%S"),
                    None,
                )
            )

    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        orders,
    )
    conn.executemany(
        "INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        payments,
    )
    conn.executemany(
        "INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?)",
        shipments,
    )
    conn.executemany(
        "INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        refunds,
    )
    conn.execute(
        "INSERT INTO dataset_meta VALUES (?, ?, ?)",
        (DATASET_VERSION, GENERATOR_VERSION, seed),
    )
    conn.commit()
    conn.close()
    return path


def _demo_customer() -> tuple:
    return ("CUS10001", "张三", "zh", "CN", _dt(2025, 3, 1))


def _demo_fixtures() -> tuple[list, list, list, list]:
    """CUS10001 的 5 个必测订单，对应文档 edge cases。"""
    orders = [
        (
            "ORD10001",
            "CUS10001",
            "PRD10001",
            1,
            299.0,
            "CNY",
            "SHIPPED",
            _dt(2026, 8, 28),
            _dt(2026, 8, 30),
            None,
            None,
        ),
        (
            "ORD10002",
            "CUS10001",
            "PRD10002",
            1,
            459.0,
            "CNY",
            "PENDING",
            _dt(2026, 9, 6),
            None,
            None,
            None,
        ),
        (
            "ORD10003",
            "CUS10001",
            "PRD10003",
            1,
            899.0,
            "CNY",
            "DELIVERED",
            _dt(2026, 8, 20),
            _dt(2026, 8, 21),
            _dt(2026, 8, 24),
            None,
        ),
        (
            "ORD10004",
            "CUS10001",
            "PRD10004",
            1,
            399.0,
            "CNY",
            "CANCELLED",
            _dt(2026, 8, 10),
            None,
            None,
            _dt(2026, 8, 10, 16),
        ),
        (
            "ORD10005",
            "CUS10001",
            "PRD10005",
            2,
            118.0,
            "CNY",
            "DELIVERED",
            _dt(2026, 7, 1),
            _dt(2026, 7, 2),
            _dt(2026, 7, 5),
            None,
        ),
    ]
    payments = [
        ("PAY10001", "ORD10001", "CUS10001", 299.0, "CNY", "WALLET", "SUCCESS", _dt(2026, 8, 28), _dt(2026, 8, 28, 11)),
        ("PAY10002", "ORD10002", "CUS10001", 459.0, "CNY", "CARD", "FAILED", _dt(2026, 9, 6), None),
        ("PAY10003", "ORD10003", "CUS10001", 899.0, "CNY", "CARD", "REFUNDED", _dt(2026, 8, 20), _dt(2026, 8, 20, 11)),
        ("PAY10004", "ORD10004", "CUS10001", 399.0, "CNY", "WALLET", "SUCCESS", _dt(2026, 8, 10), _dt(2026, 8, 10, 11)),
        ("PAY10005", "ORD10005", "CUS10001", 118.0, "CNY", "WALLET", "SUCCESS", _dt(2026, 7, 1), _dt(2026, 7, 1, 11)),
    ]
    shipments = [
        ("SHP10001", "ORD10001", "顺丰", "SF100011234", "DELAYED", "2026-09-05", None),
        ("SHP10003", "ORD10003", "京东物流", "JD10003321", "DELIVERED", "2026-08-24", "2026-08-24"),
        ("SHP10005", "ORD10005", "中通", "ZT10005555", "DELIVERED", "2026-07-05", "2026-07-05"),
    ]
    refunds = [
        (
            "RFD10003",
            "ORD10003",
            "CUS10001",
            899.0,
            "CNY",
            "PROCESSING",
            "尺寸不合适",
            _dt(2026, 8, 26),
            None,
        ),
    ]
    return orders, payments, shipments, refunds
