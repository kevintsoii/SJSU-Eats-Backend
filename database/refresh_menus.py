import os
import psycopg

from dotenv import load_dotenv

from setup import create_menu_tables_and_indexes


load_dotenv()


conn = psycopg.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
    DROP TABLE IF EXISTS menu_items CASCADE;
    DROP TABLE IF EXISTS menus CASCADE;
    DROP TYPE IF EXISTS menu_status_enum;
    DROP TYPE IF EXISTS menu_meal_enum;
""")

create_menu_tables_and_indexes(cur)

conn.commit()

cur.close()
conn.close()

print("Successfully refreshed menus.")
