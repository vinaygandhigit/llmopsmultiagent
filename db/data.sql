CREATE TABLE IF NOT EXISTS accounts (
    account_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number  TEXT UNIQUE NOT NULL,
    customer_name   TEXT NOT NULL,
    account_type    TEXT NOT NULL CHECK (account_type IN ('SAVINGS', 'CURRENT', 'FIXED_DEPOSIT')),
    balance         REAL NOT NULL DEFAULT 0,
    currency        TEXT NOT NULL DEFAULT 'USD',
    branch          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'CLOSED')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 50 sample records
INSERT OR IGNORE INTO accounts (account_number, customer_name, account_type, balance, currency, branch, status) VALUES
('ACC10001', 'John Smith', 'SAVINGS', 15230.50, 'USD', 'Downtown', 'ACTIVE'),
('ACC10002', 'Emma Johnson', 'CURRENT', 8420.75, 'USD', 'Uptown', 'ACTIVE'),
('ACC10003', 'Michael Brown', 'SAVINGS', 32100.00, 'USD', 'Downtown', 'ACTIVE'),
('ACC10004', 'Olivia Davis', 'FIXED_DEPOSIT', 50000.00, 'USD', 'Westside', 'ACTIVE'),
('ACC10005', 'William Miller', 'CURRENT', 1230.20, 'USD', 'Eastside', 'ACTIVE'),
('ACC10006', 'Ava Wilson', 'SAVINGS', 7600.10, 'USD', 'Downtown', 'ACTIVE'),
('ACC10007', 'James Moore', 'CURRENT', 4321.00, 'USD', 'Uptown', 'INACTIVE'),
('ACC10008', 'Sophia Taylor', 'SAVINGS', 91234.45, 'USD', 'Westside', 'ACTIVE'),
('ACC10009', 'Benjamin Anderson', 'FIXED_DEPOSIT', 25000.00, 'USD', 'Eastside', 'ACTIVE'),
('ACC10010', 'Isabella Thomas', 'CURRENT', 560.35, 'USD', 'Downtown', 'ACTIVE'),
('ACC10011', 'Lucas Jackson', 'SAVINGS', 12000.00, 'USD', 'Uptown', 'ACTIVE'),
('ACC10012', 'Mia White', 'CURRENT', 3300.60, 'USD', 'Westside', 'ACTIVE'),
('ACC10013', 'Henry Harris', 'SAVINGS', 45000.90, 'USD', 'Eastside', 'ACTIVE'),
('ACC10014', 'Charlotte Martin', 'FIXED_DEPOSIT', 100000.00, 'USD', 'Downtown', 'ACTIVE'),
('ACC10015', 'Alexander Thompson', 'CURRENT', 780.00, 'USD', 'Uptown', 'CLOSED'),
('ACC10016', 'Amelia Garcia', 'SAVINGS', 6540.25, 'USD', 'Westside', 'ACTIVE'),
('ACC10017', 'Daniel Martinez', 'CURRENT', 990.15, 'USD', 'Eastside', 'ACTIVE'),
('ACC10018', 'Harper Robinson', 'SAVINGS', 23400.00, 'USD', 'Downtown', 'ACTIVE'),
('ACC10019', 'Matthew Clark', 'FIXED_DEPOSIT', 75000.00, 'USD', 'Uptown', 'ACTIVE'),
('ACC10020', 'Evelyn Rodriguez', 'CURRENT', 1500.75, 'USD', 'Westside', 'ACTIVE'),
('ACC10021', 'Joseph Lewis', 'SAVINGS', 8900.40, 'USD', 'Eastside', 'INACTIVE'),
('ACC10022', 'Abigail Lee', 'CURRENT', 2200.00, 'USD', 'Downtown', 'ACTIVE'),
('ACC10023', 'David Walker', 'SAVINGS', 15600.55, 'USD', 'Uptown', 'ACTIVE'),
('ACC10024', 'Emily Hall', 'FIXED_DEPOSIT', 30000.00, 'USD', 'Westside', 'ACTIVE'),
('ACC10025', 'Christopher Allen', 'CURRENT', 430.20, 'USD', 'Eastside', 'ACTIVE'),
('ACC10026', 'Elizabeth Young', 'SAVINGS', 71000.00, 'USD', 'Downtown', 'ACTIVE'),
('ACC10027', 'Andrew Hernandez', 'CURRENT', 6600.10, 'USD', 'Uptown', 'ACTIVE'),
('ACC10028', 'Sofia King', 'SAVINGS', 9800.00, 'USD', 'Westside', 'ACTIVE'),
('ACC10029', 'Joshua Wright', 'FIXED_DEPOSIT', 40000.00, 'USD', 'Eastside', 'CLOSED'),
('ACC10030', 'Avery Lopez', 'CURRENT', 3120.65, 'USD', 'Downtown', 'ACTIVE'),
('ACC10031', 'Ryan Hill', 'SAVINGS', 5400.00, 'USD', 'Uptown', 'ACTIVE'),
('ACC10032', 'Ella Scott', 'CURRENT', 890.30, 'USD', 'Westside', 'ACTIVE'),
('ACC10033', 'Nathan Green', 'SAVINGS', 22300.00, 'USD', 'Eastside', 'ACTIVE'),
('ACC10034', 'Scarlett Adams', 'FIXED_DEPOSIT', 60000.00, 'USD', 'Downtown', 'ACTIVE'),
('ACC10035', 'Samuel Baker', 'CURRENT', 1750.45, 'USD', 'Uptown', 'INACTIVE'),
('ACC10036', 'Grace Gonzalez', 'SAVINGS', 33000.00, 'USD', 'Westside', 'ACTIVE'),
('ACC10037', 'Tyler Nelson', 'CURRENT', 2100.90, 'USD', 'Eastside', 'ACTIVE'),
('ACC10038', 'Chloe Carter', 'SAVINGS', 18700.20, 'USD', 'Downtown', 'ACTIVE'),
('ACC10039', 'Aaron Mitchell', 'FIXED_DEPOSIT', 85000.00, 'USD', 'Uptown', 'ACTIVE'),
('ACC10040', 'Victoria Perez', 'CURRENT', 640.00, 'USD', 'Westside', 'ACTIVE'),
('ACC10041', 'Jack Roberts', 'SAVINGS', 27600.75, 'USD', 'Eastside', 'ACTIVE'),
('ACC10042', 'Zoey Turner', 'CURRENT', 4890.10, 'USD', 'Downtown', 'ACTIVE'),
('ACC10043', 'Gabriel Phillips', 'SAVINGS', 11200.00, 'USD', 'Uptown', 'CLOSED'),
('ACC10044', 'Lily Campbell', 'FIXED_DEPOSIT', 20000.00, 'USD', 'Westside', 'ACTIVE'),
('ACC10045', 'Logan Parker', 'CURRENT', 3300.00, 'USD', 'Eastside', 'ACTIVE'),
('ACC10046', 'Hannah Evans', 'SAVINGS', 9200.40, 'USD', 'Downtown', 'ACTIVE'),
('ACC10047', 'Caleb Edwards', 'CURRENT', 1230.00, 'USD', 'Uptown', 'ACTIVE'),
('ACC10048', 'Aria Collins', 'SAVINGS', 46000.60, 'USD', 'Westside', 'ACTIVE'),
('ACC10049', 'Isaac Stewart', 'FIXED_DEPOSIT', 55000.00, 'USD', 'Eastside', 'ACTIVE'),
('ACC10050', 'Layla Sanchez', 'CURRENT', 2870.85, 'USD', 'Downtown', 'ACTIVE');

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number   TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('CREDIT', 'DEBIT')),
    amount           REAL NOT NULL CHECK (amount >= 0),
    description      TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    balance_after    REAL NOT NULL,
    FOREIGN KEY (account_number) REFERENCES accounts (account_number)
);

