CREATE DATABASE IF NOT EXISTS techshop;
USE techshop;

CREATE TABLE IF NOT EXISTS clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    telefono VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    precio DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pedidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(50) NOT NULL,
    total DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_pedidos_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

CREATE TABLE IF NOT EXISTS pedido_detalle (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_pedido_detalle_pedido
        FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
    CONSTRAINT fk_pedido_detalle_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
);

CREATE TABLE IF NOT EXISTS conversaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NULL,
    session_id VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL,
    mensaje TEXT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversaciones_cliente_id (cliente_id),
    INDEX idx_conversaciones_session_id (session_id),
    INDEX idx_conversaciones_fecha (fecha),
    CONSTRAINT fk_conversaciones_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

INSERT INTO clientes (nombre, email, telefono)
VALUES
    ('Ana Lopez', 'ana@example.com', '+51911111111'),
    ('Carlos Perez', 'carlos@example.com', '+51922222222')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO productos (nombre, descripcion, precio, stock, activo)
VALUES
    ('Laptop Pro X', 'Portátil premium para trabajo y estudio', 1200.00, 10, TRUE),
    ('Smartphone Y', 'Teléfono inteligente con gran cámara', 800.00, 15, TRUE),
    ('Auriculares Z', 'Auriculares inalámbricos con cancelación de ruido', 150.00, 30, TRUE),
    ('Tablet W', 'Tablet versátil para entretenimiento y productividad', 400.00, 12, TRUE)
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);
