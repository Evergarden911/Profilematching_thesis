-- ============================================================
-- Pramita Lab SDM DSS — PostgreSQL Setup Script
-- Run as PostgreSQL superuser (postgres)
-- ============================================================

-- ------------------------------------------------------------
-- 1. Database
-- ------------------------------------------------------------
CREATE DATABASE sdm_dss
    ENCODING 'UTF8'
    LC_COLLATE 'en_US.UTF-8'
    LC_CTYPE 'en_US.UTF-8'
    TEMPLATE template0;

-- ------------------------------------------------------------
-- 2. Users
--    sdm_app     → FastAPI runtime  (DML only: no DROP/ALTER)
--    sdm_migrate → Alembic only     (DDL: CREATE/ALTER/DROP)
-- ------------------------------------------------------------
CREATE USER sdm_app     WITH PASSWORD 'ganti_password_app_ini';
CREATE USER sdm_migrate WITH PASSWORD 'ganti_password_migrate_ini';

\c sdm_dss

-- Grant connection
GRANT CONNECT ON DATABASE sdm_dss TO sdm_app;
GRANT CONNECT ON DATABASE sdm_dss TO sdm_migrate;

-- Migration user owns DDL
GRANT ALL PRIVILEGES ON SCHEMA public TO sdm_migrate;

-- App user: DML only on all current AND future tables
GRANT USAGE ON SCHEMA public TO sdm_app;
ALTER DEFAULT PRIVILEGES FOR ROLE sdm_migrate IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sdm_app;
ALTER DEFAULT PRIVILEGES FOR ROLE sdm_migrate IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO sdm_app;

-- ------------------------------------------------------------
-- 3. Enum types
--    Alembic will create these, but defining here lets you
--    verify the exact values match models.py before migrating.
-- ------------------------------------------------------------

-- These are created automatically by Alembic from SQLAlchemy
-- Enum definitions. Listed here for reference only:
--
-- userrole:       kepala_hrd, kepala_cabang, kepala_divisi
-- requeststatus:  pending, gate_check, interview_required,
--                 forwarded, under_review, matched,
--                 approved, rejected, gate_rejected
-- factortype:     core, secondary
-- gatestatus:     pending, passed, failed,
--                 interview_pending, interview_passed, interview_failed
-- constrainttype: allowed, blocked

-- ------------------------------------------------------------
-- 4. Verify privileges (run after Alembic migration)
-- ------------------------------------------------------------
-- SET ROLE sdm_app;
-- DROP TABLE users;  -- must fail: permission denied
-- RESET ROLE;
