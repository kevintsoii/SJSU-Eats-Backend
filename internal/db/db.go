package db

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/data/azcosmos"
	"github.com/joho/godotenv"
)

var db *azcosmos.DatabaseClient

func createContainer(container string, partitionKeyPath []string, thoroughput int32, ttl int32) error {
	ctx := context.Background()
	containerProperties := azcosmos.ContainerProperties{
		ID: container,
		PartitionKeyDefinition: azcosmos.PartitionKeyDefinition{
			Paths: partitionKeyPath,
		},
		DefaultTimeToLive: &ttl,
	}
	throughputProperties := azcosmos.NewManualThroughputProperties(thoroughput)

	_, err := db.CreateContainer(ctx, containerProperties, &azcosmos.CreateContainerOptions{ThroughputProperties: &throughputProperties})
	if err != nil {
		if azErr, ok := err.(*azcore.ResponseError); ok && azErr.StatusCode == 409 {
			return nil
		}
		return fmt.Errorf("error creating container: %v", err)
	}
	return nil
}

func Init() error {
	err := godotenv.Load(".env")
	if err != nil {
		return fmt.Errorf("error loading .env: %v", err)
	}

	cred, err := azcosmos.NewKeyCredential(os.Getenv("DB_KEY"))
	if err != nil {
		return fmt.Errorf("error creating Cosmos DB key credential: %v", err)
	}

	client, err := azcosmos.NewClientWithKey(os.Getenv("DB_URI"), cred, nil)
	if err != nil {
		return fmt.Errorf("error creating Cosmos DB client: %v", err)
	}

	// Create Database if not exists
	ctx := context.Background()
	databaseProperties := azcosmos.DatabaseProperties{ID: "sjsu-eats"}
	_, _ = client.CreateDatabase(ctx, databaseProperties, nil)

	db, err = client.NewDatabase("sjsu-eats")
	if err != nil {
		return fmt.Errorf("error grabbing Cosmos DB database: %v", err)
	}

	// Create Containers if not exists
	err = createContainer("menus", []string{"/datemeal"}, 400, 60*60*24*30)
	if err != nil {
		return fmt.Errorf("error creating menus container: %v", err)
	}
	err = createContainer("items", []string{"/name"}, 600, -1)
	if err != nil {
		return fmt.Errorf("error creating items container: %v", err)
	}

	log.Printf("Successfully initialized database connection")

	return nil
}

func GetDB() *azcosmos.DatabaseClient {
	return db
}
