"""Tax-lot cost basis (FIFO/LIFO/HIFO) + tax-loss-harvesting with wash-sale flag."""
from lucore.compute.taxlots import Lot, realized_gain, tlh_scan


def test_realized_gain_methods_differ():
    lots = [Lot(date="2024-01-01", quantity=10, price=100.0),
            Lot(date="2024-06-01", quantity=10, price=150.0)]
    # Sell 10 @ 200.
    assert realized_gain(lots, 10, 200.0, "fifo").realized_gain == 1000.0   # oldest @100
    assert realized_gain(lots, 10, 200.0, "lifo").realized_gain == 500.0    # newest @150
    assert realized_gain(lots, 10, 200.0, "hifo").realized_gain == 500.0    # highest cost @150


def test_hifo_distinct_from_lifo_when_old_lot_is_pricier():
    lots = [Lot(date="2024-01-01", quantity=10, price=150.0),  # old + expensive
            Lot(date="2024-06-01", quantity=10, price=100.0)]  # new + cheap
    assert realized_gain(lots, 10, 200.0, "lifo").realized_gain == 1000.0   # newest @100 → big gain
    assert realized_gain(lots, 10, 200.0, "hifo").realized_gain == 500.0    # highest @150 → min gain
    assert realized_gain(lots, 10, 200.0, "fifo").realized_gain == 500.0    # oldest @150


def test_realized_gain_partial_and_capped():
    lots = [Lot(date="2024-01-01", quantity=5, price=100.0)]
    r = realized_gain(lots, 10, 200.0, "fifo")  # only 5 available
    assert r.sold_qty == 5.0 and r.cost_basis == 500.0 and r.realized_gain == 500.0


def test_tlh_scan_flags_losses_and_wash_sale():
    positions = [
        {"symbol": "LOSS", "quantity": 10, "avg_cost": 100.0, "price": 80.0, "days_held": 60},
        {"symbol": "RECENT", "quantity": 5, "avg_cost": 50.0, "price": 40.0, "days_held": 10},
        {"symbol": "GAIN", "quantity": 10, "avg_cost": 100.0, "price": 120.0, "days_held": 200},
    ]
    r = tlh_scan(positions)
    syms = [c.symbol for c in r.candidates]
    assert syms == ["LOSS", "RECENT"]          # GAIN excluded; sorted by loss size
    assert r.total_harvestable_loss == 250.0    # 200 + 50
    loss = r.candidates[0]
    assert loss.unrealized_loss == 200.0 and loss.loss_pct == -20.0 and loss.wash_sale_risk is False
    recent = r.candidates[1]
    assert recent.wash_sale_risk is True and recent.note is not None
