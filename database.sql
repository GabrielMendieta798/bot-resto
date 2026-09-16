-- =====================================================
-- RESTAURANT BOT - DATABASE SCHEMA
-- PostgreSQL
-- =====================================================


-- =========================
-- CUSTOMERS
-- =========================

CREATE TABLE customers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    phone VARCHAR(30) NOT NULL UNIQUE,

    name VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================
-- MENU ITEMS
-- =========================

CREATE TABLE menu_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    category VARCHAR(100) NOT NULL,

    name VARCHAR(150) NOT NULL,

    description TEXT,

    price NUMERIC(12, 2) NOT NULL,

    estimated_time_min INTEGER,

    available BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_menu_item_price
        CHECK (price >= 0),

    CONSTRAINT chk_estimated_time
        CHECK (
            estimated_time_min IS NULL
            OR estimated_time_min >= 0
        )
);


-- =========================
-- ORDERS
-- =========================

CREATE TABLE orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    customer_id BIGINT NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'RECEIVED',

    delivery_type VARCHAR(20) NOT NULL,

    delivery_address TEXT,

    total NUMERIC(12, 2) NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id),

    CONSTRAINT chk_order_total
        CHECK (total >= 0),

    CONSTRAINT chk_order_status
        CHECK (
            status IN (
                'RECEIVED',
                'PREPARING',
                'READY',
                'ON_THE_WAY',
                'DELIVERED',
                'CANCELLED'
            )
        ),

    CONSTRAINT chk_delivery_type
        CHECK (
            delivery_type IN (
                'DELIVERY',
                'PICKUP'
            )
        ),

    CONSTRAINT chk_delivery_address
        CHECK (
            delivery_type <> 'DELIVERY'
            OR delivery_address IS NOT NULL
        )
);


-- =========================
-- ORDER ITEMS
-- =========================

CREATE TABLE order_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    order_id BIGINT NOT NULL,

    menu_item_id BIGINT NOT NULL,

    quantity INTEGER NOT NULL,

    unit_price_snapshot NUMERIC(12, 2) NOT NULL,

    notes TEXT,

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_order_items_menu_item
        FOREIGN KEY (menu_item_id)
        REFERENCES menu_items(id),

    CONSTRAINT chk_order_item_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_order_item_price
        CHECK (unit_price_snapshot >= 0)
);


-- =========================
-- CONVERSATIONS
-- =========================

CREATE TABLE conversations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    customer_id BIGINT NOT NULL UNIQUE,

    state VARCHAR(50) NOT NULL DEFAULT 'MAIN_MENU',

    active_flow VARCHAR(30),

    current_order_id BIGINT,

    handoff_active BOOLEAN NOT NULL DEFAULT FALSE,

    last_interaction TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_conversations_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_conversations_current_order
        FOREIGN KEY (current_order_id)
        REFERENCES orders(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_active_flow
        CHECK (
            active_flow IS NULL
            OR active_flow IN (
                'ORDER',
                'RESERVATION'
            )
        )
);


-- =========================
-- RESERVATIONS
-- =========================

CREATE TABLE reservations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    customer_id BIGINT NOT NULL,

    reservation_date DATE NOT NULL,

    reservation_time TIME NOT NULL,

    people INTEGER NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'REQUESTED',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_reservations_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id),

    CONSTRAINT chk_reservation_people
        CHECK (people > 0),

    CONSTRAINT chk_reservation_status
        CHECK (
            status IN (
                'REQUESTED',
                'CONFIRMED',
                'REJECTED',
                'CANCELLED'
            )
        )
);


-- =========================
-- INDEXES
-- =========================

CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

CREATE INDEX idx_orders_status
    ON orders(status);

CREATE INDEX idx_orders_created_at
    ON orders(created_at);

CREATE INDEX idx_order_items_order_id
    ON order_items(order_id);

CREATE INDEX idx_reservations_customer_id
    ON reservations(customer_id);

CREATE INDEX idx_reservations_date
    ON reservations(reservation_date);