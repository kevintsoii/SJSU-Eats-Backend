import os
import threading
import time
from datetime import datetime

import psycopg
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from scraper.scraper import scrape_menus


load_dotenv()

app = Flask(__name__)
CORS(app)

currently_scraping = set()

conn = psycopg.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True


def is_valid_date(date: str) -> bool:
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def async_scrape_menus(date: str):
    """Asynchronously scrape menus for a given date."""
    print(f"Scraping menus for {date} asynchronously.")

    try:
        scrape_menus(date, refresh_menus=True)
    except Exception as e:
        print(f"Error in async scraping for {date}: {e}")
    finally:
        currently_scraping.discard(date)

@app.route("/api/item/<item_name>")
def get_item(item_name):
    """
    Fetches all basic item info from the database.
    """
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
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
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
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
    
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
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
    Implements smart refresh logic:
    - If menu doesn't exist: scrape synchronously before proceeding
    - If menu exists but is >3 days old: re-scrape asynchronously
    - If menu exists and is fresh: proceed normally

    Args:
        date (str): YYYY-MM-DD format
    """
    if not is_valid_date(date):
        return jsonify({"error": "Invalid date format."}), 400

    if date in currently_scraping:
        return jsonify({"error": "Menu data is currently being scraped. Please try again shortly."}), 202
    
    menus = {
        "breakfast": {},
        "lunch": {},
        "dinner": {}
    }

    # Check if menus exist and get their last_updated timestamps
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("""
            WITH filtered_menus AS (
                SELECT id, meal, location, status, last_updated
                FROM menus
                WHERE date = %s
            )
            SELECT 
                fm.meal, fm.location, fm.status, fm.last_updated, mi.item_name
            FROM filtered_menus fm
            LEFT JOIN menu_items mi ON fm.id = mi.menu_id;
        """, (date,))

        rows = cur.fetchall()

    # If no menus exist, scrape synchronously
    if not rows:
        if date not in currently_scraping:
            print(f"Scraping menus for {date} synchronously.")
            currently_scraping.add(date)
            try:
                scrape_menus(date)
            except Exception as e:
                currently_scraping.discard(date)
                return jsonify({"error": f"Failed to scrape menus: {str(e)}"}), 500
            finally:
                currently_scraping.discard(date)
            
            # Re-fetch the data after scraping
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                    WITH filtered_menus AS (
                        SELECT id, meal, location, status, last_updated
                        FROM menus
                        WHERE date = %s
                    )
                    SELECT 
                        fm.meal, fm.location, fm.status, fm.last_updated, mi.item_name
                    FROM filtered_menus fm
                    LEFT JOIN menu_items mi ON fm.id = mi.menu_id;
                """, (date,))
                rows = cur.fetchall()
        else:
            return jsonify({"error": "Menu data is currently being scraped. Please try again shortly."}), 202

    # Check if any menu data is older than 48 hours and trigger async refresh
    if rows and date not in currently_scraping:
        current_time = time.time()
        oldest_update = min(row["last_updated"] for row in rows if row["last_updated"])
        
        if current_time - oldest_update > 259200:
            currently_scraping.add(date)
            # Start async scraping in background thread
            thread = threading.Thread(target=async_scrape_menus, args=(date,))
            thread.daemon = True
            thread.start()

    # Process the menu data
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
    
    for meal in menus:
        if 'closed' not in menus[meal]:
            if all(
                "closed" in menus[meal][location] and menus[meal][location]["closed"]
                for location in menus[meal]
            ):
                menus[meal] = {"closed": True}

    return jsonify(menus)


if __name__ == "__main__":
    app.run()
    