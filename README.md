# SJSU-Eats-Backend
Flask backend for [SJSU Eats](https://github.com/kevintsoii/SJSU-Eats).

## Prerequisites

- [Python](https://www.python.org/) 3+
- [PostgreSQL](https://www.postgresql.org/download/) 16

## Getting Started
   
1. Create an `.env` file with the your Postgres database credentials
   
   ```
   DATABASE_URL="postgresql://postgres:password@localhost:5432/sjsu_eats"
   ```
   
2. (Optional) Set up a venv
   
   ```
   python -m venv .venv
   .venv\scripts\activate
   ```

3. Install dependencies

   ```
   pip install -r requirements.txt
   ```

4. Set up the Postgres database and run the Flask app

   ```
   py database/setup.py
   py app.py
   ```

## Setting up image scraping

1. Create a custom Google Search Engine - https://programmablesearchengine.google.com/controlpanel/create
   - Search the entire web
   - Enable Image Search
   - Grab the Search Engine ID
     
2. Grab your API Key - https://developers.google.com/custom-search/v1/introduction
   
3. Add to your `.env` file
   
   ```
   GOOGLE_IMAGES_CSE_ID="....."
   GOOGLE_IMAGES_API_KEY="AI....."
   ```

4. Run the image scraper

   ```
   py scraper/image_scraper.py
   ```

## Heroku Hosting

Commands to import a database to Heroku.
```
pg_dump -Fp --no-acl --no-owner postgresql://postgres:password@localhost:5432/sjsu_eats > mydb.dump
heroku pg:psql -a sjsu-eats-backend -f mydb.dump
```
