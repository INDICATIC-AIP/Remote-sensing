#!/bin/bash
set -e

# Inicializa una base de datos SQLite usando metadata.sql
# Initialize a SQLite database using metadata.sql
DIR="$(cd "$(dirname "$0")" && pwd)"
SQL_FILE="$DIR/metadata.sql"
DB_FILE="$DIR/metadata.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 is not installed. Please install it and try again."
  exit 1
fi

if [ ! -f "$SQL_FILE" ]; then
  echo "SQL file not found: $SQL_FILE"
  exit 1

echo "Creating/updating database at: $DB_FILE"
sqlite3 "$DB_FILE" < "$SQL_FILE"

echo "Database created/updated: $DB_FILE"
