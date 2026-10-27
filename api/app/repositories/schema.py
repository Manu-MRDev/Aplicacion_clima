"""Introspección de esquemas existentes (solo lectura) y citado seguro de identificadores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

class SchemaMismatchError(Exception):
    """El esquema real no coincide con lo que la aplicación necesita."""


def quote_pg(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def quote_mssql(identifier: str) -> str:
    return "[" + identifier.replace("]", "]]") + "]"


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    is_identity: bool = False


@dataclass(frozen=True)
class TableProfile:
    schema: str
    name: str
    columns: tuple[ColumnInfo, ...]
    primary_key: tuple[str, ...] = ()

    def find(self, *candidates: str) -> ColumnInfo | None:
        lowered = {column.name.lower(): column for column in self.columns}
        for candidate in candidates:
            column = lowered.get(candidate.lower())
            if column is not None:
                return column
        return None

    def require(self, logical_name: str, *aliases: str) -> ColumnInfo:
        column = self.find(logical_name, *aliases)
        if column is None:
            raise SchemaMismatchError(
                f"El esquema de {self.schema}.{self.name} no contiene la columna requerida "
                f"{logical_name!r}"
            )
        return column

    @property
    def qualified_name(self) -> str:
        return f"{quote_pg(self.schema)}.{quote_pg(self.name)}"

    def has(self, *candidates: str) -> bool:
        return self.find(*candidates) is not None


def pg_table_profile(conn, schema: str, table: str) -> TableProfile | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, udt_name, is_nullable, is_identity
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        rows = cur.fetchall()
    if not rows:
        return None

    columns = tuple(
        ColumnInfo(
            name=row[0],
            data_type=(row[2] or row[1] or "").lower(),
            nullable=(row[3] == "YES"),
            is_identity=(row[4] == "YES"),
        )
        for row in rows
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
            """,
            (f"{quote_pg(schema)}.{quote_pg(table)}",),
        )
        primary_key = tuple(row[0] for row in cur.fetchall())

    return TableProfile(schema=schema, name=table, columns=columns, primary_key=primary_key)


def mssql_table_profile(cursor, schema: str, table: str) -> TableProfile | None:
    object_name = f"{schema}.{table}"
    cursor.execute("SELECT OBJECT_ID(?, 'U')", (object_name,))
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None

    cursor.execute(
        """
        SELECT c.name, t.name, c.max_length, c.is_nullable, c.is_identity, c.column_id
        FROM sys.columns c
        JOIN sys.types t ON c.user_type_id = t.user_type_id
        WHERE c.object_id = OBJECT_ID(?)
        ORDER BY c.column_id
        """,
        (object_name,),
    )
    columns = tuple(
        ColumnInfo(
            name=item[0],
            data_type=(item[1] or "").lower(),
            nullable=bool(item[3]),
            is_identity=bool(item[4]),
        )
        for item in cursor.fetchall()
    )

    cursor.execute(
        """
        SELECT c.name
        FROM sys.index_columns ic
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        JOIN sys.indexes i ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE ic.object_id = OBJECT_ID(?) AND i.is_primary_key = 1
        ORDER BY ic.key_ordinal
        """,
        (object_name,),
    )
    primary_key = tuple(item[0] for item in cursor.fetchall())
    return TableProfile(schema=schema, name=table, columns=columns, primary_key=primary_key)


def require_columns(profile: TableProfile, logical: dict[str, Iterable[str]]) -> dict[str, ColumnInfo]:
    return {key: profile.require(key, *aliases) for key, aliases in logical.items()}
