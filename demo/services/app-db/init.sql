CREATE TABLE IF NOT EXISTS inventory (
    sku TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO inventory (sku, quantity) VALUES ('SKU-CHECKOUT', 10000)
ON CONFLICT (sku) DO NOTHING;
