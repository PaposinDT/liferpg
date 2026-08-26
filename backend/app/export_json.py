import json
import os
import sys

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


def main():
    data = {}

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)

            tables = [
                row["tablename"]
                for row in cur.fetchall()
            ]

            for table in tables:
                cur.execute(
                    sql.SQL(
                        "SELECT * FROM {}"
                    ).format(
                        sql.Identifier(table)
                    )
                )

                data[table] = cur.fetchall()

    json.dump(
        data,
        sys.stdout,
        indent=2,
        default=str,
    )


if __name__ == "__main__":
    main()
