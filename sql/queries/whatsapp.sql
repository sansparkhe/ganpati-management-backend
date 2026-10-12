

--name: insert_whatsapp_job
INSERT INTO tbwhat (
    phone_number,
    name,
    created_at
)
VALUES (
    :phone_number,
    :name,
    CURRENT_TIMESTAMP
);

--name: select_whatsapp_job

SELECT
    id,
    phone_number,
    name,
    created_at,
    completed_at
FROM tbwhat
WHERE phone_number = :phone_number
  AND name = :name
  AND completed_at IS NULL;


