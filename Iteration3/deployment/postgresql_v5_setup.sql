-- PostgreSQL setup template for V5 production deployment
-- Replace placeholder values before executing in production.

-- 1. Create application role with least privilege.
CREATE ROLE rehab_app
LOGIN
PASSWORD 'CHANGE_ME_STRONG_PASSWORD'
NOSUPERUSER
NOCREATEDB
NOCREATEROLE
NOINHERIT;

-- 2. Create production database.
CREATE DATABASE rehab_prod
OWNER rehab_app
ENCODING 'UTF8'
TEMPLATE template0;

-- 3. Restrict default access.
REVOKE ALL ON DATABASE rehab_prod FROM PUBLIC;
GRANT CONNECT ON DATABASE rehab_prod TO rehab_app;

-- 4. Connect to the database before running the following section.
-- \c rehab_prod

-- 5. Restrict public schema permissions.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO rehab_app;

-- 6. Optional: enforce statement timeout and idle timeout for the app role.
ALTER ROLE rehab_app SET statement_timeout = '15s';
ALTER ROLE rehab_app SET idle_in_transaction_session_timeout = '10s';

-- 7. TLS/SSL should be enforced on the PostgreSQL server side.
-- Recommended postgresql.conf settings:
-- ssl = on
-- password_encryption = scram-sha-256
--
-- Recommended pg_hba.conf entries:
-- hostssl rehab_prod rehab_app <trusted_client_or_vpn_cidr> scram-sha-256
-- host    all        all       0.0.0.0/0 reject

-- 8. Schema tables are created by the V5 application on first startup.
