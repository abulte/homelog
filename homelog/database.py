import os

import dataset


def connect():
    db_url = os.getenv("DATABASE_URL")
    db_url = db_url.replace("postgres://", "postgresql://")
    return dataset.connect(db_url, sqlite_wal_mode=False)
