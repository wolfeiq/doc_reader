import asyncio
import logging
from pathlib import Path

from app.db.bootstrap import create_schema
from app.services.seeding import (
    clear_database,
    clear_vectors,
    seed_documents,
)

DATA_PATH = Path("data/openai-agents-sdk")


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    asyncio.run(create_schema())
    asyncio.run(clear_vectors())
    asyncio.run(clear_database())
    asyncio.run(seed_documents(DATA_PATH))


if __name__ == "__main__":
    main()
