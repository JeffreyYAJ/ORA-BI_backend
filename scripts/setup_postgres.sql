-- Exécuter une fois avec un superutilisateur PostgreSQL, par exemple :
--   sudo -u postgres psql -f scripts/setup_postgres.sql

CREATE USER datapipe WITH PASSWORD 'datapipe';
CREATE DATABASE datapipe OWNER datapipe;
GRANT ALL PRIVILEGES ON DATABASE datapipe TO datapipe;
