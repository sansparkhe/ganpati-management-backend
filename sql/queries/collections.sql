-- Queries for TBCOLL. See users.sql for the conventions used here.
--
-- `password` is never present in any SELECT list: it is written on insert and
-- never read back out, so it cannot leak through a response.
--
-- `paid_by` is derived in SQL rather than in Python, so every query that
-- returns a collection row agrees on who the money came from.

-- name: insert_collection
INSERT INTO "TBCOLL" (approved, in_queue, owner_name, is_tenant, tenant_name, phone_number,
                      amount, payment_mode, transaction_id, cash_held_by, username, password)
VALUES (:approved, :in_queue, :owner_name, :is_tenant, :tenant_name, :phone_number,
        :amount, :payment_mode, :transaction_id, :cash_held_by, :username, :password)
RETURNING id, approved, in_queue, owner_name, is_tenant, tenant_name, phone_number,
          amount, payment_mode, transaction_id, cash_held_by, username,
          CASE WHEN is_tenant AND tenant_name IS NOT NULL THEN tenant_name
               ELSE owner_name END AS paid_by;

-- name: select_collections
SELECT id, approved, in_queue, owner_name, is_tenant, tenant_name, phone_number,
       amount, payment_mode, transaction_id, cash_held_by, username,
       CASE WHEN is_tenant AND tenant_name IS NOT NULL THEN tenant_name
            ELSE owner_name END AS paid_by
FROM "TBCOLL"
WHERE (CAST(:approved AS BOOLEAN) IS NULL OR approved = :approved)
  AND (CAST(:in_queue AS BOOLEAN) IS NULL OR in_queue = :in_queue)
  AND (CAST(:is_tenant AS BOOLEAN) IS NULL OR is_tenant = :is_tenant)
  AND (CAST(:payment_mode AS VARCHAR) IS NULL OR payment_mode = :payment_mode)
  AND (CAST(:username AS VARCHAR) IS NULL OR username = :username)
  AND (CAST(:min_amount AS NUMERIC) IS NULL OR amount >= :min_amount)
  AND (CAST(:max_amount AS NUMERIC) IS NULL OR amount <= :max_amount)
  AND (CAST(:search AS VARCHAR) IS NULL
       OR LOWER(owner_name) LIKE LOWER(:search)
       OR LOWER(COALESCE(tenant_name, '')) LIKE LOWER(:search)
       OR LOWER(COALESCE(phone_number, '')) LIKE LOWER(:search)
       OR LOWER(COALESCE(transaction_id, '')) LIKE LOWER(:search))
ORDER BY id DESC
LIMIT :limit OFFSET :skip;

-- name: count_collections
SELECT COUNT(*) AS total
FROM "TBCOLL"
WHERE (CAST(:approved AS BOOLEAN) IS NULL OR approved = :approved)
  AND (CAST(:in_queue AS BOOLEAN) IS NULL OR in_queue = :in_queue)
  AND (CAST(:is_tenant AS BOOLEAN) IS NULL OR is_tenant = :is_tenant)
  AND (CAST(:payment_mode AS VARCHAR) IS NULL OR payment_mode = :payment_mode)
  AND (CAST(:username AS VARCHAR) IS NULL OR username = :username)
  AND (CAST(:min_amount AS NUMERIC) IS NULL OR amount >= :min_amount)
  AND (CAST(:max_amount AS NUMERIC) IS NULL OR amount <= :max_amount)
  AND (CAST(:search AS VARCHAR) IS NULL
       OR LOWER(owner_name) LIKE LOWER(:search)
       OR LOWER(COALESCE(tenant_name, '')) LIKE LOWER(:search)
       OR LOWER(COALESCE(phone_number, '')) LIKE LOWER(:search)
       OR LOWER(COALESCE(transaction_id, '')) LIKE LOWER(:search));

-- name: select_collection_by_id
SELECT id, approved, in_queue, owner_name, is_tenant, tenant_name, phone_number,
       amount, payment_mode, transaction_id, cash_held_by, username,
       CASE WHEN is_tenant AND tenant_name IS NOT NULL THEN tenant_name
            ELSE owner_name END AS paid_by
FROM "TBCOLL"
WHERE id = :id;

-- name: collection_totals
-- Only approved money counts as collected; the rest is reported as pending.
SELECT COALESCE(SUM(CASE WHEN approved THEN amount END), 0)     AS total_collection,
       COUNT(CASE WHEN approved THEN 1 END)                     AS collection_count,
       COALESCE(SUM(CASE WHEN NOT approved THEN amount END), 0) AS pending_amount,
       COUNT(CASE WHEN NOT approved THEN 1 END)                 AS pending_count,
       COUNT(CASE WHEN in_queue THEN 1 END)                     AS in_queue_count,
       COUNT(CASE WHEN is_tenant THEN 1 END)                    AS tenant_payment_count,
       COUNT(*)                                                 AS total_count
FROM "TBCOLL";

-- name: collection_totals_by_payment_mode
SELECT payment_mode,
       SUM(amount) AS total,
       COUNT(*)    AS count
FROM "TBCOLL"
WHERE approved
GROUP BY payment_mode
ORDER BY SUM(amount) DESC;

-- name: collection_cash_in_hand
-- Approved cash that has not been banked yet, grouped by who is holding it.
SELECT cash_held_by,
       SUM(amount) AS total,
       COUNT(*)    AS count
FROM "TBCOLL"
WHERE approved
  AND payment_mode = 'CASH'
  AND cash_held_by IS NOT NULL
GROUP BY cash_held_by
ORDER BY SUM(amount) DESC;

-- name: collection_top_contributors
SELECT owner_name,
       SUM(amount) AS total,
       COUNT(*)    AS count
FROM "TBCOLL"
WHERE approved
GROUP BY owner_name
ORDER BY SUM(amount) DESC
LIMIT :limit;
