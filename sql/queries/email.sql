-- name: insert_reg_mail
INSERT INTO tbregmail (
    phone_number,
    first_name,
    email_id,
    last_name,
    date_of_birth,
    created_ts
)
VALUES (
    :phone_number,
    :first_name,
    :email_id,
    :last_name,
    :date_of_birth,
    CURRENT_TIMESTAMP
);


-- name: select_reg_mail
SELECT
    id,
    phone_number,
    first_name,
    last_name,
    date_of_birth,
    created_ts,
    completed_ts
FROM tbregmail
WHERE first_name = :first_name
  AND last_name = :last_name
  AND phone_number = :phone_number
  AND completed_ts IS NULL;


-- name: insert_apr_mail
INSERT INTO tbaprmail (
    receiver_name,
    receiver_phone,
    email_id,
    passcode,
    is_online,
    transaction_id,
    created_ts,
    expires_at
)
VALUES (
    :receiver_name,
    :receiver_phone,
    :email_id,
    :passcode,
    :is_online,
    :transaction_id, 
    CURRENT_TIMESTAMP,
    DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 2 HOUR));


-- name: validate_apr_code
SELECT
    passcode,
    expires_at
FROM tbaprmail
WHERE receiver_phone = :receiver_phone
  AND transaction_id = :transaction_id
  AND completed_ts IS NULL
  