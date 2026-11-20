"""Detección de la ventana activa.

En Windows usa la API del sistema con ctypes (sin pywin32 ni psutil).
En otros sistemas devuelve None y la app registra "Desconocido".
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class InfoVentana:
    pid: int
    proceso: str  # p. ej. "chrome.exe"
    titulo: str


@dataclass(frozen=True)
class App:
    """Lo que se guarda en el registro para la aplicación en uso."""
    sistema: str
    proceso: str = ""
    titulo: str = ""


DESCONOCIDA = App("Desconocido")

_SISTEMAS = {
    "explorer.exe": "Explorador de archivos",
    "chrome.exe": "Web",
    "msedge.exe": "Web",
    "firefox.exe": "Web",
    "excel.exe": "Excel",
    "winword.exe": "Word",
    "powerpnt.exe": "PowerPoint",
    "outlook.exe": "Outlook",
    "olk.exe": "Outlook",
    "ms-teams.exe": "Teams",
    "teams.exe": "Teams",
    "pbidesktop.exe": "Power BI",
}

MAX_TITULO = 120


def a_app(info: InfoVentana | None, capturar_titulos: bool) -> App:
    if info is None or not info.proceso:
        return DESCONOCIDA
    proceso = info.proceso.lower()
    sistema = _SISTEMAS.get(proceso, proceso.removesuffix(".exe"))
    titulo = " ".join(info.titulo.split())[:MAX_TITULO] if capturar_titulos else ""
    return App(sistema, proceso, titulo)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL

    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    def _nombre_proceso(pid: int) -> str:
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            tam = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(tam.value)
            if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(tam)):
                return os.path.basename(buf.value)
            return ""
        finally:
            _kernel32.CloseHandle(handle)

    def ventana_activa() -> InfoVentana | None:
        try:
            hwnd = _user32.GetForegroundWindow()
            if not hwnd:
                return None
            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            largo = _user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(largo + 1)
            _user32.GetWindowTextW(hwnd, buf, largo + 1)
            return InfoVentana(pid.value, _nombre_proceso(pid.value), buf.value)
        except OSError:
            log.exception("Error leyendo la ventana activa")
            return None

    def activar_dpi() -> None:
        """Texto nítido en pantallas con escala (125 %, 150 %...)."""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

else:
    def ventana_activa() -> InfoVentana | None:
        return None

    def activar_dpi() -> None:
        pass
