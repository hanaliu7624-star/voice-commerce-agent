from __future__ import annotations

import sqlite3
from typing import Any

from voice_commerce.db import require_db


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cur.fetchall()]


def get_customer_orders(customer_id: str, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    own = conn or require_db()
    try:
        cur = own.execute(
            """
            SELECT o.*, p.name AS product_name
            FROM orders o
            JOIN products p ON p.product_id = o.product_id
            WHERE o.customer_id = ?
            ORDER BY o.created_at DESC
            """,
            (customer_id,),
        )
        return _rows(cur)
    finally:
        if conn is None:
            own.close()


def get_order(customer_id: str, order_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    own = conn or require_db()
    try:
        cur = own.execute(
            """
            SELECT
                o.*,
                p.name AS product_name,
                pay.payment_id,
                pay.method AS payment_method,
                pay.status AS payment_status
            FROM orders o
            JOIN products p ON p.product_id = o.product_id
            LEFT JOIN payments pay ON pay.order_id = o.order_id
            WHERE o.order_id = ? AND o.customer_id = ?
            """,
            (order_id, customer_id),
        )
        row = cur.fetchone()
        if row is None:
            return {"found": False, "order_id": order_id, "reason": "订单不存在或不属于当前用户"}
        data = dict(row)
        data["found"] = True
        return data
    finally:
        if conn is None:
            own.close()


def get_delivery(customer_id: str, order_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    own = conn or require_db()
    try:
        order = get_order(customer_id, order_id, conn=own)
        if not order.get("found"):
            return order
        cur = own.execute(
            "SELECT * FROM shipments WHERE order_id = ?",
            (order_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {
                "found": True,
                "order_id": order_id,
                "order_status": order["status"],
                "shipment": None,
                "reason": "该订单尚无物流单",
            }
        return {
            "found": True,
            "order_id": order_id,
            "order_status": order["status"],
            "shipment": dict(row),
        }
    finally:
        if conn is None:
            own.close()


def get_refund(customer_id: str, order_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    own = conn or require_db()
    try:
        order = get_order(customer_id, order_id, conn=own)
        if not order.get("found"):
            return order
        cur = own.execute(
            "SELECT * FROM refunds WHERE order_id = ? AND customer_id = ?",
            (order_id, customer_id),
        )
        row = cur.fetchone()
        if row is None:
            return {
                "found": True,
                "order_id": order_id,
                "order_status": order["status"],
                "refund": None,
                "reason": "该订单没有退款单",
            }
        return {
            "found": True,
            "order_id": order_id,
            "order_status": order["status"],
            "refund": dict(row),
        }
    finally:
        if conn is None:
            own.close()


def get_customer_refunds(customer_id: str, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    own = conn or require_db()
    try:
        cur = own.execute(
            "SELECT * FROM refunds WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        )
        return _rows(cur)
    finally:
        if conn is None:
            own.close()


def pick_latest_order_id(customer_id: str, conn: sqlite3.Connection | None = None) -> str | None:
    orders = get_customer_orders(customer_id, conn=conn)
    if not orders:
        return None
    return orders[0]["order_id"]
