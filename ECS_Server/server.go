// EXPERIMENTAL rewrite of the FastAPI Server in Go using Gin


package main

import (
	"database/sql"
	"fmt"

	"github.com/gin-gonic/gin"
	_ "github.com/go-sql-driver/mysql"
)

func main() {
	router := gin.Default()

	router.GET("/status", statusHandler)
	router.GET("/test", testReadHandler)
	router.GET("/disconnect", testDisconnectDB)
	router.POST("/metric", metricHandler)

	router.Run(":8080")
}

var DBConn *sql.DB

const TEST_QUERY string = "SELECT * FROM devdb.testextron"
const TEST_TABLE string = "devdb.testextron"

func init() {
	var err error
	DBConn, err = makeDatabaseConn()
	if err != nil {
		fmt.Printf("Error connecting to database: %v", err)
	}
}

func makeDataSourceName() string {
	user := "admin"
	pw := "yourpassword"
	address := "<ip of mysql server>"
	db_name := "devdb"
	return user + ":" + pw + "@tcp(" + address + ")/" + db_name
}

func makeDatabaseConn() (*sql.DB, error) {
	dsn := makeDataSourceName()
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return db, nil
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

func statusHandler(context *gin.Context) {
	if err := DBConn.Ping(); err != nil {
		context.JSON(500, gin.H{
			"message": "Error connecting to database :" + err.Error(),
		})
		// TODO: try to recover connection
		return
	}

	context.JSON(200, gin.H{
		"message": "Okay",
	})
}

func testReadHandler(context *gin.Context) {
	rows, read_err := readFromDatabase(DBConn, TEST_QUERY)

	if read_err != nil {
		fmt.Println("Error reading from database: ", read_err)
		return
	}
	defer rows.Close()

	res, serialize_err := sqlTojsonSerializer(rows)

	if serialize_err != nil {
		fmt.Println("Error serializing to json: ", serialize_err)
		return
	}

	context.JSON(200, gin.H{
		"message": res,
	})
}

func testDisconnectDB(context *gin.Context) {
	DBConn.Close()

	context.JSON(200, gin.H{
		"message": "Disconnected from database",
	})
}

func metricHandler(context *gin.Context) {
	var jsonData map[string]interface{}
	if err := context.BindJSON(&jsonData); err != nil {
		context.JSON(400, gin.H{
			"error": "Invalid JSON data",
		})
		return
	}

	room, roomOk := jsonData["room"].(string)
	time, timeOk := jsonData["time"].(string)
	metric, metricOk := jsonData["metric"].(string)
	action, actionOk := jsonData["action"].(string)

	if !roomOk || !timeOk || !metricOk || !actionOk {
		context.JSON(400, gin.H{
			"error": "Missing or invalid fields in JSON data",
		})
		return
	}

	query := fmt.Sprintf(
		"INSERT INTO %s (room, time, metric, action) VALUES (?, ?, ?, ?)",
		TEST_TABLE,
	)
	_, err := DBConn.Exec(query, room, time, metric, action)
	if err != nil {
		context.JSON(500, gin.H{
			"error": "Failed to insert data into database",
		})
		return
	}

	context.JSON(200, gin.H{
		"message": "Success",
	})
}
