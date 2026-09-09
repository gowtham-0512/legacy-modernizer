-- Legacy Relational Database Schema
-- Database: legacy_company_db

CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    department VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed Data
INSERT INTO departments (name) VALUES ('Engineering'), ('Marketing'), ('Finance');

INSERT INTO users (name, email, department) VALUES
('Alice Johnson', 'alice.johnson@example.com', 'Engineering'),
('Bob Smith', 'bob.smith@example.com', 'Marketing'),
('Charlie Brown', 'charlie.brown@example.com', 'Finance');
