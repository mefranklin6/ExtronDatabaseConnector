#!/usr/bin/env python3

from __future__ import annotations

from socket import gethostbyname, gethostname
from fastapi import FastAPI
from pydantic import BaseModel
import aiomysql
import asyncio
from time import sleep

"""
https://github.com/mefranklin6/ExtronDatabaseConnector

This is a translation layer between
processors and the MySQL database

This needs to be ran on a x86 machine

"""


class DatabaseTools:
    def __init__(self):
        # if using a seperate database server, change the host to the IP address
        self.host = "127.0.0.1"
        self.user = "fast_api"
        self.password = "mypw"  # use a secure method, don't deploy to prod like this
        self.database = "devdb"
        self.table = "testextron"
        self.pool = None

    async def _create_pool(self):
        while True:
            try:
                self.pool = await aiomysql.create_pool(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    db=self.database,
                )
                print("Database connection established")
                break
            except Exception as e:
                print(f"Error connecting to database: {e}")
                sleep(5)  # intentionally blocks the event loop.
                # FastAPI startup will be delayed until the database is connected

    async def db_read(self, sql):
        """Pass a SQL query to the database and return the result"""
        sanatized_input = aiomysql.escape_string(sql)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sanatized_input)
                result = await cur.fetchall()
                return result

    async def _write(self, sql, params=None):
        """Internal only, do not call directly.
        Inputs must be sanatized before calling this function"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if params is not None:
                    await cur.execute(sql, params)
                await conn.commit()

    async def db_write_metric(self, processor, time, metric_name, action):
        (
            sanitized_processor,
            sanitized_time,
            sanitized_metric_name,
            sanitized_action,
        ) = await self.sanitize_inputs(processor, time, metric_name, action)

        formatted_data = await self._format_metric()

        await self._write(
            formatted_data,
            (
                sanitized_processor,
                sanitized_time,
                sanitized_metric_name,
                sanitized_action,
            ),
        )

    async def _format_metric(self):
        return """
                    INSERT INTO {} (Room, Time, Metric, Action)
                    VALUES (%s, %s, %s, %s)
                """.format(
            self.table
        )
        # paramatarizing the query further helps against SQL injection

    async def sanitize_inputs(self, *raw_inputs):
        return tuple(aiomysql.escape_string(input) for input in raw_inputs)

    async def check_connection(self) -> tuple():
        # attempts to grab a new connection and execute a query
        # using 'with' closes the connection after being established
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    return (True, "")
        except Exception as e:
            print(f"DB Connection Error: {e}")
            return (False, f"DB Connection Error: {e}")


db_connect = DatabaseTools()

app = FastAPI()

# waits for the FastAPI server to startup before connecting to the database
app.add_event_handler("startup", db_connect._create_pool)


# not a coroutine
def shutdown_event():
    print("shutting down")
    db_connect.pool.close()


app.add_event_handler("shutdown", shutdown_event)


class Item(BaseModel):
    Processor: str
    Time: str
    Metric: str
    Action: str


@app.post("/data")
async def receive_metric_data(item: Item):
    # print(item.model_dump())
    processor, time, metric, action = (
        item.Processor,
        item.Time,
        item.Metric,
        item.Action,
    )
    await db_connect.db_write_metric(processor, time, metric, action)
    return {"message": "200"}


@app.get("/stress")
async def get_data():
    sql_data = await db_connect.db_read("SELECT * FROM scitemp")
    return {"message": sql_data}


@app.get("/")
async def get_homepage():
    return "You have reached the dev proxy server"


@app.get("/check")
async def called_check_connection():
    result_bool, error_message = await db_connect.check_connection()
    if result_bool == True:
        return "DB Connection is good"
    else:
        return f"""Could not connect to the Database.  
This message is returned from the proxy server 
{error_message}"""


# global killswitch for API metrics.


@app.get("/data/global/enable")
async def global_report_enable() -> str:
    try:
        result_bool, error_message = await asyncio.wait_for(
            db_connect.check_connection(), timeout=3
        )
        if result_bool == True:
            return "True"
        else:
            return "False"
    except:
        return "False"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=gethostbyname(gethostname()), port=8080)
