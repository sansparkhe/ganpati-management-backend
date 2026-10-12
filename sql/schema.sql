-- tbexp
CREATE TABLE IF NOT EXISTS tbexp (
    id                INT             NOT NULL AUTO_INCREMENT,
    expense_name      VARCHAR(160)    NOT NULL,
    expense_category  VARCHAR(50)     NOT NULL,
    amount            DECIMAL(12, 2)  NOT NULL,
    name              VARCHAR(60)     NOT NULL,
    phone_number      VARCHAR(128)    NOT NULL,
    description       TEXT            NULL,

    PRIMARY KEY (id),
    CONSTRAINT ck_tbexp_amount_positive CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbcoll 
CREATE TABLE IF NOT EXISTS tbcoll (
    id                      INT             NOT NULL AUTO_INCREMENT,
    name                    VARCHAR(120)    NOT NULL,
    amount                  DECIMAL(12, 2)  NOT NULL,
    payment_mode            VARCHAR(50)     NOT NULL,
    approver_name           VARCHAR(60)     NOT NULL,
    approver_phone_number   VARCHAR(20)     NULL,
    wing                    VARCHAR(20)     NULL,
    is_tenant               BOOLEAN         NOT NULL DEFAULT FALSE,
    is_external             BOOLEAN         NOT NULL DEFAULT FALSE,
    tenant_name             VARCHAR(120)    NULL,
    phone_number            VARCHAR(20)     NULL,
    transaction_id          VARCHAR(64)     NULL,
    receiver_name           VARCHAR(120)    NULL,
    receiver_phone_number   VARCHAR(20)     NULL,

    PRIMARY KEY (id),
    CONSTRAINT ck_tbcoll_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_tbcoll_tenant_name_required_when_is_tenant
        CHECK (is_tenant = 0 OR tenant_name IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbregmail
CREATE TABLE IF NOT EXISTS tbregmail (
    id             INT           NOT NULL AUTO_INCREMENT,
    phone_number   VARCHAR(20)   NOT NULL,
    first_name     VARCHAR(160)  NOT NULL,
    last_name      VARCHAR(160)  NOT NULL,
    date_of_birth  VARCHAR(10)   NULL,
    email_id       VARCHAR(160)  NOT NULL,
    created_ts     VARCHAR(32)   NOT NULL DEFAULT (REPLACE(NOW(), ' ', 'T')),
    completed_ts   VARCHAR(32)   NULL,

    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbaprmail
CREATE TABLE IF NOT EXISTS tbaprmail (
    id              INT           NOT NULL AUTO_INCREMENT,
    receiver_name   VARCHAR(160)  NOT NULL,
    receiver_phone  VARCHAR(20)   NOT NULL,
	email_id       VARCHAR(160)  NOT NULL,
    is_online       VARCHAR(5)    NULL,
    passcode        VARCHAR(20)   NOT NULL,
    transaction_id  VARCHAR(160)  NOT NULL,
    expires_at      DATETIME      NOT NULL,
    created_ts      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_ts    DATETIME      NULL,

    PRIMARY KEY (id),
    CONSTRAINT ck_tbaprmail_is_online_valid
        CHECK (is_online IS NULL OR is_online IN ('true', 'false'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbqueue
CREATE TABLE IF NOT EXISTS tbqueue (
    id                      INT             NOT NULL AUTO_INCREMENT,
    name                    VARCHAR(160)    NOT NULL,
    phone_number            VARCHAR(20)     NULL,
    is_tenant               BOOLEAN         NOT NULL DEFAULT FALSE,
    wing                    VARCHAR(20)     NOT NULL,
    is_external             BOOLEAN         NOT NULL DEFAULT FALSE,
    amount                  DECIMAL(12, 2)  NOT NULL,
    payment_mode            VARCHAR(50)     NOT NULL,
    approver_name           VARCHAR(160)    NULL,
    approver_phone_number   VARCHAR(20)     NULL,
    receiver_name           VARCHAR(160)    NULL,
    receiver_phone_number   VARCHAR(20)     NULL,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'pending',

    PRIMARY KEY (id),
    CONSTRAINT ck_tbqueue_amount_positive CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbuser
CREATE TABLE IF NOT EXISTS tbuser (
    id             INT           NOT NULL AUTO_INCREMENT,
    first_name     VARCHAR(80)   NOT NULL,
    last_name      VARCHAR(80)   NOT NULL,
    email_id       VARCHAR(160)  NOT NULL,
    phone_number   VARCHAR(20)   NULL,
    dob            DATE          NULL,
    admin_access   BOOLEAN       NOT NULL DEFAULT FALSE,

    PRIMARY KEY (id),
    CONSTRAINT uq_tbuser_email_id UNIQUE (email_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbwhat
CREATE TABLE IF NOT EXISTS tbwhat (
    id            INT           NOT NULL AUTO_INCREMENT,
    phone_number  VARCHAR(20)   NOT NULL,
    name          VARCHAR(160)  NOT NULL,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at  DATETIME      NULL,

    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- tbhexp
CREATE TABLE IF NOT EXISTS tbhexp (
    id               INT             NOT NULL AUTO_INCREMENT,
    expense_name     VARCHAR(160)    NOT NULL,
    description      TEXT            NULL,
    amount           DECIMAL(12, 2)  NOT NULL,
    year           SMALLINT        NOT NULL,

    PRIMARY KEY (id),
    CONSTRAINT ck_tbhexp_amount_positive CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbhcoll
CREATE TABLE IF NOT EXISTS tbhcoll (
    id               INT             NOT NULL AUTO_INCREMENT,
    name             VARCHAR(120)    NOT NULL,
    phone_number     VARCHAR(20)     NULL,
    wing             VARCHAR(20)     NULL,
    is_tenant        BOOLEAN         NOT NULL DEFAULT FALSE,
    is_external      BOOLEAN         NOT NULL DEFAULT FALSE,
    amount           DECIMAL(12, 2)  NOT NULL,
    year           SMALLINT        NOT NULL,

    PRIMARY KEY (id),
    CONSTRAINT ck_tbhcoll_amount_positive CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tbhist
CREATE TABLE IF NOT EXISTS tbhist (
    id                INT             NOT NULL AUTO_INCREMENT,
    year           SMALLINT        NOT NULL,
    initiator_name    VARCHAR(60)     NOT NULL,
    initiator_phone   VARCHAR(20)     NULL,
    total_collection  DECIMAL(14, 2)  NOT NULL DEFAULT 0.00,
    total_expense     DECIMAL(14, 2)  NOT NULL DEFAULT 0.00,
    status            VARCHAR(30)     NOT NULL,

    PRIMARY KEY (id),
    CONSTRAINT uq_tbhist_year UNIQUE (year),
    CONSTRAINT ck_tbhist_total_collection_non_negative CHECK (total_collection >= 0),
    CONSTRAINT ck_tbhist_total_expense_non_negative CHECK (total_expense >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;