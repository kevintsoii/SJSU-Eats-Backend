import os
from datetime import datetime
from multiprocessing import Process

import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from scraper.scraper import scrape_menus
from scraper.image_scraper import scrape_all_images


load_dotenv()

app = Flask(__name__)
CORS(app)

currently_scraping = set()

conn = psycopg2.connect(
    dbname="sjsu_eats",
    host="localhost",
    port=5432,
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
conn.autocommit = True


def is_valid_date(date: str) -> bool:
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False


@app.route("/api/items")
def get_items():
    """
    Fetches all items from the database.
    """
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM items;")
        rows = cur.fetchall()

    items = {
        row["name"]: {k: v for k, v in row.items() if k != "name"}
        for row in rows
    }

    return jsonify(items)


@app.route("/api/search/<query>")
def get_search_results(query):
    """
    Fetches items that match the search query.
    """
    if len(query) < 3 or len(query) > 50:
        return jsonify({})
    
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute("SELECT date, item FROM menus, UNNEST(items) AS item WHERE item ILIKE %s "
                    "AND date BETWEEN CURRENT_DATE AND (CURRENT_DATE + interval '1 month') ORDER BY date LIMIT 100;", 
                    (f"%{query}%", ))
        rows = cur.fetchall()

    data = {}
    for row in rows:
        data.setdefault(str(row["date"]), set()).add(row["item"])
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
        cur.execute("SELECT * FROM menus WHERE date = %s;", (date, ))
        rows = cur.fetchall()

        if not rows:
            if date not in currently_scraping:
                currently_scraping.add(date)
                scraped_successfully = scrape_menus(date)
                currently_scraping.remove(date)

                if scraped_successfully:
                    cur.execute("SELECT * FROM menus WHERE date = %s;", (date, ))
                    rows = cur.fetchall()
                    menus["new"] = True

                    #if len(currently_scraping) == 0:
                        #p = Process(target=scrape_all_images)
                        #p.start()

        if not rows:
            return jsonify({"error": "No menus found for this date."})

    for row in rows:
        if "items" in row:
            menus[row["meal"]][row["location"]] = row["items"]
    
    return jsonify(menus)

if __name__ == "__main__":
    app.run()
    