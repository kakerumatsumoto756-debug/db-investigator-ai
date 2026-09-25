BEGIN;

CREATE TABLE users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    full_name text NOT NULL,
    region text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE products (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku text NOT NULL UNIQUE,
    name text NOT NULL,
    category text NOT NULL,
    price_cents integer NOT NULL CHECK (price_cents > 0),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    status text NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    total_cents integer NOT NULL CHECK (total_cents >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders(id),
    product_id bigint NOT NULL REFERENCES products(id),
    quantity smallint NOT NULL CHECK (quantity > 0),
    unit_price_cents integer NOT NULL CHECK (unit_price_cents > 0)
);

-- These support routine relationships while leaving realistic gaps for investigations.
CREATE INDEX idx_orders_created_at ON orders (created_at DESC);
CREATE INDEX idx_order_items_order_id ON order_items (order_id);
CREATE INDEX idx_order_items_product_id ON order_items (product_id);
CREATE INDEX idx_products_category ON products (category);

CREATE TABLE investigations (
    id uuid PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    problem text NOT NULL,
    submitted_sql text,
    events jsonb NOT NULL DEFAULT '[]'::jsonb,
    report jsonb,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;