CREATE TABLE IF NOT EXISTS statements (
    statement_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number   TEXT NOT NULL,
    period_start     TEXT NOT NULL,
    period_end       TEXT NOT NULL,
    opening_balance  REAL NOT NULL,
    closing_balance  REAL NOT NULL,
    generated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (account_number) REFERENCES accounts (account_number)
);

CREATE TABLE IF NOT EXISTS address_updates (
    address_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number   TEXT NOT NULL,
    current_address  TEXT NOT NULL,
    requested_address TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    requested_at     TEXT NOT NULL,
    FOREIGN KEY (account_number) REFERENCES accounts (account_number)
);

CREATE TABLE IF NOT EXISTS kyc_updates (
    kyc_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number   TEXT NOT NULL,
    kyc_status       TEXT NOT NULL CHECK (kyc_status IN ('PENDING', 'VERIFIED', 'EXPIRED', 'REJECTED')),
    remarks          TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    FOREIGN KEY (account_number) REFERENCES accounts (account_number)
);

CREATE TABLE IF NOT EXISTS cheque_book_requests (
    request_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number   TEXT NOT NULL,
    leaves           INTEGER NOT NULL CHECK (leaves IN (25, 50, 100)),
    request_status   TEXT NOT NULL CHECK (request_status IN ('REQUESTED', 'PROCESSING', 'DELIVERED', 'REJECTED')),
    requested_at     TEXT NOT NULL,
    delivered_at     TEXT,
    FOREIGN KEY (account_number) REFERENCES accounts (account_number)
);

