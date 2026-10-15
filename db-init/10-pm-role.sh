#!/bin/sh
set -eu
# This script runs ONLY inside the new, isolated PM database on first init.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$PM_DB_PASSWORD" <<'SQL'
CREATE ROLE pm_app LOGIN PASSWORD :'app_password';
GRANT CONNECT ON DATABASE multitek_pm TO pm_app;
GRANT USAGE, CREATE ON SCHEMA public TO pm_app;
SQL
