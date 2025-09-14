import os
import threading
import time
from datetime import datetime
from queue import Queue

import psycopg
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from scraper.scraper import scrape_menus


load_dotenv()

app = Flask(__name__)
CORS(app, origins="*", allow_headers="*", methods="*")

# Queue system for scraping requests
scrape_queue = Queue()
queued_dates = set()  # Track what's in queue to avoid duplicates
currently_scraping = set()
queue_processor_running = False

conn = psycopg.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True


def is_valid_date(date: str) -> bool:
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def process_scrape_queue():
    """Background thread function to process scraping queue sequentially."""
    global queue_processor_running
    
    while True:
        try:
            # Get next item from queue (this blocks until an item is available)
            date, refresh_menus = scrape_queue.get(timeout=30)  # 30 second timeout
            
            print(f"[QUEUE] Processing scrape request for {date} (refresh={refresh_menus})")
            
            # Move from queued to currently_scraping
            queued_dates.discard(date)
            currently_scraping.add(date)
            
            try:
                scrape_menus(date, refresh_menus=refresh_menus)
                print(f"[QUEUE] Successfully scraped {date}")
            except Exception as e:
                print(f"[QUEUE] Error scraping {date}: {e}")
            finally:
                currently_scraping.discard(date)
                scrape_queue.task_done()
                
        except:
            # Queue timeout or other error - this is normal when no items in queue
            continue


def add_to_scrape_queue(date: str, refresh_menus: bool = False):
    """Add a date to the scraping queue if not already queued or being processed."""
    if date in queued_dates or date in currently_scraping:
        print(f"[QUEUE] {date} already queued or being processed")
        return False
    
    queued_dates.add(date)
    scrape_queue.put((date, refresh_menus))
    print(f"[QUEUE] Added {date} to scrape queue (refresh={refresh_menus})")
    
    # Start queue processor if not running
    global queue_processor_running
    if not queue_processor_running:
        queue_processor_running = True
        thread = threading.Thread(target=process_scrape_queue, daemon=True)
        thread.start()
        print("[QUEUE] Started queue processor thread")
    
    return True

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

    # Check if date is queued or currently being scraped
    if date in queued_dates or date in currently_scraping:
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

    # If no menus exist, add to queue and return 202
    if not rows:
        add_to_scrape_queue(date, refresh_menus=False)
        return jsonify({"error": "Menu data is being scraped. Please try again shortly."}), 202

    # Check if any menu data is older than 72 hours and trigger async refresh
    if rows and date not in currently_scraping and date not in queued_dates:
        current_time = time.time()
        oldest_update = min(row["last_updated"] for row in rows if row["last_updated"])
        
        if current_time - oldest_update > 259200:  # 72 hours
            add_to_scrape_queue(date, refresh_menus=True)

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
    