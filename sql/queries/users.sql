-- Queries for TBUSER.
--
-- Loaded by app/sql_loader.py: each statement is addressed by the `-- name:`
-- marker directly above it, e.g. load("users", "insert_user").
--
-- Conventions used throughout this folder:
--   * Every value is a bound parameter (:name). No string interpolation, ever,
--     so none of these statements can be SQL-injected.
--   * Optional filters use the `(CAST(:p AS <type>) IS NULL OR col = :p)` idiom,
--     which lets one static statement serve every combination of filters. The
--     CAST is required: PostgreSQL rejects a bare `:p IS NULL` with
--     "could not determine data type of parameter". SQLite ignores it.
--   * Table names are double-quoted because they are uppercase; PostgreSQL
--     folds unquoted identifiers to lower case.
--   * LOWER(..) LIKE LOWER(..) rather than ILIKE, so the same SQL runs on both
--     PostgreSQL and the SQLite used by the tests.

-- name: insert_user
INSERT INTO "TBUSER" (first_name, last_name, phone_number, dob, email_id, admin_access)
VALUES (:first_name, :last_name, :phone_number, :dob, :email_id, :admin_access)
RETURNING id,
          first_name,
          last_name,
          first_name || ' ' || last_name AS full_name,
          phone_number,
          dob,
          email_id,
          admin_access;

-- name: select_users
SELECT id,
       first_name,
       last_name,
       first_name || ' ' || last_name AS full_name,
       phone_number,
       dob,
       email_id,
       admin_access
FROM "TBUSER"
WHERE (CAST(:admin_access AS BOOLEAN) IS NULL OR admin_access = :admin_access)
  AND (CAST(:search AS VARCHAR) IS NULL
       OR LOWER(first_name) LIKE LOWER(:search)
       OR LOWER(last_name) LIKE LOWER(:search)
       OR LOWER(email_id) LIKE LOWER(:search)
       OR LOWER(COALESCE(phone_number, '')) LIKE LOWER(:search))
ORDER BY id
LIMIT :limit OFFSET :skip;

-- name: count_users
SELECT COUNT(*) AS total
FROM "TBUSER"
WHERE (CAST(:admin_access AS BOOLEAN) IS NULL OR admin_access = :admin_access)
  AND (CAST(:search AS VARCHAR) IS NULL
       OR LOWER(first_name) LIKE LOWER(:search)
       OR LOWER(last_name) LIKE LOWER(:search)
       OR LOWER(email_id) LIKE LOWER(:search)
       OR LOWER(COALESCE(phone_number, '')) LIKE LOWER(:search));

-- name: select_user_by_id
SELECT id,
       first_name,
       last_name,
       first_name || ' ' || last_name AS full_name,
       phone_number,
       dob,
       email_id,
       admin_access
FROM "TBUSER"
WHERE id = :id;

-- name: select_user_id_by_email
SELECT id
FROM "TBUSER"
WHERE LOWER(email_id) = LOWER(:email_id);
