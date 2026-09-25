BEGIN;

INSERT INTO users (email, full_name, region, created_at)
SELECT
    'user' || n || '@example.test',
    'Customer ' || n,
    (ARRAY['north', 'south', 'east', 'west'])[1 + (n % 4)],
    timestamptz '2022-01-01 00:00:00+00' + ((n * 37) % 730) * interval '1 day'
FROM generate_series(1, 20000) AS series(n);

INSERT INTO products (sku, name, category, price_cents, active, created_at)
SELECT
    'SKU-' || lpad(n::text, 6, '0'),
    'Product ' || n,
    (ARRAY['books', 'electronics', 'home', 'outdoors', 'toys'])[1 + (n % 5)],
    500 + ((n * 7919) % 150000),
    n % 20 <> 0,
    timestamptz '2021-01-01 00:00:00+00' + ((n * 13) % 900) * interval '1 day'
FROM generate_series(1, 5000) AS series(n);

INSERT INTO orders (user_id, status, total_cents, created_at)
SELECT
    1 + ((n * 1543) % 20000),
    (ARRAY['pending', 'paid', 'shipped', 'shipped', 'shipped', 'cancelled'])[1 + (n % 6)],
    1000 + ((n * 3571) % 250000),
    timestamptz '2023-01-01 00:00:00+00'
        + (n % 730) * interval '1 day'
        + (n % 86400) * interval '1 second'
FROM generate_series(1, 100000) AS series(n);

INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
SELECT
    order_number,
    1 + ((order_number * 97 + item_number * 997) % 5000),
    1 + ((order_number + item_number) % 4),
    500 + ((((order_number * 97 + item_number * 997)::bigint * 7919) % 150000)::integer)
FROM generate_series(1, 100000) AS orders(order_number)
CROSS JOIN generate_series(1, 3) AS items(item_number);

ANALYZE users;
ANALYZE products;
ANALYZE orders;
ANALYZE order_items;

COMMIT;
