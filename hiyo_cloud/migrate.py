"""Initial schema migration. Run as a controlled deployment job, never per API startup."""

import os
from .models import Base, database

if __name__ == "__main__":
    engine, _ = database(os.environ["HIYO_DATABASE_URL"])
    Base.metadata.create_all(engine)
    print(
        "Hiyo cloud schema initialized. Future schema changes require versioned migrations."
    )
