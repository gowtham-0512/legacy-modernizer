-- Standalone Legacy Relational Database Fixture
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_total DECIMAL(10, 2) NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING',
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
) ENGINE=InnoDB;

INSERT INTO customers (first_name, last_name, email, phone) VALUES
('John', 'Doe', 'john.doe@example.com', '555-0199'),
('Jane', 'Roe', 'jane.roe@example.com', '555-0200');

INSERT INTO orders (customer_id, order_total, status) VALUES
(1, 149.99, 'COMPLETED'),
(2, 89.50, 'PENDING');
