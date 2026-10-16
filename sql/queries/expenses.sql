-- Queries for tbexp. See users.sql for the conventions used here.
--
-- `password` is never present in any SELECT list: it is written on insert and
-- never read back out, so it cannot leak through a response.

-- name: insert_expense
INSERT INTO `tbexp` (expense_name, expense_category, description, amount, username, password)
VALUES (:expense_name, :expense_category, :description, :amount, :username, :password)

-- name: select_expenses
SELECT
    id,
    expense_name,
    expense_category,
    description,
    amount,
    username
FROM tbexp;

-- name: select_by_id
SELECT id, expense_name, expense_category, description, amount, username
FROM tbexp
WHERE id = :id

-- name: count_expenses
SELECT COUNT(*) AS total
FROM "tbexp"
WHERE (CAST(:expense_category AS VARCHAR) IS NULL OR expense_category = :expense_category)
  AND (CAST(:username AS VARCHAR) IS NULL OR username = :username)
  AND (CAST(:min_amount AS NUMERIC) IS NULL OR amount >= :min_amount)
  AND (CAST(:max_amount AS NUMERIC) IS NULL OR amount <= :max_amount)
  AND (CAST(:search AS VARCHAR) IS NULL
       OR LOWER(expense_name) LIKE LOWER(:search)
       OR LOWER(COALESCE(description, '')) LIKE LOWER(:search));

-- name: select_expense_by_id
SELECT id, expense_name, expense_category, description, amount, username
FROM "tbexp"
WHERE id = :id;

-- name: total_expenses
SELECT COALESCE(SUM(amount), 0) AS total_expense
FROM tbexp;

-- name: select_expenses_history
SELECT
    expense_name,
    description,
    amount
FROM tbhexp
WHERE year = :year
ORDER BY id
