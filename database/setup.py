import os
import sys

import psycopg
from dotenv import load_dotenv


load_dotenv()

DB_NAME = "sjsu_eats"
DATABASE_URL = os.getenv("DATABASE_URL")


def create_menu_tables_and_indexes(cursor):
    cursor.execute("""
        CREATE TYPE menu_status_enum AS ENUM ('closed', 'open');
        CREATE TYPE menu_meal_enum AS ENUM ('breakfast', 'lunch', 'dinner');
    """)
    
    cursor.execute("""
        CREATE TABLE menus (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            meal menu_meal_enum NOT NULL,
            location VARCHAR(64),
            status menu_status_enum NOT NULL,
            last_updated BIGINT DEFAULT extract(epoch from now()) NOT NULL,
            UNIQUE NULLS NOT DISTINCT (date, meal, location)
        );
    """)
    
    cursor.execute("""
        CREATE TABLE menu_items (
            menu_id INT REFERENCES menus(id) ON DELETE CASCADE,
            item_name VARCHAR(64) REFERENCES items(name) ON DELETE CASCADE,
            PRIMARY KEY (menu_id, item_name)
        );
    """)
    
    cursor.execute("""
        CREATE INDEX idx_menus_date ON menus (date);
        CREATE INDEX idx_menu_items_date_name ON menu_items (item_name, menu_id);
    """)

if __name__ == "__main__":
    try:
        database_url = DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
        conn = psycopg.connect(database_url, autocommit=True)
        cur = conn.cursor()

        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
        exists = cur.fetchone()

        if exists:
            input("Warning: The database already exists.\n"
                "Press enter to continue (old data will be lost): ")
        else:
            cur.execute(f"CREATE DATABASE {DB_NAME};")
            print(f"Database {DB_NAME} created.")

        cur.close()
        conn.close()
    except psycopg.Error as e:
        sys.exit(f"Failed to connect or create database: {e}")

    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        DROP TABLE IF EXISTS menu_items CASCADE;
        DROP TABLE IF EXISTS menus CASCADE;
        DROP TABLE IF EXISTS items CASCADE;
        DROP TYPE IF EXISTS menu_status_enum;
        DROP TYPE IF EXISTS menu_meal_enum;
    """)

    cur.execute("""
        CREATE TABLE items (
            name VARCHAR(64) PRIMARY KEY,
            description VARCHAR(256),
            portion VARCHAR(64),
            ingredients TEXT,
            nutrients JSONB,
            filters JSONB,
            image VARCHAR(256),
            image_source VARCHAR(1024)
        );
    """
    )

    create_menu_tables_and_indexes(cur)

    conn.commit()

    cur.close()
    conn.close()

    print("Successfully created tables.")
