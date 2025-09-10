from sqlalchemy import create_engine, text


class Tools:
    def __init__(self):
        self.connection_string = "redshift+psycopg2://analytics_api:2WTdwC0LyMTr76d6jP@host.docker.internal:5439/dev?sslmode=require"

    def query_redshift(self, query: str):
        """Run a SQL query on Amazon Redshift"""
        try:
            engine = create_engine(self.connection_string)
            with engine.connect() as conn:
                result = conn.execute(text(query))
                # return [dict(row) for row in result]
                return [row[0] for row in result]
        except Exception as e:
            return {"error": str(e)}

    def get_tools(self):
        return [
            {
                "name": "query_redshift",
                "description": "Run SQL query on Redshift and return results as JSON",
                "parameters": {"query": "SQL query string"},
                "function": self.query_redshift,
            }
        ]
