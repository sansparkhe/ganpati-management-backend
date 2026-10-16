-- name: select_open_ledger
SELECT year
FROM tbhist
WHERE status = 'OPEN'
LIMIT 1
FOR UPDATE

-- name: insert_ledger
INSERT INTO tbhist (year, initiator_name, initiator_phone, status)
VALUES (:year, :initiator_name, :initiator_phone, 'OPEN')


-- name: insert_collections_history
INSERT INTO tbhcoll (name, phone_number, wing, is_tenant, is_external, amount, year)
SELECT name, phone_number, wing, is_tenant, is_external, amount, :year FROM tbcoll;

-- name: insert_expenses_history
INSERT INTO tbhexp (expense_name, description, amount, year)
SELECT expense_name, description, amount, :year FROM tbexp;

-- name: close_ledger  
UPDATE tbhist
SET total_collection = (SELECT COALESCE(SUM(amount), 0) FROM tbcoll),
    total_expense    = (SELECT COALESCE(SUM(amount), 0) FROM tbexp),
    status           = 'CLOSED'
WHERE year = :year;