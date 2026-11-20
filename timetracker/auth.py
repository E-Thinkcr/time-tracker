"""Usuarios y contraseñas.

- Las contraseñas nunca se guardan en texto plano: PBKDF2-HMAC-SHA256 con sal aleatoria
  (solo librería estándar, sin dependencias).
- La verificación tarda lo mismo exista o no el usuario, para no revelar qué usuarios existen.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
from pathlib import Path

from .config import escribir_json_atomico

log = logging.getLogger(__name__)

ROLES = ("ADMIN", "USUARIO")
ITERACIONES = 600_000  # recomendación OWASP para PBKDF2-SHA256
PATRON_USUARIO = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8


class ErrorUsuarios(ValueError):
    """Error de validación con un mensaje apto para mostrar al usuario."""


def hash_password(password: str, iteraciones: int = ITERACIONES) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, iteraciones)
    return "pbkdf2_sha256${}${}${}".format(
        iteraciones, base64.b64encode(sal).decode(), base64.b64encode(dk).decode()
    )


def verificar_hash(password: str, guardado: str) -> bool:
    try:
        algoritmo, iter_txt, sal_b64, dk_b64 = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(sal_b64), int(iter_txt)
        )
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


def validar_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ErrorUsuarios(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    if password.strip() != password:
        raise ErrorUsuarios("La contraseña no puede empezar ni terminar con espacios.")
    if password.isdigit() or password.isalpha():
        raise ErrorUsuarios("La contraseña debe combinar letras con números o símbolos.")


class Usuarios:
    def __init__(self, ruta: Path, iteraciones: int = ITERACIONES):
        self.ruta = Path(ruta)
        self.iteraciones = iteraciones
        self._dummy = hash_password(secrets.token_hex(8), iteraciones)

    # ---------- lectura / escritura ----------
    def _cargar(self) -> dict:
        if not self.ruta.exists():
            return {}
        try:
            with open(self.ruta, encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError) as e:
            # No se "arregla" solo: si el archivo está dañado, nadie entra hasta revisarlo.
            raise ErrorUsuarios(f"No se pudo leer el archivo de usuarios: {e}") from e
        usuarios = datos.get("usuarios", {}) if isinstance(datos, dict) else {}
        return {
            u: d for u, d in usuarios.items()
            if isinstance(d, dict) and d.get("rol") in ROLES and isinstance(d.get("hash"), str)
        }

    def _guardar(self, usuarios: dict) -> None:
        escribir_json_atomico(self.ruta, {"version": 1, "usuarios": usuarios})

    # ---------- consultas ----------
    def hay_usuarios(self) -> bool:
        return bool(self._cargar())

    def listar(self) -> list[tuple[str, str]]:
        return sorted((u, d["rol"]) for u, d in self._cargar().items())

    def verificar(self, usuario: str, password: str) -> str | None:
        """Devuelve el rol si las credenciales son correctas, si no None."""
        datos = self._cargar().get(usuario)
        if datos is None:
            verificar_hash(password, self._dummy)  # mismo costo de tiempo
            return None
        return datos["rol"] if verificar_hash(password, datos["hash"]) else None

    # ---------- cambios ----------
    def crear(self, usuario: str, password: str, rol: str) -> None:
        usuario = usuario.strip()
        if not PATRON_USUARIO.match(usuario):
            raise ErrorUsuarios(
                "El usuario debe tener de 3 a 32 caracteres: letras, números, punto, guion o guion bajo."
            )
        if rol not in ROLES:
            raise ErrorUsuarios(f"Rol inválido. Opciones: {', '.join(ROLES)}.")
        validar_password(password)
        usuarios = self._cargar()
        if usuario in usuarios:
            raise ErrorUsuarios("Ese usuario ya existe.")
        usuarios[usuario] = {"rol": rol, "hash": hash_password(password, self.iteraciones)}
        self._guardar(usuarios)
        log.info("Usuario creado: %s (%s)", usuario, rol)

    def cambiar_password(self, usuario: str, nueva: str) -> None:
        validar_password(nueva)
        usuarios = self._cargar()
        if usuario not in usuarios:
            raise ErrorUsuarios("Ese usuario no existe.")
        usuarios[usuario]["hash"] = hash_password(nueva, self.iteraciones)
        self._guardar(usuarios)
        log.info("Contraseña cambiada: %s", usuario)

    def eliminar(self, usuario: str) -> None:
        usuarios = self._cargar()
        if usuario not in usuarios:
            raise ErrorUsuarios("Ese usuario no existe.")
        admins = [u for u, d in usuarios.items() if d["rol"] == "ADMIN"]
        if usuarios[usuario]["rol"] == "ADMIN" and len(admins) == 1:
            raise ErrorUsuarios("No se puede eliminar al único administrador.")
        del usuarios[usuario]
        self._guardar(usuarios)
        log.info("Usuario eliminado: %s", usuario)
