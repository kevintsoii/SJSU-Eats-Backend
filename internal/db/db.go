package db

import (
	"database/sql"
	"fmt"
	"os"

	"github.com/joho/godotenv"
	_ "github.com/microsoft/go-mssqldb"
)

var db *sql.DB

func createTables() error {
	statements := []string{
		`IF OBJECT_ID('dbo.Menus', 'U') IS NULL
		BEGIN 
			CREATE TABLE dbo.Menus (
				id INT PRIMARY KEY IDENTITY(1,1),
				date DATE,
				meal VARCHAR(10) CHECK (meal IN ('breakfast', 'lunch', 'dinner')),
				location VARCHAR(64),
				CONSTRAINT UQ_Meals UNIQUE (date, meal, location)
			);
		END;`,
		`IF OBJECT_ID('dbo.Items', 'U') IS NULL
		BEGIN
			CREATE TABLE dbo.Items (
				name VARCHAR(64) PRIMARY KEY,
				description VARCHAR(256),
				portion VARCHAR(64),
				ingredients VARCHAR(256),
				nutrients NVARCHAR(MAX),
				filters NVARCHAR(MAX),
				image_url NVARCHAR(2083),
				image_source NVARCHAR(2083)
			);
		END;`,
		`IF OBJECT_ID('dbo.MenuItems', 'U') IS NULL
		BEGIN
			CREATE TABLE dbo.MenuItems (
				menu_id INT,
				item_name VARCHAR(64),
				FOREIGN KEY (menu_id) REFERENCES dbo.Menus(id),
				FOREIGN KEY (item_name) REFERENCES dbo.Items(name),
				PRIMARY KEY (menu_id, item_name)
			);
		END;`,
	}

	for _, statement := range statements {
		_, err := db.Exec(statement)
		if err != nil {
			return fmt.Errorf("error executing statement %q: %v", statement, err)
		}
	}
	return nil
}

func Init() error {
	err := godotenv.Load(".env")
	if err != nil {
		return fmt.Errorf("error loading .env: %v", err)
	}

	connString := fmt.Sprintf("server=%s;user id=%s;password=%s;port=%d;database=%s;",
		os.Getenv("DB_SERVER"), os.Getenv("DB_USER"), os.Getenv("DB_PASS"), 1433, os.Getenv("DB_NAME"))

	db, err = sql.Open("sqlserver", connString)
	if err != nil {
		return fmt.Errorf("error loading .env: %v", err.Error())
	}

	if err := createTables(); err != nil {
		return fmt.Errorf("error creating tables: %v", err)
	}

	return db.Ping()
}

func GetDB() *sql.DB {
	return db
}

func Close() {
	db.Close()
}
