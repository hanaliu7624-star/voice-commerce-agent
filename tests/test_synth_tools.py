from __future__ import annotations

from pathlib import Path

from voice_commerce.synth import generate
from voice_commerce.tools import get_customer_orders, get_delivery, get_order, get_refund, pick_latest_order_id


def test_fixtures_and_isolation(tmp_path: Path):
    db_path = tmp_path / "ecommerce.db"
    generate(seed=42, db_path=db_path)

    from voice_commerce.db import connect

    conn = connect(db_path)
    try:
        meta = dict(conn.execute("SELECT * FROM dataset_meta").fetchone())
        assert meta["seed"] == 42
        orders = get_customer_orders("CUS10001", conn=conn)
        ids = [row["order_id"] for row in orders]
        assert ids[0] == "ORD10002"
        assert set(ids) == {"ORD10001", "ORD10002", "ORD10003", "ORD10004", "ORD10005"}

        own = get_order("CUS10001", "ORD10001", conn=conn)
        assert own["found"] is True
        assert own["status"] == "SHIPPED"
        assert own["payment_status"] == "SUCCESS"

        leaked = get_order("CUS10002", "ORD10001", conn=conn)
        assert leaked["found"] is False

        delayed = get_delivery("CUS10001", "ORD10001", conn=conn)
        assert delayed["shipment"]["status"] == "DELAYED"

        refund = get_refund("CUS10001", "ORD10003", conn=conn)
        assert refund["refund"]["status"] == "PROCESSING"

        cancelled = get_order("CUS10001", "ORD10004", conn=conn)
        assert cancelled["status"] == "CANCELLED"
        assert cancelled["cancelled_at"]

        failed_pay = get_order("CUS10001", "ORD10002", conn=conn)
        assert failed_pay["status"] == "PENDING"
        assert failed_pay["payment_status"] == "FAILED"

        assert pick_latest_order_id("CUS10001", conn=conn) == "ORD10002"
        count = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
        assert count == 1000
    finally:
        conn.close()
