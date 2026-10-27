"""Pruebas de orquestación de registros y filtros por usuario."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.exceptions import DatabaseUnavailableError, NotFoundError
from app.models.domain import User
from app.services.records_service import RecordInput, RecordsService
from tests.support import FakeAuthRepository, FakeRecordsRepository, make_settings, stored_record


def _input() -> RecordInput:
    return RecordInput(
        nombre="Ana",
        paterno="Pérez",
        materno="López",
        estado="CDMX",
        municipio="Coyoacán",
        latitud=Decimal("19.35"),
        longitud=Decimal("-99.16"),
        temperatura=Decimal("21.5"),
        humedad=Decimal("55"),
        viento=Decimal("12.3"),
        fecha_hora=datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    )


def _context() -> SimpleNamespace:
    return SimpleNamespace(user_id=1, username="ana")


def _users() -> FakeAuthRepository:
    return FakeAuthRepository(
        [
            User(
                id=1,
                username="ana",
                password_hash="x",
                totp_secret_encrypted=None,
                totp_enabled=False,
                created_at=None,
            )
        ]
    )


def _service(settings, postgres, sqlserver, users=None) -> RecordsService:
    return RecordsService(settings, postgres, sqlserver, users or _users())


def test_crear_con_integridad(settings):
    pg = FakeRecordsRepository()
    service = _service(settings, pg, FakeRecordsRepository(servidor="windows"))
    result = service.create(_context(), _input(), "ubuntu")
    assert result.integrity["status"] == "created"
    assert result.integrity["cadena"] == "api-ubuntu"
    assert pg.inserted[0][1] is True


def test_crear_con_integridad_desactivada():
    settings = make_settings(integrity_enabled=False)
    pg = FakeRecordsRepository()
    service = _service(settings, pg, FakeRecordsRepository(servidor="windows"))
    result = service.create(_context(), _input(), "ubuntu")
    assert result.integrity["status"] == "disabled"
    assert pg.inserted[0][1] is False


def test_crear_sin_tabla_de_integridad(settings):
    pg = FakeRecordsRepository(integrity=False, issue="tabla ausente")
    service = _service(settings, pg, FakeRecordsRepository(servidor="windows"))
    result = service.create(_context(), _input(), "ubuntu")
    assert result.integrity["status"] == "unavailable"
    assert result.integrity["detalle"] == "tabla ausente"
    assert pg.inserted[0][1] is False


def test_usuario_numerico_usa_id(settings):
    pg = FakeRecordsRepository(numeric_user=True)
    service = _service(settings, pg, FakeRecordsRepository(servidor="windows"))
    result = service.create(_context(), _input(), "ubuntu")
    assert result.record.usuario == "1"


def test_servidor_invalido(settings):
    service = _service(settings, FakeRecordsRepository(), FakeRecordsRepository())
    with pytest.raises(ValueError):
        service.create(_context(), _input(), "otro")


def test_listar_un_servidor(settings):
    record = stored_record(record_id=3)
    pg = FakeRecordsRepository(records=[record])
    service = _service(settings, pg, FakeRecordsRepository())
    result = service.list_records(
        _context(),
        servidor="ubuntu",
        usuario=None,
        desde=None,
        hasta=None,
        limit=10,
        offset=0,
        order_field="fecha_hora",
        order_desc=True,
    )
    assert result.records == [record]
    assert result.partial is False
    assert result.sources["ubuntu"]["status"] == "ok"


def test_listar_ambos_ordena_por_fecha(settings):
    older = stored_record(
        record_id=1, servidor="ubuntu", fecha_hora=datetime(2026, 1, 1, tzinfo=UTC)
    )
    newer = stored_record(
        record_id=2, servidor="windows", fecha_hora=datetime(2026, 2, 1, tzinfo=UTC)
    )
    service = _service(
        settings,
        FakeRecordsRepository(records=[older]),
        FakeRecordsRepository(servidor="windows", chain_id="api-windows", records=[newer]),
    )
    result = service.list_records(
        _context(),
        servidor="ambos",
        usuario=None,
        desde=None,
        hasta=None,
        limit=10,
        offset=0,
        order_field="fecha_hora",
        order_desc=True,
    )
    assert [record.id for record in result.records] == [2, 1]
    assert result.partial is False
    assert set(result.sources) == {"ubuntu", "windows"}


def test_listar_ambos_parcial(settings):
    record = stored_record(record_id=2, servidor="windows")
    service = _service(
        settings,
        FakeRecordsRepository(fail=True),
        FakeRecordsRepository(servidor="windows", chain_id="api-windows", records=[record]),
    )
    result = service.list_records(
        _context(),
        servidor="ambos",
        usuario=None,
        desde=None,
        hasta=None,
        limit=10,
        offset=0,
        order_field="id",
        order_desc=False,
    )
    assert result.partial is True
    assert result.sources["ubuntu"]["status"] == "unavailable"
    assert result.sources["windows"]["status"] == "ok"
    assert result.records == [record]


def test_listar_ambos_sin_servidores(settings):
    service = _service(
        settings, FakeRecordsRepository(fail=True), FakeRecordsRepository(fail=True)
    )
    with pytest.raises(DatabaseUnavailableError):
        service.list_records(
            _context(),
            servidor="ambos",
            usuario=None,
            desde=None,
            hasta=None,
            limit=10,
            offset=0,
            order_field="id",
            order_desc=False,
        )


def test_filtro_por_usuario_numerico(settings):
    pg = FakeRecordsRepository(numeric_user=True)
    service = _service(settings, pg, FakeRecordsRepository())
    service.list_records(
        _context(),
        servidor="ubuntu",
        usuario="ana",
        desde=None,
        hasta=None,
        limit=10,
        offset=0,
        order_field="id",
        order_desc=False,
    )
    assert pg.last_filters["usuario_filter"] == 1


def test_filtro_por_usuario_desconocido_no_consulta(settings):
    pg = FakeRecordsRepository(numeric_user=True)
    service = _service(settings, pg, FakeRecordsRepository())
    result = service.list_records(
        _context(),
        servidor="ubuntu",
        usuario="nadie",
        desde=None,
        hasta=None,
        limit=10,
        offset=0,
        order_field="id",
        order_desc=False,
    )
    assert result.records == []
    assert pg.last_filters == {}


def test_filtro_textual_se_pasa_tal_cual(settings):
    pg = FakeRecordsRepository(numeric_user=False)
    service = _service(settings, pg, FakeRecordsRepository())
    service.list_records(
        _context(),
        servidor="ubuntu",
        usuario="ana",
        desde=None,
        hasta=None,
        limit=10,
        offset=0,
        order_field="id",
        order_desc=False,
    )
    assert pg.last_filters["usuario_filter"] == "ana"


def test_obtener_registro(settings):
    record = stored_record(record_id=5)
    service = _service(settings, FakeRecordsRepository(records=[record]), FakeRecordsRepository())
    assert service.get_record(_context(), "ubuntu", 5) == record
    with pytest.raises(NotFoundError):
        service.get_record(_context(), "ubuntu", 6)
