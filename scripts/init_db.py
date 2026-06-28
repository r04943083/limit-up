"""Create / migrate the local SQLite database."""
from lucore.config import get_settings
from lucore.db import init_db

if __name__ == "__main__":
    init_db()
    print(f"Initialized LU database at {get_settings().db_path}")
