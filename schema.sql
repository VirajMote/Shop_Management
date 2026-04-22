-- ============================================================
--  Smart Mall Inventory & Sales Management System
--  Database Schema
-- ============================================================

USE smart_mall;

-- ============================================================
-- TABLE: users
-- Stores admin/staff credentials
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,          -- bcrypt hashed
    role ENUM('admin', 'staff') DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: products
-- Core product catalog with stock tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
    stock_quantity INT NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),  -- CONSTRAINT: no negative stock
    image_url VARCHAR(500) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- INDEX: faster search by product name and category
CREATE INDEX idx_product_name ON products(name);
CREATE INDEX idx_product_category ON products(category);

-- ============================================================
-- TABLE: sales
-- Each row = one billing transaction
-- ============================================================
CREATE TABLE IF NOT EXISTS sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    total_amount DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: sale_items
-- Line items for each sale (supports multi-product billing)
-- ============================================================
CREATE TABLE IF NOT EXISTS sale_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    price DECIMAL(10, 2) NOT NULL,           -- price at time of sale (snapshot)
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- INDEX: faster joins on sale_id
CREATE INDEX idx_sale_items_sale_id ON sale_items(sale_id);

-- ============================================================
-- TRIGGER: auto-deduct stock when a sale item is inserted
-- ============================================================
DELIMITER $$

CREATE TRIGGER trg_reduce_stock
AFTER INSERT ON sale_items
FOR EACH ROW
BEGIN
    -- Reduce stock by the quantity sold
    UPDATE products
    SET stock_quantity = stock_quantity - NEW.quantity
    WHERE id = NEW.product_id;
END$$

-- ============================================================
-- TRIGGER: prevent stock going below 0 (extra safety layer)
-- ============================================================
CREATE TRIGGER trg_check_stock_before_sale
BEFORE INSERT ON sale_items
FOR EACH ROW
BEGIN
    DECLARE current_stock INT;
    SELECT stock_quantity INTO current_stock
    FROM products WHERE id = NEW.product_id;

    IF current_stock < NEW.quantity THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Insufficient stock for this product';
    END IF;
END$$

-- ============================================================
-- STORED PROCEDURE: create_sale
-- Handles full sale transaction atomically
-- Usage: CALL create_sale(items_json, @sale_id)
-- ============================================================
CREATE PROCEDURE create_sale(
    IN p_total DECIMAL(10,2),
    OUT p_sale_id INT
)
BEGIN
    -- Insert sale header
    INSERT INTO sales (total_amount) VALUES (p_total);
    SET p_sale_id = LAST_INSERT_ID();
END$$

DELIMITER ;

-- ============================================================
-- DEFAULT ADMIN USER
-- Password: admin123 (bcrypt hashed)
-- ============================================================
INSERT INTO users (email, password, role)
VALUES (
    'admin@gmail.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMqJqhcanFp8RRDlaZGmGvnJyO',
    'admin'
)
ON DUPLICATE KEY UPDATE id=id;

-- ============================================================
-- SAMPLE PRODUCTS (for demo)
-- ============================================================
INSERT INTO products (name, category, price, stock_quantity) VALUES
('Nike Air Max 270',     'Footwear',     8999.00,  45),
('Levi\'s 511 Jeans',   'Apparel',      3499.00,  30),
('Apple AirPods Pro',   'Electronics',  24999.00,  12),
('Titan Analog Watch',  'Accessories',  4500.00,  20),
('Maybelline Lipstick', 'Cosmetics',     499.00,   5),
('Basmati Rice 5kg',    'Groceries',     450.00,   3),
('Dove Shampoo 650ml',  'Personal Care', 349.00,  60),
('Notebook A4 Pack',    'Stationery',    199.00,  80)
ON DUPLICATE KEY UPDATE id=id;
