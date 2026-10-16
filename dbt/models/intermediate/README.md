# Intermediate

`int_<entity>_<verb>` models (for example `int_order_items_summed_to_orders`): joins, re-graining and isolated complex logic between staging and marts. Group into business-area folders (`intermediate/finance/`) once there are around 10 models. Properties go in `_int_<area>__models.yml`. Views in the `intermediate` dataset; not exposed to end users.

See [`docs/dbt-style-guide.md`](../../docs/dbt-style-guide.md).
