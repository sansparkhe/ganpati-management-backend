-- name: insert_user

INSERT INTO `tbuser` (
    first_name,
    last_name,
    phone_number,
    dob,
    email_id,
    admin_access
)
VALUES (
    :first_name,
    :last_name,
    :phone_number,
    :dob,
    :email_id,
    :admin_access
);

-- name: select_inserted_user

SELECT
    id,
    first_name,
    last_name,
    CONCAT(first_name, ' ', last_name) AS full_name,
    phone_number,
    dob,
    email_id,
    admin_access
FROM `tbuser`
WHERE id = LAST_INSERT_ID();


-- name: select_users

SELECT
    id,
    first_name,
    last_name,
    CONCAT(first_name, ' ', last_name) AS full_name,
    phone_number,
    dob,
    email_id,
    admin_access
FROM `tbuser`
ORDER BY id;


-- name: count_users

SELECT COUNT(*) AS total
FROM `tbuser`
WHERE (
    :admin_access IS NULL
    OR admin_access = :admin_access
)
AND (
    :search IS NULL
    OR LOWER(first_name) LIKE LOWER(:search)
    OR LOWER(last_name) LIKE LOWER(:search)
    OR LOWER(email_id) LIKE LOWER(:search)
    OR LOWER(COALESCE(phone_number, '')) LIKE LOWER(:search)
);


-- name: select_user_by_id

SELECT
    id,
    first_name,
    last_name,
    CONCAT(first_name, ' ', last_name) AS full_name,
    phone_number,
    dob,
    email_id,
    admin_access
FROM `tbuser`
WHERE id = :id;

-- name: validate_admin
SELECT
    id,
    first_name,
    last_name,
    CONCAT(first_name, ' ', last_name) AS full_name,
    phone_number,
    dob,
    email_id,
    admin_access
FROM `tbuser`
WHERE first_name = :initiator_name
AND phone_number = :initiator_number
