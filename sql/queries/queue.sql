-- name: insert_queue_item
INSERT INTO tbqueue (
    name,
    phone_number,
    is_tenant,
    wing,
    is_external,
    amount,
    payment_mode,
    approver_name,
    approver_phone_number,
    receiver_name,
    receiver_phone_number,
    status
)
VALUES (
    :name,
    :phone_number,
    :is_tenant,
    :wing,
    :is_external,
    :amount,
    :payment_mode,
    :approver_name,
    :approver_phone_number,
    NULL,
    NULL,
    'pending'
)

-- name: approve_queue_item
UPDATE tbqueue
SET status = 'approved'
WHERE name = :name
  AND phone_number = :phone_number
  AND status = 'pending'