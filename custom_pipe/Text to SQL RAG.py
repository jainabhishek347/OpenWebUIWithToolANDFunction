
"""
with postgres database and Gemini Text-to-SQL model
"""

from pydantic import BaseModel, Field
from typing import Union, Generator, Iterator, Optional
import os
from llama_index.llms.gemini import Gemini
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.core import SQLDatabase, PromptTemplate
import llama_index.core
from sqlalchemy import create_engine
from open_webui.utils.misc import get_last_user_message
import logging


class Pipe:
    class Valves(BaseModel):
        DB_ENGINE: str = Field(
            os.getenv("DB_TYPE", "postgres"),
            description="Database type (supports 'postgres' and 'mysql', defaults to postgres)",
        )
        DB_HOST: str = Field(
            os.getenv("DB_HOST", "host.docker.internal"),
            description="Database hostname",
        )
        DB_PORT: str = Field(
            os.getenv("DB_PORT", "5432"),
            description="Database port (default: 5432)",
        )
        DB_USER: str = Field(
            os.getenv("DB_USER", "postgres"),
            description="Database user to connect with. Make sure this user has permissions to the database and tables you define",
        )
        DB_PASSWORD: str = Field(
            os.getenv("DB_PASSWORD", "password"),
            description="Database user's password",
        )
        DB_DATABASE: str = Field(
            os.getenv("DB_DATABASE", "postgres"),
            description="Database with the data you want to ask questions about",
        )
        DB_TABLE: str = Field(
            # os.getenv("DB_TABLE", "table")
            # "platinum.api__analytics__summery"
            "api__analytics__summery",
            description="Table in the database with the data you want to ask questions about",
        )
        GEMINI_API_KEY: str = Field(
            # os.getenv("GEMINI_API_KEY", "")
            "AIzaSyAki6lpWE1nCJk",
            description="Google Gemini API Key",
        )
        TEXT_TO_SQL_MODEL: str = Field(
            # os.getenv("TEXT_TO_SQL_MODEL", "models/gemini-1.5-flash")
            "models/gemini-1.5-flash",
            description="Gemini model name (e.g., models/gemini-1.5-flash)",
        )

        CONTEXT_WINDOW: int = Field(
            os.getenv("CONTEXT_WINDOW", 30000),
            description="The number of tokens to use in the context window",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.type = "pipe"
        self.name = "Database RAG Pipeline"
        self.engine = None
        self.nlsql_response = ""

        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)
        self.log.addHandler(ch)

    def init_db_connection(self):
        # Update your DB connection string based on selected DB engine - current connection string is for Postgres
        if self.valves.DB_ENGINE == "mysql":
            self.engine = create_engine(
                f"mysql+mysqlconnector://{self.valves.DB_USER}:{self.valves.DB_PASSWORD}@{self.valves.DB_HOST}:{self.valves.DB_PORT}/{self.valves.DB_DATABASE}"
            )
        elif self.valves.DB_ENGINE == "postgres":
            self.engine = create_engine(
                f"postgresql+psycopg2://{self.valves.DB_USER}:{self.valves.DB_PASSWORD}@{self.valves.DB_HOST}:{self.valves.DB_PORT}/{self.valves.DB_DATABASE}"
            )
        else:
            raise ValueError(f"Unsupported database engine: {self.valves.DB_ENGINE}")

        return self.engine

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __event_emitter__=None,
        __event_call__=None,
        __task__=None,
        __task_body__: Optional[dict] = None,
        __valves__=None,
    ) -> Union[str, Generator, Iterator]:
        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Connecting to the database...", "done": False},
            }
        )

        print(f"pipe:{__name__}")

        print(__event_emitter__)
        print(__event_call__)

        # Create database reader for Postgres
        self.init_db_connection()
        sql_database = SQLDatabase(
            self.engine, include_tables=self.valves.DB_TABLE.split(",")
        )
        await __event_emitter__(
            {
                "type": "status",  # We set the type here
                "data": {"description": "Querying the database...", "done": False},
            }
        )
        print("******************************\n******set up llm connection")
        # Set up LLM connection
        llm = Gemini(
            model=self.valves.TEXT_TO_SQL_MODEL,
            api_key=self.valves.GEMINI_API_KEY,
            temperature=0.0,  # for deterministic SQL generation
        )

        # Set up the custom prompt used when generating SQL queries from text
        text_to_sql_prompt = """
            Table: public.api__analytics__summery
            Columns:
            - request_id: unique request identifier
            - created_at: timestamp of the request
            - status: success or failure
            - endpoint: API endpoint called
            
            Given an input question, generate a SQL query using only these columns...
            """

        text_to_sql_template = PromptTemplate(text_to_sql_prompt)

        query_engine = NLSQLTableQueryEngine(
            sql_database=sql_database,
            tables=self.valves.DB_TABLE.split(","),
            llm=llm,
            text_to_sql_prompt=text_to_sql_template,
            embed_model="local",
            streaming=False,
        )
        print("*********\nquery_engine:", query_engine)
        user_message = get_last_user_message(body["messages"])

        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Returning response...", "done": True},
            }
        )

        response = query_engine.query(user_message)
        print("Generated SQL:", response.response)
        llm_output = response.response
        self.log.debug("Full LLM output: %s", llm_output)
        llm_output = response.response

        import re

        match = re.search(r"SQLQuery:\s*(.*)", llm_output)
        if match:
            generated_sql = match.group(1)
            print("Generated SQL:", generated_sql)
            self.log.debug("Generated SQL: %s", generated_sql)

            with self.engine.connect() as conn:
                result = conn.execute(generated_sql)
                rows = result.fetchall()
                print("SQL Result:", rows)
                self.log.debug("SQL Result: %s", rows)

            return f"Generated SQL: {generated_sql}\nResult from DB: {rows}"
