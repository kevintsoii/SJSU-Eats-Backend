import os
import sys

import psycopg2
from dotenv import load_dotenv


load_dotenv()


try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL").replace("/sjsu_eats", "/postgres"))
    conn.autocommit = True
    cur = conn.cursor()
except psycopg2.Error as e:
    sys.exit(f"Failed to connect to PostgreSQL: {e}")

try:
    cur.execute(f"CREATE DATABASE sjsu_eats;")
except psycopg2.Error as e:
    input("Warning: The database already exists.\n"
          "Press enter to continue (old data will be lost): ")

cur.close()
conn.close()


conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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

cur.execute("""
    CREATE TYPE menu_status_enum AS ENUM ('closed', 'open');
    CREATE TYPE menu_meal_enum AS ENUM ('breakfast', 'lunch', 'dinner');
    CREATE TABLE menus (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        meal menu_meal_enum NOT NULL,
        location VARCHAR(64),
        status menu_status_enum NOT NULL,
        UNIQUE NULLS NOT DISTINCT (date, meal, location)
    );
"""
)

cur.execute("""
    CREATE TABLE menu_items (
        menu_id INT REFERENCES menus(id) ON DELETE CASCADE,
        item_name VARCHAR(64) REFERENCES items(name) ON DELETE CASCADE,
        PRIMARY KEY (menu_id, item_name)
    );
"""
)

cur.execute("""
    CREATE INDEX idx_menus_date ON menus (date);
    CREATE INDEX idx_menu_items_date_name ON menu_items (item_name, menu_id);
""")

conn.commit()

cur.close()
conn.close()

print("Successfully created tables.")
