import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://node@localhost:5432/searcheval",
)
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
DEFAULT_INDEX = os.getenv("OPENSEARCH_INDEX", "docs")
