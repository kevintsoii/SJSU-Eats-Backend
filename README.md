# SJSU-Eats-Backend

Flask backend for [SJSU Eats](https://github.com/kevintsoii/SJSU-Eats).

## Prerequisites

- [Python](https://www.python.org/) 3+
- [PostgreSQL](https://www.postgresql.org/download/) 16

## Getting Started

1. Create an `.env` file with the your Postgres database credentials

   ```
   DATABASE_URL="postgresql://postgres:password@localhost:5432/sjsu_eats"
   BASE_API_URL="api.xxxx.com"
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

2. Grab your Google API Key - https://developers.google.com/custom-search/v1/introduction

3. Sign up for Cloudflare R2 storage - https://www.cloudflare.com/developer-platform/products/r2/

   - Create a Bucket and allow public read access
   - Create an API token with object read/write access
   - Grab the Access Key ID, Secret Access Key, Public URL, and S3 Endpoint

4. Add keys to your `.env` file

   ```
   GOOGLE_IMAGES_CSE_ID=
   GOOGLE_IMAGES_API_KEY=
   ACCESS_KEY_ID=
   SECRET_ACCESS_KEY=
   S3_ENDPOINT=
   R2_BUCKET_NAME=sjsu-eats
   R2_PUBLIC_URL=
   ```

5. Run the image scraper

   ```
   py scraper/image_scraper.py
   ```

## Heroku Hosting

Commands to import a database to Heroku.

```
pg_dump -Fp --no-acl --no-owner postgresql://postgres:password@localhost:5432/sjsu_eats > mydb.dump
heroku pg:psql -a sjsu-eats-backend -f mydb.dump
```
