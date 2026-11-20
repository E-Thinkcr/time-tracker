import json
from datetime import date

import pytest

from timetracker.almacen import CAMPOS, limpiar_celda
from timetracker.auth import ErrorUsuarios, Usuarios, hash_password, verificar_hash
from timetracker.config import DEFAULTS, cargar_config, validar_config
from timetracker.deteccion import InfoVentana, a_app

ITER = 1_000  # rápido para pruebas


@pytest.fixture
def usuarios(tmp_path):
    return Usuarios(tmp_path / "usuarios.json", iteraciones=ITER)


# ---------------------------------------------------------------- auth
def test_password_no_se_guarda_en_texto_plano(usuarios):
    usuarios.crear("admin", "Clave-segura1", "ADMIN")
    contenido = usuarios.ruta.read_text(encoding="utf-8")
    assert "Clave-segura1" not in contenido
    assert "pbkdf2_sha256$" in contenido


def test_verificar(usuarios):
    usuarios.crear("admin", "Clave-segura1", "ADMIN")
    assert usuarios.verificar("admin", "Clave-segura1") == "ADMIN"
    assert usuarios.verificar("admin", "otra-clave1") is None
    assert usuarios.verificar("noexiste", "Clave-segura1") is None


def test_hash_con_sal_distinta():
    a, b = hash_password("igual123x", 1000), hash_password("igual123x", 1000)
    assert a != b
    assert verificar_hash("igual123x", a) and verificar_hash("igual123x", b)
    assert not verificar_hash("igual123x", "basura")


@pytest.mark.parametrize("pwd", ["corta1", "solamenteletras", "1234567890", " Espacio123"])
def test_passwords_debiles_rechazadas(usuarios, pwd):
    with pytest.raises(ErrorUsuarios):
        usuarios.crear("ana", pwd, "USUARIO")


@pytest.mark.parametrize("nombre", ["ab", "con espacio", "../../etc", "a" * 40, "x;rm"])
def test_nombres_invalidos(usuarios, nombre):
    with pytest.raises(ErrorUsuarios):
        usuarios.crear(nombre, "Clave-segura1", "USUARIO")


def test_rol_invalido_y_duplicado(usuarios):
    with pytest.raises(ErrorUsuarios):
        usuarios.crear("ana", "Clave-segura1", "SUPERADMIN")
    usuarios.crear("ana", "Clave-segura1", "USUARIO")
    with pytest.raises(ErrorUsuarios):
        usuarios.crear("ana", "Clave-segura1", "USUARIO")


def test_no_se_elimina_el_ultimo_admin(usuarios):
    usuarios.crear("admin", "Clave-segura1", "ADMIN")
    usuarios.crear("ana", "Clave-segura1", "USUARIO")
    with pytest.raises(ErrorUsuarios):
        usuarios.eliminar("admin")
    usuarios.eliminar("ana")
    assert usuarios.listar() == [("admin", "ADMIN")]


def test_cambiar_password(usuarios):
    usuarios.crear("ana", "Clave-segura1", "USUARIO")
    usuarios.cambiar_password("ana", "Nueva-clave2")
    assert usuarios.verificar("ana", "Clave-segura1") is None
    assert usuarios.verificar("ana", "Nueva-clave2") == "USUARIO"


def test_archivo_danado_no_deja_entrar(usuarios):
    usuarios.ruta.write_text("{roto", encoding="utf-8")
    with pytest.raises(ErrorUsuarios):
        usuarios.verificar("admin", "x")


def test_entradas_manipuladas_se_ignoran(usuarios):
    usuarios.ruta.write_text(json.dumps({"usuarios": {
        "hacker": {"rol": "ROOT", "hash": "x"},
        "sinhash": {"rol": "ADMIN"},
    }}), encoding="utf-8")
    assert usuarios.listar() == []


# ---------------------------------------------------------------- almacén
@pytest.mark.parametrize("valor", ["=HYPERLINK(\"x\")", "+1", "-2+3", "@SUM(A1)"])
def test_inyeccion_de_formulas_neutralizada(valor):
    assert limpiar_celda(valor).startswith("'")


def test_csv_sin_bom_repetido_y_con_encabezado_unico(almacen):
    fila = {k: "" for k in CAMPOS}
    fila.update(fecha="2026-11-18", usuario="ana", titulo="=cmd|' /C calc'!A0", segundos=5)
    almacen.agregar(fila)
    almacen.agregar(fila)
    datos = almacen.ruta("ana", date(2026, 11, 18)).read_bytes()
    assert datos.count(b"\xef\xbb\xbf") == 1
    texto = datos.decode("utf-8-sig")
    assert texto.count("fecha,usuario") == 1
    assert ",=cmd" not in texto


def test_nombre_de_archivo_seguro(almacen):
    ruta = almacen.ruta("../../malo", date(2026, 11, 18))
    assert ruta.parent == almacen.carpeta


# ---------------------------------------------------------------- config / detección
def test_config_invalida_usa_defaults(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({
        "tema": "ROSADO", "max_hueco_segundos": -5, "categorias_productivas": [],
        "capturar_titulos": "si",
    }), encoding="utf-8")
    cfg = cargar_config(tmp_path)
    assert cfg["tema"] == DEFAULTS["tema"]
    assert cfg["max_hueco_segundos"] == DEFAULTS["max_hueco_segundos"]
    assert cfg["categorias_productivas"] == DEFAULTS["categorias_productivas"]
    assert cfg["capturar_titulos"] is False


def test_config_quita_categorias_repetidas():
    cfg = validar_config({"categorias_productivas": ["Task"], "categorias_no_productivas": ["Task", "Lunch"]})
    assert cfg["categorias_no_productivas"] == ["Lunch"]


def test_titulos_solo_si_se_permiten():
    info = InfoVentana(1, "CHROME.EXE", "Correo de  cliente X")
    assert a_app(info, False).titulo == ""
    app = a_app(info, True)
    assert app.sistema == "Web" and app.titulo == "Correo de cliente X"
    assert a_app(None, True).sistema == "Desconocido"
