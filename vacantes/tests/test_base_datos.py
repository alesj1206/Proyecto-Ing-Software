import pytest
from django.db import connection


@pytest.mark.django_db
def test_postgres_con_pgvector():
    assert connection.vendor == "postgresql"
    with connection.cursor() as c:
        c.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        assert c.fetchone() is not None
