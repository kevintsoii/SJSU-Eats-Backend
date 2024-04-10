import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

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

print("Successfully refreshed menus.")
