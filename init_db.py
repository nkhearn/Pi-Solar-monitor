import sqlite3
import os
import re

DB_PATH = "data/inverter_logs.db"
BACKUP_PATH = DB_PATH + ".bak"
LATEST_VERSION = 1

def sanitize_column_name(name):
    """
    Sanitizes a name for use as a SQL column name.
    """
    # Replace non-alphanumeric characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized.lower()

def get_row_count(conn, table_name):
    cursor = conn.cursor()
    try:
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0

def migrate_data_points_json_to_columns(conn):
    cursor = conn.cursor()
    print("Migrating legacy data_points table (JSON to columns)...")

    # 1. Get all unique keys from the JSON data
    try:
        cursor.execute("SELECT DISTINCT key FROM data_points, json_each(data_points.data)")
        keys = [row[0] for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        print(f"No data to migrate or error: {e}")
        return

    # 2. Rename old table
    cursor.execute("ALTER TABLE data_points RENAME TO data_points_old")

    # 3. Create new table
    cursor.execute('''
        CREATE TABLE data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Add columns and prepare migration query
    cols_to_insert = []
    select_exprs = []
    seen_sanitized = set()

    for key in keys:
        sanitized = sanitize_column_name(key)
        if sanitized not in seen_sanitized:
            print(f"Adding column: {sanitized} (from key: {key})")
            cursor.execute(f"ALTER TABLE data_points ADD COLUMN {sanitized} REAL")
            cols_to_insert.append(sanitized)
            # Use json_extract with original key.
            safe_key = key.replace("'", "''")
            select_exprs.append(f"json_extract(data, '$.\"{safe_key}\"')")
            seen_sanitized.add(sanitized)

    # 5. Insert data
    if cols_to_insert:
        cols_str = ", ".join(cols_to_insert)
        select_str = ", ".join(select_exprs)
        query = f"INSERT INTO data_points (id, timestamp, {cols_str}) SELECT id, timestamp, {select_str} FROM data_points_old"
        cursor.execute(query)
    else:
        cursor.execute("INSERT INTO data_points (id, timestamp) SELECT id, timestamp FROM data_points_old")

    # 6. Drop old table
    cursor.execute("DROP TABLE data_points_old")
    print("Migration complete.")

def backup_database(src, dest):
    if os.path.exists(dest):
        os.remove(dest)

    src_conn = sqlite3.connect(src)
    dest_conn = sqlite3.connect(dest)
    with dest_conn:
        src_conn.backup(dest_conn)
    dest_conn.close()
    src_conn.close()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    db_exists = os.path.exists(DB_PATH)
    initial_row_count = 0

    if db_exists:
        # Backup before anything
        print(f"Backing up database to {BACKUP_PATH}...")
        try:
            backup_database(DB_PATH, BACKUP_PATH)

            # Get initial row count for verification later
            temp_conn = sqlite3.connect(BACKUP_PATH)
            initial_row_count = get_row_count(temp_conn, "data_points")
            temp_conn.close()
        except Exception as e:
            print(f"Warning: Backup failed or could not determine initial row count: {e}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    upgrade_successful = True
    try:
        # Get current version
        cursor.execute("PRAGMA user_version")
        result = cursor.fetchone()
        current_version = result[0] if result else 0

        # Legacy check (if versioning wasn't used yet)
        if current_version == 0:
            cursor.execute("PRAGMA table_info(data_points)")
            columns = [row[1] for row in cursor.fetchall()]
            if "data" in columns:
                migrate_data_points_json_to_columns(conn)

        # Ensure all tables exist (standard init / create if not exists)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON data_points(timestamp)')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS virtual_metrics (
                name TEXT PRIMARY KEY,
                formula TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dashboard_charts (
                id TEXT PRIMARY KEY,
                config TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metric_configs (
                key TEXT PRIMARY KEY,
                config TEXT NOT NULL
            )
        ''')

        # Enable Write-Ahead Logging
        cursor.execute('PRAGMA journal_mode=WAL')
        # Set version
        cursor.execute(f"PRAGMA user_version = {LATEST_VERSION}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error during database initialization/upgrade: {e}")
        upgrade_successful = False

    # Verification
    new_row_count = get_row_count(conn, "data_points")
    conn.close()

    if db_exists:
        if upgrade_successful and new_row_count == initial_row_count:
            print("Verification successful. Row counts match.")
            try:
                if os.path.exists(BACKUP_PATH):
                    os.remove(BACKUP_PATH)
                    print("Backup removed.")
            except Exception as e:
                print(f"Warning: Could not remove backup file: {e}")
        else:
            print("\n" + "!"*60)
            if not upgrade_successful:
                print("WARNING: Upgrade failed!")
            else:
                print("WARNING: Row count mismatch after upgrade!")
            print(f"Original row count: {initial_row_count}")
            print(f"New row count:      {new_row_count}")
            print("!"*60)
            print(f"\nThe backup database has been kept at: {BACKUP_PATH}")
            print("\nTo manually restore your data, you can use the following commands:")
            print(f"  sqlite3 {BACKUP_PATH} \".dump\" | sqlite3 {DB_PATH}")
            print("\nOr use ATTACH within sqlite3 to transfer data:")
            print(f"  ATTACH '{BACKUP_PATH}' AS backup;")
            print(f"  -- Example: INSERT INTO data_points (timestamp, col1) SELECT timestamp, col1 FROM backup.data_points;")
            print("!"*60 + "\n")

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
