from __future__ import annotations

import aiomysql
from time import sleep

"""This is the database connector used for FastAPI_Server and GCP_Socket_Server"""


class DatabaseTools:
    def __init__(self, host, user, password, database, table):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.table = table
        self.pool = None

    async def _create_pool(self):
        """Creates a pool of connections to the database"""
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

    async def check_connection(self) -> tuple():
        """
        attempts to grab a new connection from the pool and run a test query
        returns a tuple of (success bool, error_message)
        """
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    return (True, "")
        except Exception as e:
            print(f"DB Connection Error: {e}")
            return (False, f"DB Connection Error: {e}")

    async def sanitize_inputs(self, *raw_inputs) -> tuple():
        """
        Uses aiomysql.escape_string to sanitize inputs
        returns a tuple of sanitized inputs
        """
        return tuple(aiomysql.escape_string(input) for input in raw_inputs)

    async def db_read(self, sql) -> list():
        """Pass a SQL query to the database and return the result"""
        sanatized_input = await self.sanitize_inputs(sql)
        sanatized_input_str = " ".join(sanatized_input)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sanatized_input_str)
                result = await cur.fetchall()
                return result

    async def _write(self, sql, params=None) -> None:
        """Internal only, do not call directly.
        Inputs must be sanatized before calling this function"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if params is not None:
                    await cur.execute(sql, params)
                await conn.commit()

    async def db_write_metric(self, processor, time, metric_name, action) -> None:
        """Takes metric data sent from the processor and writes it to the database"""
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
                    INSERT INTO {} (room, time, metric, action)
                    VALUES (%s, %s, %s, %s)
                """.format(
            self.table
        )
        # paramatarizing the query further helps against SQL injection
