from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateTable

import models  # noqa: F401  (registers the tables)
from database import Base

parts = [
    str(CreateTable(t).compile(dialect=sqlite.dialect())).strip() + ";"
    for t in Base.metadata.sorted_tables
]
with open("schema.sql", "w") as f:
    f.write("\n\n".join(parts) + "\n")
print("schema.sql written")