-- name: insert_collection
INSERT INTO tbcoll (
    name,
    amount,
    payment_mode,
    approver_name,
    approver_phone_number,
    wing,
    is_tenant,
    is_external,
    tenant_name,
    phone_number,
    transaction_id,
    receiver_name,
    receiver_phone_number
)
VALUES (
    :name,
    :amount,
    :payment_mode,
    :approver_name,
    :approver_phone_number,
    :wing,
    :is_tenant,
    :is_external,
    :tenant_name,
    :phone_number,
    :transaction_id,
    NULL,
    NULL
)

-- name: select_collections_history
SELECT
    name,
    phone_number,
    wing,
    is_tenant,
    is_external,
    amount
FROM tbhcoll
WHERE year = :year
ORDER BY id


