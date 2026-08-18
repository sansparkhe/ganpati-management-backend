-- Queries for TBEXP. See users.sql for the conventions used here.
--
-- `password` is never present in any SELECT list: it is written on insert and
-- never read back out, so it cannot leak through a response.

-- name: insert_expense
INSERT INTO "TBEXP" (expense_name, expense_category, description, amount, username, password)
VALUES (:expense_name, :expense_category, :description, :amount, :username, :password)
RETURNING id, expense_name, expense_category, description, amount, username;

-- name: select_expenses
SELECT id, expense_name, expense_category, description, amount, username
FROM "TBEXP"
WHERE (CAST(:expense_category AS VARCHAR) IS NULL OR expense_category = :expense_category)
  AND (CAST(:username AS VARCHAR) IS NULL OR username = :username)
  AND (CAST(:min_amount AS NUMERIC) IS NULL OR amount >= :min_amount)
  AND (CAST(:max_amount AS NUMERIC) IS NULL OR amount <= :max_amount)
  AND (CAST(:search AS VARCHAR) IS NULL
       OR LOWER(expense_name) LIKE LOWER(:search)
       OR LOWER(COALESCE(description, '')) LIKE LOWER(:search))
ORDER BY id DESC
LIMIT :limit OFFSET :skip;

-- name: count_expenses
SELECT COUNT(*) AS total
FROM "TBEXP"
WHERE (CAST(:expense_category AS VARCHAR) IS NULL OR expense_category = :expense_category)
  AND (CAST(:username AS VARCHAR) IS NULL OR username = :username)
  AND (CAST(:min_amount AS NUMERIC) IS NULL OR amount >= :min_amount)
  AND (CAST(:max_amount AS NUMERIC) IS NULL OR amount <= :max_amount)
  AND (CAST(:search AS VARCHAR) IS NULL
       OR LOWER(expense_name) LIKE LOWER(:search)
       OR LOWER(COALESCE(description, '')) LIKE LOWER(:search));

-- name: select_expense_by_id
SELECT id, expense_name, expense_category, description, amount, username
FROM "TBEXP"
WHERE id = :id;

-- name: expense_totals
SELECT COALESCE(SUM(amount), 0) AS total_expenses,
       COUNT(*)                 AS expense_count,
       COALESCE(AVG(amount), 0) AS average_expense,
       COALESCE(MAX(amount), 0) AS highest_expense
FROM "TBEXP";

-- name: expense_totals_by_category
SELECT expense_category,
       SUM(amount) AS total,
       COUNT(*)    AS count
FROM "TBEXP"
GROUP BY expense_category
ORDER BY SUM(amount) DESC;
