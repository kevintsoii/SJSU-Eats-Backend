import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()


conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
    DROP TABLE IF EXISTS menu_items CASCADE;
    DROP TABLE IF EXISTS menus CASCADE;
            
    CREATE TABLE menus (
        id SERIAL PRIMARY KEY,
        date DATE,
        meal VARCHAR(10) NOT NULL,
        location VARCHAR(64),
        status menu_status_enum NOT NULL,
        UNIQUE (date, meal, location)
    );
    
    CREATE TABLE menu_items (
        menu_id INT REFERENCES menus(id) ON DELETE CASCADE,
        item_name VARCHAR(64) REFERENCES items(name) ON DELETE CASCADE,
        PRIMARY KEY (menu_id, item_name)
    );
            
    CREATE INDEX idx_menus_date ON menus (date);
    CREATE INDEX idx_menu_items_date_name ON menu_items (item_name, menu_id);
"""
)

conn.commit()

cur.close()
conn.close()

print("Successfully refreshed menus.")
