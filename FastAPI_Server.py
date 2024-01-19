#!/usr/bin/env python3

from __future__ import annotations

from socket import gethostbyname, gethostname
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
from time import sleep
from mysql_tools import DatabaseTools

"""
https://github.com/mefranklin6/ExtronDatabaseConnector

This is a translation layer between
processors running Extron Control Script and the MySQL database

This needs to be ran on a x86 machine

"""

db_connect = DatabaseTools(
    host="127.0.0.1",
    user="fast_api",
    password="mypw",
    database="devdb",
    table="testextron",
)

app = FastAPI()

# waits for the FastAPI server to startup before connecting to the database
app.add_event_handler("startup", db_connect._create_pool)


# not a coroutine
def shutdown_event():
    print("shutting down")
    db_connect.pool.close()


app.add_event_handler("shutdown", shutdown_event)


class Item(BaseModel):
    processor: str
    time: str
    metric: str
    action: str


@app.post("/data")
async def receive_metric_data(item: Item):
    # print(item.model_dump())
    processor, time, metric, action = (
        item.processor,
        item.time,
        item.metric,
        item.action,
    )
    await db_connect.db_write_metric(processor, time, metric, action)
    return {"message": "200"}


# Example SQL Read

# @app.get("/stress")
# async def get_data():
#     sql_data = await db_connect.db_read("SELECT * FROM scitemp")
#     return {"message": sql_data}


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
        result_bool, _ = await asyncio.wait_for(
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
