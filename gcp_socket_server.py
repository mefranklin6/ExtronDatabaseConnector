#!/usr/bin/env python3

import asyncio
from mysql_tools import DatabaseTools
import json
from datetime import datetime
from socket import gethostbyname, gethostname

"""
In-development server to unidirectionally connect GCP processors to an external database

This needs to be ran on a x86 server

The GCP processors require the driver:
'Extron - Universial Device Driver, Unidirectional RS232 and TCP v1.1"

For metrics, format the 'User Defined String" as follows:
{"room":"<room_name>","metric":"<metric_name>","action":"<action_name>"}

Example:
{"room": "GLNN210", "metric": "Camera", "action": "Started"}

then call 'User Defined Command' to send it out the processor to here

"""
TCP_PORT = 9999


db_connect = DatabaseTools(
    host="127.0.0.1",
    user="fast_api",
    password="mypw",
    database="devdb",
    table="testextron",
)


async def create_pool():
    return await db_connect._create_pool()


async def format_metric_data(data):
    data_dict = json.loads(data)
    room = data_dict.get("room")

    # GCP processors currently have no way of giving us time,
    # so we stamp it at the server level
    time_now = datetime.now()
    time = time_now.strftime("%Y-%m-%dT%H:%M:%S")

    metric = data_dict.get("metric")
    action = data_dict.get("action")

    return room, time, metric, action


async def receive_data(reader, writer):
    data = await reader.read(100)
    message = data.decode()
    addr = writer.get_extra_info("peername")

    print(f"Received {message!r} from {addr!r}")

    room, time, metric, action = await format_metric_data(message)
    await db_connect.db_write_metric(room, time, metric, action)

    await writer.drain()

    writer.close()


async def main():
    await create_pool()

    server = await asyncio.start_server(
        receive_data, gethostbyname(gethostname()), TCP_PORT
    )

    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}")

    async with server:
        await server.serve_forever()


asyncio.run(main())
