# Demo investigation scenarios

These prompts exercise different investigation paths. They describe symptoms and queries without
telling the agent the cause or expected fix.

## Scenario A: customer order history

**Problem:** Customer support reports that loading a customer's recent order history becomes slow
as the order table grows.

```sql
SELECT id, status, total_cents, created_at
FROM orders
WHERE user_id = 1544
ORDER BY created_at DESC
LIMIT 25;
```

## Scenario B: inflated customer totals

**Problem:** This report sometimes shows order counts and revenue larger than the values displayed
on individual orders. Investigate whether the query returns the intended result.

```sql
SELECT
    u.id,
    u.email,
    count(o.id) AS order_count,
    sum(o.total_cents) AS lifetime_value_cents
FROM users AS u
JOIN orders AS o ON o.user_id = u.id
JOIN order_items AS oi ON oi.order_id = o.id
WHERE u.region = 'north'
GROUP BY u.id, u.email
ORDER BY lifetime_value_cents DESC
LIMIT 50;
```

## Scenario C: shipped-order operations queue

**Problem:** Operations uses this query to find the largest shipped orders, but the screen has
become slow even though it only displays 50 rows.

```sql
SELECT id, user_id, total_cents, created_at
FROM orders
WHERE status = 'shipped'
ORDER BY total_cents DESC
LIMIT 50;
```

Run each scenario through the normal investigation endpoint. Scenario labels are documentation
only and are never sent to the agent as special identifiers.

