#!/usr/bin/env python3
import asyncio

"""!!!!EARLY DEVELOPMENT STAGE!!!!

This is a server that receives data from GCP controllers running
'Extron - Universal Device Driver, Unidirectional RS232 and TCP v1.1

The end goal is to provide some connectivity between GCP controllers,
and external databases.

Set GCP to run on port 9999, and the IP address of this server.

"""

async def handle_echo(reader, writer):
    data = await reader.read(100)
    message = data.decode()
    addr = writer.get_extra_info('peername')

    print(f"Received {message!r} from {addr!r}")

    print(f"Send: {message!r}")
    writer.write(data)
    await writer.drain()

    print("Closing the connection")
    writer.close()

async def main():
    server = await asyncio.start_server(
        handle_echo, '10.248.134.141', 9999)

    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    async with server:
        await server.serve_forever()

asyncio.run(main())







