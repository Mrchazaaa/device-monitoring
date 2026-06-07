from datetime import datetime, timezone

from app.database import PostgreSQLDatabase, SQLiteDatabase, create_database


def test_create_database_selects_postgresql_adapter():
    database = create_database("postgresql://user:password@localhost/presence")

    assert isinstance(database, PostgreSQLDatabase)
    assert database.url == "postgresql://user:password@localhost/presence"


def test_postgresql_adapter_converts_placeholders():
    class Connection:
        def execute(self, sql, params):
            self.sql = sql
            self.params = params

    connection = Connection()
    database = PostgreSQLDatabase("postgresql://localhost/presence")

    database.execute(connection, "SELECT * FROM devices WHERE mac = ? AND online = ?", ("mac", True))

    assert connection.sql == "SELECT * FROM devices WHERE mac = %s AND online = %s"
    assert connection.params == ("mac", True)


def test_sqlite_adapter_serializes_datetime_parameters(tmp_path):
    class Connection:
        def execute(self, sql, params):
            self.sql = sql
            self.params = params

    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    connection = Connection()
    database = SQLiteDatabase(str(tmp_path / "presence.db"))

    database.execute(connection, "SELECT ?", (now,))

    assert connection.params == (now.isoformat(),)


def test_postgresql_adapter_returns_inserted_id():
    class Cursor:
        def fetchone(self):
            return {"id": 42}

    class Connection:
        def execute(self, sql, params):
            self.sql = sql
            self.params = params
            return Cursor()

    connection = Connection()
    database = PostgreSQLDatabase("postgresql://localhost/presence")

    device_id = database.insert(connection, "INSERT INTO devices (mac) VALUES (?)", ("mac",))

    assert device_id == 42
    assert connection.sql == "INSERT INTO devices (mac) VALUES (%s) RETURNING id"
