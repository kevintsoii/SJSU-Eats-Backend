import os
import psycopg
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("SELECT * FROM items LIMIT 10")
items = cur.fetchall()
for item in items:
    print(item)

print()
print()

cur.execute("SELECT * FROM menus ORDER BY last_updated DESC LIMIT 10")
menus = cur.fetchall()
for menu in menus:
    print(menu)

print()
print()

cur.execute("SELECT * FROM menu_items LIMIT 10")
menu_items = cur.fetchall()
for menu_item in menu_items:
    print(menu_item)

cur.close()
conn.close()
