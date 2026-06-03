-- Schéma démo pour workflow ETL (même instance PostgreSQL que l'API)
CREATE SCHEMA IF NOT EXISTS ora_demo;

DROP TABLE IF EXISTS ora_demo.transactions;
CREATE TABLE ora_demo.transactions (
    id SERIAL PRIMARY KEY,
    transaction_date DATE NOT NULL,
    client_email VARCHAR(255),
    client_name VARCHAR(120),
    iban VARCHAR(34),
    amount NUMERIC(14, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'EUR',
    category VARCHAR(64),
    country_code CHAR(2) DEFAULT 'FR'
);

INSERT INTO ora_demo.transactions (transaction_date, client_email, client_name, iban, amount, currency, category, country_code) VALUES
('2025-01-15', 'marie.dupont@banque-exemple.fr', 'Marie Dupont', 'FR7612345678901234567890123', 1250.50, 'EUR', 'virement', 'FR'),
('2025-01-16', 'jean.martin@credit-demo.fr', 'Jean Martin', 'FR7698765432109876543210987', 89.99, 'EUR', 'carte', 'FR'),
('2025-01-17', 'sophie.bernard@mail.fr', 'Sophie Bernard', 'FR7611112222333344445555666', 4500.00, 'EUR', 'virement', 'FR'),
('2025-01-18', 'pierre.leroy@banque-exemple.fr', 'Pierre Leroy', 'FR7622223333444455556666777', 320.00, 'USD', 'international', 'US'),
('2025-01-19', 'claire.petit@demo.fr', 'Claire Petit', 'FR7633334444555566667777888', 15600.75, 'EUR', 'salaire', 'FR'),
('2025-01-20', 'lucas.moreau@mail.fr', 'Lucas Moreau', 'FR7644445555666677778888999', 45.20, 'EUR', 'carte', 'FR'),
('2025-01-21', 'emma.garcia@exemple.es', 'Emma Garcia', 'ES9121000418450200051332', 2100.00, 'EUR', 'virement', 'ES'),
('2025-01-22', 'thomas.roux@banque.fr', 'Thomas Roux', 'FR7655556666777788889999000', 780.00, 'GBP', 'international', 'GB');
