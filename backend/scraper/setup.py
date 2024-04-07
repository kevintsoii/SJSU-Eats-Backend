import os
import sys

import psycopg2
from dotenv import load_dotenv


load_dotenv()

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
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

conn = psycopg2.connect(
    dbname="sjsu_eats",
    host="localhost",
    port=5432,
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor()

cur.execute("""
    DROP TABLE IF EXISTS items;
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
    DROP TABLE IF EXISTS locations CASCADE;
    CREATE TABLE locations (
        name VARCHAR(64) PRIMARY KEY,
        image VARCHAR(256)
    );
"""
)

cur.execute("""
    DROP TABLE IF EXISTS menus CASCADE;
    CREATE TABLE menus (
        date DATE,
        meal VARCHAR(10) NOT NULL,
        location VARCHAR(64) REFERENCES locations(name),
        items VARCHAR(64)[],
        PRIMARY KEY(date, meal, location)
    );
"""
)

conn.commit()

cur.close()
conn.close()

print("Successfully created tables.")
