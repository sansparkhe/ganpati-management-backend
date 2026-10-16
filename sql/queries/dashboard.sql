-- name: dashboard_stats
SELECT
    t.total_collections,
    t.total_expenses,
    t.total_collections - t.total_expenses AS balance
FROM (
    SELECT
        (SELECT COALESCE(SUM(amount), 0) FROM tbexp) AS total_expenses,
        (SELECT COALESCE(SUM(amount), 0)
           FROM tbcoll
          WHERE receiver_name IS NOT NULL
            AND receiver_phone_number IS NOT NULL) AS total_collections
) AS t;


