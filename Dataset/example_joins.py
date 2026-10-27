"""Example joins for the pharma inventory dataset. Run from the folder containing the CSV files."""
import pandas as pd

inv  = pd.read_csv("fact_inventory_daily.csv", parse_dates=["date"])
po   = pd.read_csv("fact_purchase_orders.csv", parse_dates=["order_date", "expected_delivery_date", "actual_delivery_date"])
ev   = pd.read_csv("fact_events.csv", parse_dates=["start_date", "end_date"])
sku  = pd.read_csv("dim_sku.csv")
wh   = pd.read_csv("dim_warehouse.csv")
sup  = pd.read_csv("dim_supplier.csv")
cal  = pd.read_csv("dim_calendar.csv", parse_dates=["date"])
dsw  = pd.read_csv("dim_sku_warehouse.csv")

# 1) Monthly demand by category and season (inventory + sku + calendar)
m = (inv.merge(sku[["sku_id", "category"]], on="sku_id")
        .merge(cal[["date", "year", "month", "indian_season"]], on="date"))
print(m.groupby(["category", "month"]).demand_qty.sum().unstack().round(0).head(), "\n")

# 2) Stockout rate by warehouse region and ABC-XYZ segment (inventory + warehouse + sku_warehouse)
s = (inv.merge(wh[["warehouse_id", "region"]], on="warehouse_id")
        .merge(dsw[["sku_wh_key", "abc_xyz_segment"]], on="sku_wh_key"))
print(s.pivot_table(index="abc_xyz_segment", columns="region", values="stockout_flag", aggfunc="mean").round(4), "\n")

# 3) Supplier performance: promised vs actual (purchase orders + supplier)
p = po[po.po_status == "Received"].merge(sup, on="supplier_id")
print(p.groupby("supplier_name").agg(orders=("po_number", "count"),
        promised_reliability=("delivery_reliability", "first"),
        actual_full_delivery=("is_short_shipped", lambda x: 1 - x.mean()),
        avg_delay_days=("delay_days", "mean"),
        late_share=("is_late", "mean")).round(3), "\n")

# 4) Follow an order to its delivery day in the daily table (PO -> inventory via received_po_number)
rec = inv.dropna(subset=["received_po_number"]).assign(po_number=lambda d: d.received_po_number.str.split(";")).explode("po_number")
chain = po.merge(rec[["po_number", "date", "receipts_qty", "closing_stock"]], on="po_number", how="left")
print(chain[["po_number", "order_date", "actual_delivery_date", "date", "ordered_qty", "received_qty", "receipts_qty"]].dropna().head(), "\n")

# 5) Lead-time impact of supplier disruption events (purchase orders + events)
d = ev[ev.event_type == "Supplier Disruption"][["event_id", "supplier_id", "start_date", "end_date"]]
x = po[po.po_status == "Received"].merge(d, on="supplier_id")
x = x[(x.order_date >= x.start_date) & (x.order_date <= x.end_date)]
print("Avg actual lead time during disruptions:", x.actual_lead_time_days.mean().round(1),
      "| outside:", po[(po.po_status == "Received") & (po.supplier_disruption_at_order == 0)].actual_lead_time_days.mean().round(1))
