package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

const (
	ConfigFileEnv = "ConfigFile"
	ConfigFileLoc = "config.json"
	testQuery     = "SELECT * FROM devdb.testextron"
)

type Config struct {
	DBAddress            string   `json:"DBAddress"`
	DBName               string   `json:"DBName"`
	DBTable              string   `json:"DBTable"`
	DBUser               string   `json:"DBUser"`
	DBPassword           string   `json:"DBPassword"`
	TrustedProxies       []string `json:"TrustedProxies"`
	DBMaxIdleTimeMinutes int      `json:"DBMaxIdleTimeMinutes"`
	DBMaxOpenConns       int      `json:"DBMaxOpenConns"`
	DBMaxIdleConns       int      `json:"DBMaxIdleConns"`
}

// Globals
var (
	config   Config
	DBHandle *sql.DB
)

func init() {
	// Load config file
	var configfile string
	if configfile = os.Getenv(ConfigFileEnv); configfile == "" {
		configfile = ConfigFileLoc
	}
	if file, err := os.Open(configfile); err != nil {
		panic(fmt.Errorf("could not open config file: %s | %w", configfile, err))
	} else if err := json.NewDecoder(file).Decode(&config); err != nil {
		panic(fmt.Errorf("JSON error in config file %s | %w", configfile, err))
	}

	// Connect to database
	var err error
	DBHandle, err = makeDatabaseConn(config)
	if err != nil {
		fmt.Printf("Error connecting to database: %v", err)
	}
	applyDatabaseSettings(config)
}

func main() {
	http.HandleFunc("/status", statusHandler)
	http.HandleFunc("/test", testReadHandler)
	http.HandleFunc("/disconnect", testDisconnectDBHandler)
	http.HandleFunc("/metric", metricHandler)

	fmt.Println("Server running on port 8080")
	http.ListenAndServe(":8080", nil)
}

func makeDatabaseConn(config Config) (*sql.DB, error) {
	// Inner
	makeDataSourceName := func(config Config) string {
		user := config.DBUser
		pw := config.DBPassword
		address := config.DBAddress
		db_name := config.DBName
		return user + ":" + pw + "@tcp(" + address + ")/" + db_name
	}

	dsn := makeDataSourceName(config)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		panic(err)
	}
	if err := db.Ping(); err != nil {
		panic(err)
	}
	return db, nil
}

func applyDatabaseSettings(config Config) {
	DBHandle.SetConnMaxIdleTime(time.Duration(config.DBMaxIdleTimeMinutes) * time.Minute)
	DBHandle.SetMaxOpenConns(config.DBMaxOpenConns)
	DBHandle.SetMaxIdleConns(config.DBMaxIdleConns)
}

func readFromDatabase(db *sql.DB, query string) (*sql.Rows, error) {
	rows, err := db.Query(query)
	if err != nil {
		return nil, err
	}
	return rows, nil
}

func sqlTojsonSerializer(rows *sql.Rows) ([]map[string]interface{}, error) {
	columns, err := rows.Columns()
	if err != nil {
		return nil, err
	}

	results := make([]map[string]interface{}, 0)
	for rows.Next() {
		columnsData := make([]interface{}, len(columns))
		columnsDataPtr := make([]interface{}, len(columns))
		for i := range columnsData {
			columnsDataPtr[i] = &columnsData[i]
		}

		if err := rows.Scan(columnsDataPtr...); err != nil {
			return nil, err
		}

		rowMap := make(map[string]interface{})
		for i, colName := range columns {
			val := columnsData[i]
			b, ok := val.([]byte)
			if ok {
				rowMap[colName] = string(b)
			} else {
				rowMap[colName] = val
			}
		}
		results = append(results, rowMap)
	}
	return results, nil
}

//// Handlers ////

func statusHandler(w http.ResponseWriter, r *http.Request) {
	if err := DBHandle.Ping(); err != nil {
		http.Error(w, "Error connecting to database: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"message": "Okay"}`))
}

func testReadHandler(w http.ResponseWriter, r *http.Request) {
	rows, read_err := readFromDatabase(DBHandle, testQuery)

	if read_err != nil {
		http.Error(w, "Error reading from database: "+read_err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	res, serialize_err := sqlTojsonSerializer(rows)

	if serialize_err != nil {
		http.Error(w, "Error serializing to json: "+serialize_err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"message": res})
}

func testDisconnectDBHandler(w http.ResponseWriter, r *http.Request) {
	DBHandle.Close()

	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"message": "Disconnected from database"}`))
}

func metricHandler(w http.ResponseWriter, r *http.Request) {
	var jsonData map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&jsonData); err != nil {
		http.Error(w, "Invalid JSON data", http.StatusBadRequest)
		return
	}
	room, roomOk := jsonData["room"].(string)
	time, timeOk := jsonData["time"].(string)
	metric, metricOk := jsonData["metric"].(string)
	action, actionOk := jsonData["action"].(string)

	if !roomOk || !timeOk || !metricOk || !actionOk {
		http.Error(w, "Missing or invalid fields in JSON data", http.StatusBadRequest)
		return
	}
	query := fmt.Sprintf(
		"INSERT INTO %s (room, time, metric, action) VALUES (?, ?, ?, ?)",
		config.DBTable,
	)
	_, err := DBHandle.Exec(query, room, time, metric, action)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to insert data into database: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"message": "Success"}`))
}