INSERT OR IGNORE INTO transactions
    (transaction_id, account_number, transaction_type, amount, description, transaction_date, balance_after)
VALUES
    (1, 'ACC10001', 'CREDIT', 2500.00, 'Salary credit', '2026-08-01 09:15:00', 15351.00),
    (2, 'ACC10001', 'DEBIT', 120.50, 'Utility payment', '2026-08-05 14:20:00', 15230.50),
    (3, 'ACC10002', 'CREDIT', 850.00, 'Customer payment', '2026-08-03 11:00:00', 8420.75);

INSERT OR IGNORE INTO statements
    (statement_id, account_number, period_start, period_end, opening_balance, closing_balance)
VALUES
    (1, 'ACC10001', '2026-07-01', '2026-07-31', 12851.00, 15230.50),
    (2, 'ACC10002', '2026-07-01', '2026-07-31', 7570.75, 8420.75);

INSERT OR IGNORE INTO address_updates
    (address_id, account_number, current_address, requested_address, status, requested_at)
VALUES
    (1, 'ACC10001', '12 Main Street, Downtown', '45 Lake Road, Downtown', 'APPROVED', '2026-08-10 10:30:00'),
    (2, 'ACC10002', '8 High Street, Uptown', '22 Park Avenue, Uptown', 'PENDING', '2026-08-12 15:00:00');

INSERT OR IGNORE INTO kyc_updates
    (kyc_id, account_number, kyc_status, remarks, updated_at)
VALUES
    (1, 'ACC10001', 'VERIFIED', 'Identity documents verified', '2026-07-20 09:00:00'),
    (2, 'ACC10002', 'PENDING', 'Awaiting proof of address', '2026-08-11 13:45:00');

INSERT OR IGNORE INTO cheque_book_requests
    (request_id, account_number, leaves, request_status, requested_at, delivered_at)
VALUES
    (1, 'ACC10001', 50, 'DELIVERED', '2026-07-25 12:00:00', '2026-07-30 16:10:00'),
    (2, 'ACC10002', 25, 'PROCESSING', '2026-08-13 10:15:00', NULL);

-- Additional sample records: IDs 3-50 give every requested table 50 rows.
WITH RECURSIVE numbers(id) AS (
    SELECT 3
    UNION ALL
    SELECT id + 1 FROM numbers WHERE id < 50
)
INSERT OR IGNORE INTO transactions
    (transaction_id, account_number, transaction_type, amount, description, transaction_date, balance_after)
