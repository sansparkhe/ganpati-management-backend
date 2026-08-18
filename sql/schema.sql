-- Schema for the Ganpati Utsav backend (PostgreSQL).
--
-- Generated from app/models/. Table names are quoted because they are
-- uppercase: PostgreSQL folds unquoted identifiers to lower case, so every
-- query must spell them "TBUSER" / "TBEXP" / "TBCOLL" with double quotes.
--
-- app/models/ is the source of truth. If you change a model, regenerate this
-- file rather than editing it by hand.


CREATE TABLE "TBUSER" (
	id SERIAL NOT NULL, 
	first_name VARCHAR(80) NOT NULL, 
	last_name VARCHAR(80) NOT NULL, 
	phone_number VARCHAR(20), 
	dob DATE, 
	email_id VARCHAR(160) NOT NULL, 
	admin_access BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT "pk_TBUSER" PRIMARY KEY (id)
);

CREATE INDEX "ix_TBUSER_admin_access" ON "TBUSER" (admin_access);
CREATE UNIQUE INDEX "ix_TBUSER_email_id" ON "TBUSER" (email_id);

CREATE TABLE "TBEXP" (
	id SERIAL NOT NULL, 
	expense_name VARCHAR(160) NOT NULL, 
	expense_category VARCHAR(32) NOT NULL, 
	description TEXT, 
	amount NUMERIC(12, 2) NOT NULL, 
	username VARCHAR(60) NOT NULL, 
	password VARCHAR(128) NOT NULL, 
	CONSTRAINT "pk_TBEXP" PRIMARY KEY (id), 
	CONSTRAINT "ck_TBEXP_amount_positive" CHECK (amount > 0)
);

CREATE INDEX "ix_TBEXP_expense_category" ON "TBEXP" (expense_category);
CREATE INDEX "ix_TBEXP_expense_name" ON "TBEXP" (expense_name);
CREATE INDEX "ix_TBEXP_username" ON "TBEXP" (username);

CREATE TABLE "TBCOLL" (
	id SERIAL NOT NULL, 
	approved BOOLEAN DEFAULT false NOT NULL, 
	in_queue BOOLEAN DEFAULT true NOT NULL, 
	owner_name VARCHAR(120) NOT NULL, 
	is_tenant BOOLEAN DEFAULT false NOT NULL, 
	tenant_name VARCHAR(120), 
	phone_number VARCHAR(20), 
	amount NUMERIC(12, 2) NOT NULL, 
	payment_mode VARCHAR(32) NOT NULL, 
	transaction_id VARCHAR(64), 
	cash_held_by VARCHAR(120), 
	username VARCHAR(60) NOT NULL, 
	password VARCHAR(128) NOT NULL, 
	CONSTRAINT "pk_TBCOLL" PRIMARY KEY (id), 
	CONSTRAINT "ck_TBCOLL_amount_positive" CHECK (amount > 0), 
	CONSTRAINT "ck_TBCOLL_tenant_name_required_when_is_tenant" CHECK (NOT is_tenant OR tenant_name IS NOT NULL)
);

CREATE INDEX "ix_TBCOLL_approved" ON "TBCOLL" (approved);
CREATE INDEX "ix_TBCOLL_in_queue" ON "TBCOLL" (in_queue);
CREATE INDEX "ix_TBCOLL_owner_name" ON "TBCOLL" (owner_name);
CREATE INDEX "ix_TBCOLL_payment_mode" ON "TBCOLL" (payment_mode);
CREATE INDEX "ix_TBCOLL_username" ON "TBCOLL" (username);

