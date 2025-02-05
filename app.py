import os
from datetime import datetime

import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS


load_dotenv()

app = Flask(__name__)
CORS(app)

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True


def is_valid_date(date: str) -> bool:
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False

@app.route("/api/item/<item_name>")
def get_item(item_name):
    """
    Fetches all basic item info from the database.
    """
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM items WHERE name = %s;", (item_name,))
        item = cur.fetchone()  # Fetch a single item
        
    if not item:
        return jsonify({"error": "Item not found"}), 404
    
    return jsonify(item)

@app.route("/api/items")
def get_items():
    """
    Fetches all basic item info from the database.
    """
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute("SELECT i.name, i.nutrients, i.image FROM items i;")
        rows = cur.fetchall()

    items = {
        row["name"]: {
            "calories": row["nutrients"]["Calories"] if row["nutrients"] and "Calories" in row["nutrients"] else None,
            "protein": row["nutrients"]["Protein"] if row["nutrients"] and "Protein" in row["nutrients"] else None,
            "image": row["image"]
        }
        for row in rows
    }

    return jsonify(items)

@app.route("/api/search/<query>")
def get_search_results(query):
    """
    Fetches items that match the search query.
    """
    if len(query) < 3 or len(query) > 50:
        return jsonify({"error": "Invalid search query"}), 400
    
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT m.date, mi.item_name
            FROM menus m JOIN menu_items mi ON m.id = mi.menu_id
            WHERE mi.item_name ILIKE %s
            AND m.date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '1 month')
            ORDER BY m.date
            LIMIT 100;
        """, (f"%{query}%",))
        rows = cur.fetchall()

    data = {}
    for row in rows:
        data.setdefault(str(row["date"]), set()).add(row["item_name"])

    data = {date: list(items) for date, items in data.items()}
    return jsonify(data)

@app.route("/api/menus/<date>")
def get_menus(date):
    """
    Fetches menus for the specified date.
    If none are found, requests a scrape of today's menus from the API.

    Args:
        date (str): YYYY-MM-DD format
    """
    if not is_valid_date(date):
        return jsonify({"error": "Invalid date format."}), 400
    
    menus = {
        "breakfast": {},
        "lunch": {},
        "dinner": {}
    }
    
    # date, meal, location, items
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute("""
            WITH filtered_menus AS (
                SELECT id, meal, location, status
                FROM menus
                WHERE date = %s
            )
            SELECT 
                fm.meal, fm.location, fm.status, mi.item_name
            FROM filtered_menus fm
            LEFT JOIN menu_items mi ON fm.id = mi.menu_id;
        """, (date,))

        rows = cur.fetchall()

    if not rows:
        return jsonify({"error": "No menus found for this date."})

    for row in rows:
        meal = row["meal"]
        location = row["location"]
        status = row["status"]

        if status == "closed" or row["item_name"] is None:
            if not location:
                menus[meal] = {"closed": True}
            else:
                menus[meal][location] = {"closed": True}
        else:
            if location not in menus[meal]:
                menus[meal][location] = {"items": []}

            menus[meal][location]["items"].append(row["item_name"])
    
    return jsonify(menus)


if __name__ == "__main__":
    app.run()
    