SELECT
    id,
    printf('ACC1%04d', ((id - 1) % 50) + 1),
    CASE WHEN id % 2 = 0 THEN 'DEBIT' ELSE 'CREDIT' END,
    75.00 + (id * 10.00),
    CASE WHEN id % 2 = 0 THEN 'Online purchase' ELSE 'Funds transfer' END,
    printf('2026-%02d-%02d 10:00:00', ((id - 3) % 8) + 1, ((id - 3) % 27) + 1),
    10000.00 + (id * 125.00)
FROM numbers;

WITH RECURSIVE numbers(id) AS (
    SELECT 3
    UNION ALL
    SELECT id + 1 FROM numbers WHERE id < 50
)
INSERT OR IGNORE INTO statements
    (statement_id, account_number, period_start, period_end, opening_balance, closing_balance)
SELECT
    id,
    printf('ACC1%04d', ((id - 1) % 50) + 1),
    printf('2026-%02d-01', ((id - 3) % 8) + 1),
    printf('2026-%02d-28', ((id - 3) % 8) + 1),
    9000.00 + (id * 100.00),
    10000.00 + (id * 125.00)
FROM numbers;

WITH RECURSIVE numbers(id) AS (
    SELECT 3
    UNION ALL
    SELECT id + 1 FROM numbers WHERE id < 50
)
INSERT OR IGNORE INTO address_updates
    (address_id, account_number, current_address, requested_address, status, requested_at)
SELECT
    id,
    printf('ACC1%04d', ((id - 1) % 50) + 1),
    printf('%d Main Street, Branch %d', id, ((id - 3) % 4) + 1),
    printf('%d Park Avenue, Branch %d', id + 10, ((id - 3) % 4) + 1),
    CASE id % 3 WHEN 0 THEN 'PENDING' WHEN 1 THEN 'APPROVED' ELSE 'REJECTED' END,
    printf('2026-08-%02d 11:00:00', ((id - 3) % 20) + 1)
FROM numbers;

WITH RECURSIVE numbers(id) AS (
    SELECT 3
    UNION ALL
    SELECT id + 1 FROM numbers WHERE id < 50
)
INSERT OR IGNORE INTO kyc_updates
    (kyc_id, account_number, kyc_status, remarks, updated_at)
SELECT
    id,
    printf('ACC1%04d', ((id - 1) % 50) + 1),
    CASE id % 4 WHEN 0 THEN 'PENDING' WHEN 1 THEN 'VERIFIED' WHEN 2 THEN 'EXPIRED' ELSE 'REJECTED' END,
    CASE id % 4 WHEN 0 THEN 'Documents under review' WHEN 1 THEN 'Identity documents verified'
        WHEN 2 THEN 'KYC renewal required' ELSE 'Document verification failed' END,
    printf('2026-08-%02d 12:00:00', ((id - 3) % 20) + 1)
FROM numbers;

WITH RECURSIVE numbers(id) AS (
    SELECT 3
    UNION ALL
    SELECT id + 1 FROM numbers WHERE id < 50
)
INSERT OR IGNORE INTO cheque_book_requests
    (request_id, account_number, leaves, request_status, requested_at, delivered_at)
SELECT
    id,
    printf('ACC1%04d', ((id - 1) % 50) + 1),
    CASE WHEN id % 3 = 0 THEN 100 WHEN id % 2 = 0 THEN 25 ELSE 50 END,
    CASE id % 4 WHEN 0 THEN 'REQUESTED' WHEN 1 THEN 'PROCESSING' WHEN 2 THEN 'DELIVERED' ELSE 'REJECTED' END,
    printf('2026-08-%02d 13:00:00', ((id - 3) % 20) + 1),
    CASE WHEN id % 4 = 2 THEN printf('2026-08-%02d 15:00:00', ((id - 3) % 20) + 2) ELSE NULL END
FROM numbers;