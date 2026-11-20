"""Interfaz gráfica (tkinter)."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tkinter as tk
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import APP_NOMBRE, __version__
from . import deteccion, instancia
from .almacen import Almacen, nombre_seguro
from .auth import ROLES, ErrorUsuarios, Usuarios
from .config import (
    cargar_config, carpeta_app, carpeta_datos, escribir_json_atomico, guardar_config,
)
from .tracker import ACTIVO, ErrorTracker, Tracker

log = logging.getLogger(__name__)

PALETAS = {
    "OSCURO": {
        "bg": "#1e1f26", "panel": "#2a2c36", "fg": "#e8e8ec", "sutil": "#a0a3b1",
        "acento": "#4ea8de", "campo": "#23252e", "prod": "#2f7d5b", "noprod": "#5c6170",
        "control": "#3a6ea5", "peligro": "#c0392b", "activo": "#5fd18b",
    },
    "CLARO": {
        "bg": "#f3f5f8", "panel": "#ffffff", "fg": "#1d1f24", "sutil": "#5b6070",
        "acento": "#1f6feb", "campo": "#ffffff", "prod": "#2e7d32", "noprod": "#616975",
        "control": "#1f6feb", "peligro": "#c62828", "activo": "#2e7d32",
    },
}
FUENTE = ("Segoe UI", 10)
FUENTE_NEGRITA = ("Segoe UI", 10, "bold")
FUENTE_TITULO = ("Segoe UI", 14, "bold")
FUENTE_RELOJ = ("Consolas", 26, "bold")
INTERVALO_MS = 1000
GUARDAR_CADA_TICKS = 15


def formato_hms(segundos: float) -> str:
    s = int(max(0, segundos))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def abrir_carpeta(ruta: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(ruta)  # noqa: S606 - ruta propia de la app
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(ruta)])
        else:
            subprocess.Popen(["xdg-open", str(ruta)])
    except OSError:
        messagebox.showinfo("Carpeta", str(ruta))


class Interfaz:
    def __init__(self, root: tk.Tk, base: Path, cfg: dict):
        self.root = root
        self.base = base
        self.cfg = cfg
        self.datos = carpeta_datos(cfg, base)
        self.usuarios = Usuarios(self.datos / "usuarios.json")
        self.almacen = Almacen(self.datos / "registros")

        self.tracker: Tracker | None = None
        self.usuario = ""
        self.rol = ""
        self._tick_id = None
        self._ticks = 0
        self._version_listas = -1
        self._fallos = 0
        self.lbl: dict[str, tk.Label] = {}

        root.title(APP_NOMBRE)
        root.protocol("WM_DELETE_WINDOW", self.al_cerrar)
        root.report_callback_exception = self._error_no_controlado

    @property
    def c(self) -> dict:
        return PALETAS[self.cfg["tema"]]

    # ================================================================ helpers
    def _error_no_controlado(self, exc, val, tb):
        log.error("Error no controlado", exc_info=(exc, val, tb))
        messagebox.showerror(
            "Error inesperado",
            f"{val}\n\nEl detalle quedó en el log:\n{self.base / 'app.log'}",
            parent=self.root,
        )

    def _limpiar(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        self.root.config(menu="", bg=self.c["bg"])
        self.lbl = {}
        self._estilos()

    def _estilos(self) -> None:
        c = self.c
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure("TNotebook", background=c["bg"], borderwidth=0)
        st.configure("TNotebook.Tab", background=c["panel"], foreground=c["fg"], padding=(12, 6))
        st.map("TNotebook.Tab", background=[("selected", c["acento"])],
               foreground=[("selected", "#ffffff")])
        st.configure("TCombobox", fieldbackground=c["campo"], background=c["panel"],
                     foreground=c["fg"], arrowcolor=c["fg"])
        st.map("TCombobox", fieldbackground=[("readonly", c["campo"])],
               foreground=[("readonly", c["fg"])])
        self.root.option_add("*TCombobox*Listbox.background", c["campo"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["fg"])

    def _label(self, padre, texto="", fg=None, font=FUENTE, bg=None, **kw) -> tk.Label:
        return tk.Label(padre, text=texto, bg=bg or self.c["panel"], fg=fg or self.c["fg"],
                        font=font, **kw)

    def _boton(self, padre, texto, cmd, color="control") -> tk.Button:
        col = self.c[color]
        return tk.Button(
            padre, text=texto, command=cmd, bg=col, fg="#ffffff", activebackground=col,
            activeforeground="#ffffff", relief="flat", bd=0, font=FUENTE_NEGRITA,
            padx=10, pady=7, cursor="hand2", disabledforeground="#d0d0d0",
        )

    def _entry(self, padre, show=None) -> tk.Entry:
        return tk.Entry(padre, show=show, bg=self.c["campo"], fg=self.c["fg"],
                        insertbackground=self.c["fg"], relief="solid", bd=1, font=FUENTE)

    def _tarjeta(self, titulo: str, subtitulo: str) -> tk.Frame:
        fondo = tk.Frame(self.root, bg=self.c["bg"])
        fondo.pack(fill="both", expand=True)
        tarjeta = tk.Frame(fondo, bg=self.c["panel"], padx=28, pady=24,
                           highlightbackground=self.c["acento"], highlightcolor=self.c["acento"],
                           highlightthickness=2)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")
        self._label(tarjeta, APP_NOMBRE, fg=self.c["acento"], font=FUENTE_NEGRITA).pack(anchor="w")
        self._label(tarjeta, titulo, font=FUENTE_TITULO).pack(anchor="w")
        if subtitulo:
            self._label(tarjeta, subtitulo, fg=self.c["sutil"], wraplength=300,
                        justify="left").pack(anchor="w")
        tk.Frame(tarjeta, bg=self.c["panel"], height=12).pack()
        return tarjeta

    def _campo(self, padre, texto, show=None) -> tk.Entry:
        self._label(padre, texto).pack(anchor="w")
        e = self._entry(padre, show)
        e.pack(fill="x", pady=(0, 10), ipady=3)
        return e

    def _centrar(self, ancho: int, alto: int) -> None:
        x = max(0, (self.root.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.root.winfo_screenheight() - alto) // 3)
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    # ================================================================ inicio
    def arrancar(self) -> None:
        try:
            hay = self.usuarios.hay_usuarios()
        except ErrorUsuarios as e:
            messagebox.showerror(APP_NOMBRE, str(e))
            self.root.destroy()
            return
        self.mostrar_login() if hay else self.mostrar_setup()

    def mostrar_setup(self) -> None:
        self._limpiar()
        self._centrar(460, 440)
        t = self._tarjeta("Primera configuración",
                          "Crea la cuenta de administrador. Podrá crear los demás usuarios.")
        u = self._campo(t, "Usuario")
        p = self._campo(t, "Contraseña (mín. 8, letras y números)", show="•")
        p2 = self._campo(t, "Confirmar contraseña", show="•")
        err = self._label(t, "", fg=self.c["peligro"], wraplength=300, justify="left")

        def crear(_=None):
            if p.get() != p2.get():
                err.config(text="Las contraseñas no coinciden.")
                return
            try:
                self.usuarios.crear(u.get(), p.get(), "ADMIN")
            except ErrorUsuarios as e:
                err.config(text=str(e))
                return
            messagebox.showinfo(APP_NOMBRE, "Administrador creado. Ahora inicia sesión.")
            self.mostrar_login()

        self._boton(t, "Crear administrador", crear).pack(fill="x", pady=(4, 6))
        err.pack(anchor="w")
        self.root.bind("<Return>", crear)
        u.focus_set()

    def mostrar_login(self) -> None:
        self._limpiar()
        self._centrar(440, 380)
        t = self._tarjeta("Iniciar sesión", "")
        u = self._campo(t, "Usuario")
        p = self._campo(t, "Contraseña", show="•")
        err = self._label(t, "", fg=self.c["peligro"], wraplength=300, justify="left")
        maximo = self.cfg["max_intentos_login"]
        espera = self.cfg["bloqueo_login_segundos"]

        def desbloquear():
            self._fallos = 0
            if btn.winfo_exists():
                btn.config(state="normal")
                err.config(text="")

        def entrar(_=None):
            if str(btn["state"]) == "disabled":
                return
            usuario = u.get().strip()
            self.root.config(cursor="watch")
            self.root.update_idletasks()
            try:
                rol = self.usuarios.verificar(usuario, p.get())
            except ErrorUsuarios as e:
                messagebox.showerror(APP_NOMBRE, str(e))
                return
            finally:
                self.root.config(cursor="")
            if rol:
                log.info("Inicio de sesión: %s (%s)", usuario, rol)
                self.root.unbind("<Return>")
                self.iniciar_sesion(usuario, rol)
                return
            # No se registra el usuario tecleado: a veces la gente escribe ahí la contraseña.
            log.warning("Intento de inicio de sesión fallido")
            self._fallos += 1
            p.delete(0, tk.END)
            if self._fallos >= maximo:
                btn.config(state="disabled")
                err.config(text=f"Demasiados intentos. Espera {espera} segundos.")
                self.root.after(espera * 1000, desbloquear)
            else:
                err.config(text="Usuario o contraseña incorrectos.")

        btn = self._boton(t, "Entrar", entrar)
        btn.pack(fill="x", pady=(4, 6))
        err.pack(anchor="w")
        self.root.bind("<Return>", entrar)
        u.focus_set()

    def iniciar_sesion(self, usuario: str, rol: str) -> None:
        self.usuario, self.rol = usuario, rol
        self.tracker = Tracker(
            usuario, self.almacen, self.cfg["categorias_productivas"],
            max_hueco_segundos=self.cfg["max_hueco_segundos"],
        )
        recuperada = False
        ruta = self._ruta_estado()
        if ruta.exists():
            try:
                with open(ruta, encoding="utf-8") as f:
                    recuperada = self.tracker.restaurar(json.load(f))
            except (OSError, ValueError):
                log.exception("No se pudo leer el estado guardado")
        self._guardar_estado()
        self._centrar(820, 800)
        self.root.minsize(700, 640)
        self.construir_principal()
        self._tick()
        if recuperada and self.tracker.pausadas:
            messagebox.showinfo(
                APP_NOMBRE,
                "Se recuperó tu sesión anterior. Las tareas que estaban en curso "
                "quedaron en PAUSADAS para que las reanudes.",
            )

    # ================================================================ ventana principal
    def construir_principal(self) -> None:
        self._limpiar()
        self._version_listas = -1
        c = self.c
        self._menu()

        cont = tk.Frame(self.root, bg=c["bg"])
        cont.pack(fill="both", expand=True, padx=14, pady=12)

        # ---- información
        info = tk.Frame(cont, bg=c["panel"], padx=14, pady=10,
                        highlightbackground=c["acento"], highlightcolor=c["acento"],
                        highlightthickness=2)
        info.pack(fill="x")
        for col in (1, 3):
            info.grid_columnconfigure(col, weight=1)

        def fila(r, col, titulo, clave):
            self._label(info, titulo, fg=c["sutil"]).grid(row=r, column=col, sticky="w", padx=(0, 8))
            lab = self._label(info, "", font=FUENTE_NEGRITA, anchor="w")
            lab.grid(row=r, column=col + 1, sticky="we")
            self.lbl[clave] = lab

        fila(0, 0, "Usuario", "usuario")
        fila(0, 2, "Fecha", "fecha")
        fila(1, 0, "Estado", "estado")
        fila(1, 2, "App actual", "app")
        self._label(info, "Tarea", fg=c["sutil"]).grid(row=2, column=0, sticky="w")
        self.lbl["tarea"] = self._label(info, "", font=FUENTE_NEGRITA, anchor="w", wraplength=600,
                                        justify="left")
        self.lbl["tarea"].grid(row=2, column=1, columnspan=3, sticky="we")
        self.lbl["reloj"] = self._label(info, "00:00:00", fg=c["acento"], font=FUENTE_RELOJ)
        self.lbl["reloj"].grid(row=3, column=0, columnspan=4, pady=(6, 4))

        tot = tk.Frame(info, bg=c["panel"])
        tot.grid(row=4, column=0, columnspan=4, sticky="we")
        for i, (titulo, clave) in enumerate(
            (("Total del día", "total"), ("Productivo", "prod"), ("No productivo", "noprod"))
        ):
            tot.grid_columnconfigure(i, weight=1)
            caja = tk.Frame(tot, bg=c["panel"])
            caja.grid(row=0, column=i)
            self._label(caja, titulo, fg=c["sutil"]).pack()
            self.lbl[clave] = self._label(caja, "00:00:00", font=FUENTE_NEGRITA)
            self.lbl[clave].pack()

        # ---- categorías
        def grupo(titulo, categorias, color):
            self._label(cont, titulo, bg=c["bg"], fg=c["sutil"], font=FUENTE_NEGRITA).pack(
                anchor="w", pady=(12, 4))
            marco = tk.Frame(cont, bg=c["bg"])
            marco.pack(fill="x")
            columnas = 3
            for i in range(columnas):
                marco.grid_columnconfigure(i, weight=1, uniform="cat")
            for i, cat in enumerate(categorias):
                self._boton(marco, cat, lambda x=cat: self.on_categoria(x), color).grid(
                    row=i // columnas, column=i % columnas, sticky="we", padx=3, pady=3)

        grupo("PRODUCTIVAS", self.cfg["categorias_productivas"], "prod")
        grupo("NO PRODUCTIVAS", self.cfg["categorias_no_productivas"], "noprod")

        # ---- controles
        ctr = tk.Frame(cont, bg=c["bg"])
        ctr.pack(fill="x", pady=(12, 0))
        for i, (txt, cmd) in enumerate((
            ("⏸  Pausar", self.on_pausar),
            ("▶  Reanudar", self.on_reanudar),
            ("⏹  Finalizar tarea", self.on_finalizar_tarea),
        )):
            ctr.grid_columnconfigure(i, weight=1, uniform="ctr")
            self._boton(ctr, txt, cmd).grid(row=0, column=i, sticky="we", padx=3)

        # ---- listas
        listas = tk.Frame(cont, bg=c["bg"])
        listas.pack(fill="both", expand=True, pady=(12, 0))
        listas.grid_columnconfigure(0, weight=1, uniform="l")
        listas.grid_columnconfigure(1, weight=1, uniform="l")
        listas.grid_rowconfigure(1, weight=1)
        self.lista_p = self._lista(listas, 0, "PAUSADAS  (doble clic para reanudar)")
        self.lista_f = self._lista(listas, 1, "FINALIZADAS HOY")
        self.lista_p.bind("<Double-Button-1>", self.on_reanudar)

        # ---- pie
        self._boton(cont, "Terminar el día y cerrar", self.on_terminar_dia, "peligro").pack(
            fill="x", pady=(12, 6))
        pie = tk.Frame(cont, bg=c["bg"])
        pie.pack(fill="x")
        self._label(pie, f"Registros: {self.almacen.carpeta}", bg=c["bg"], fg=c["sutil"],
                    font=("Segoe UI", 8), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(pie, text="Abrir carpeta", command=lambda: abrir_carpeta(self.almacen.carpeta),
                  relief="flat", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 8),
                  cursor="hand2").pack(side="right")

        self.refrescar()

    def _lista(self, padre, col, titulo) -> tk.Listbox:
        c = self.c
        self._label(padre, titulo, bg=c["bg"], fg=c["sutil"], font=FUENTE_NEGRITA).grid(
            row=0, column=col, sticky="w", padx=3)
        marco = tk.Frame(padre, bg=c["bg"])
        marco.grid(row=1, column=col, sticky="nsew", padx=3)
        lb = tk.Listbox(marco, bg=c["campo"], fg=c["fg"], selectbackground=c["acento"],
                        selectforeground="#ffffff", relief="solid", bd=1, font=FUENTE,
                        activestyle="none", exportselection=False, height=6)
        sb = tk.Scrollbar(marco, command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return lb

    def _menu(self) -> None:
        barra = tk.Menu(self.root)
        archivo = tk.Menu(barra, tearoff=0)
        archivo.add_command(label="Abrir carpeta de registros",
                            command=lambda: abrir_carpeta(self.almacen.carpeta))
        archivo.add_command(label="Abrir carpeta de configuración",
                            command=lambda: abrir_carpeta(self.base))
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.al_cerrar)
        barra.add_cascade(label="Archivo", menu=archivo)

        ver = tk.Menu(barra, tearoff=0)
        self._var_tema = tk.StringVar(value=self.cfg["tema"])
        ver.add_radiobutton(label="Tema oscuro", value="OSCURO", variable=self._var_tema,
                            command=self.cambiar_tema)
        ver.add_radiobutton(label="Tema claro", value="CLARO", variable=self._var_tema,
                            command=self.cambiar_tema)
        barra.add_cascade(label="Ver", menu=ver)

        if self.rol == "ADMIN":
            adm = tk.Menu(barra, tearoff=0)
            adm.add_command(label="Panel de administración…", command=self.abrir_admin)
            self._var_titulos = tk.BooleanVar(value=self.cfg["capturar_titulos"])
            adm.add_checkbutton(label="Guardar títulos de ventana (en este equipo)",
                                variable=self._var_titulos, command=self.cambiar_titulos)
            barra.add_cascade(label="Admin", menu=adm)

        ayuda = tk.Menu(barra, tearoff=0)
        ayuda.add_command(label="Acerca de", command=lambda: messagebox.showinfo(
            "Acerca de", f"{APP_NOMBRE} {__version__}\nRegistro de tiempo por tarea."))
        barra.add_cascade(label="Ayuda", menu=ayuda)
        self.root.config(menu=barra)

    # ================================================================ ciclo
    def _tick(self) -> None:
        try:
            info = deteccion.ventana_activa()
            app = None
            if info is not None and info.pid != os.getpid():  # ignorar la propia ventana
                app = deteccion.a_app(info, self.cfg["capturar_titulos"])
            self.tracker.tick(app)
            self.refrescar()
            self._ticks += 1
            if self._ticks % GUARDAR_CADA_TICKS == 0:
                self._guardar_estado()
        except Exception:  # el ciclo no debe morir nunca
            log.exception("Error en el ciclo de actualización")
        self._tick_id = self.root.after(INTERVALO_MS, self._tick)

    def refrescar(self) -> None:
        t = self.tracker
        if not t or "reloj" not in self.lbl:
            return
        ahora = datetime.now()
        tot = t.totales_dia(ahora)
        app = t.app_actual
        self.lbl["usuario"].config(text=f"{self.usuario} ({self.rol.lower()})")
        self.lbl["fecha"].config(text=ahora.strftime("%Y-%m-%d"))
        self.lbl["estado"].config(text=t.estado,
                                  fg=self.c["activo"] if t.estado == ACTIVO else self.c["fg"])
        self.lbl["app"].config(text=(f"{app.sistema} · {app.titulo}" if app.titulo else app.sistema)[:60])
        self.lbl["tarea"].config(text=f"{t.actual.tipo} — {t.actual.tarea_id}" if t.actual else "—")
        self.lbl["reloj"].config(text=formato_hms(t.segundos_tarea_actual(ahora)))
        self.lbl["total"].config(text=formato_hms(tot["Total"]))
        self.lbl["prod"].config(text=formato_hms(tot["Productiva"]))
        self.lbl["noprod"].config(text=formato_hms(tot["No productiva"]))

        if t.version != self._version_listas:  # solo se redibuja si algo cambió
            self._version_listas = t.version
            self.lista_p.delete(0, tk.END)
            for p in t.pausadas:
                self.lista_p.insert(tk.END, f"{p.tipo} — {p.tarea_id}  ({formato_hms(p.segundos_previos)})")
            self.lista_f.delete(0, tk.END)
            for f in t.finalizadas:
                self.lista_f.insert(tk.END, f"{f.fin}  {f.tipo} — {f.tarea_id}  ({formato_hms(f.segundos)})")

    # ================================================================ acciones
    def _resolver_actual(self) -> bool:
        t = self.tracker
        if not t.activa:
            return True
        r = messagebox.askyesnocancel(
            "Tarea en curso",
            f"«{t.actual.tipo} — {t.actual.tarea_id}» está en curso.\n\n"
            "Sí: pausarla (podrás reanudarla)\nNo: finalizarla\nCancelar: no hacer nada",
            parent=self.root,
        )
        if r is None:
            return False
        t.pausar() if r else t.finalizar_actual()
        return True

    def on_categoria(self, tipo: str) -> None:
        tarea_id = tipo
        if tipo in self.cfg["categorias_productivas"]:
            r = simpledialog.askstring("Nueva tarea", f"ID o comentario para «{tipo}»:",
                                       parent=self.root)
            if r is None:
                return
            tarea_id = r[:200]
        if not self._resolver_actual():
            return
        self.tracker.iniciar(tipo, tarea_id)
        self._despues_de_accion()

    def on_pausar(self) -> None:
        self.tracker.pausar()
        self._despues_de_accion()

    def on_reanudar(self, _event=None) -> None:
        if not self.tracker.pausadas:
            return
        sel = self.lista_p.curselection()
        idx = sel[0] if sel else 0
        if not self._resolver_actual():
            return
        try:
            self.tracker.reanudar(idx)
        except ErrorTracker as e:
            messagebox.showwarning(APP_NOMBRE, str(e))
        self._despues_de_accion()

    def on_finalizar_tarea(self) -> None:
        self.tracker.finalizar_actual()
        self._despues_de_accion()

    def on_terminar_dia(self) -> None:
        if not messagebox.askyesno(
            "Terminar el día",
            "Se finalizará la tarea en curso y se cerrará la aplicación.\n"
            "Las tareas pausadas quedan guardadas para la próxima vez.\n\n¿Continuar?",
        ):
            return
        self.tracker.finalizar_actual()
        self._guardar_estado()
        messagebox.showinfo(APP_NOMBRE, f"Registros guardados en:\n{self.almacen.carpeta}")
        self._salir()

    def al_cerrar(self) -> None:
        if self.tracker and self.tracker.activa:
            if not messagebox.askokcancel(
                "Cerrar",
                "La tarea en curso se pausará y podrás reanudarla al volver a abrir.\n\n¿Cerrar?",
            ):
                return
            self.tracker.pausar()
        if self.tracker:
            self._guardar_estado()
        self._salir()

    def _salir(self) -> None:
        if self._tick_id:
            self.root.after_cancel(self._tick_id)
        log.info("Aplicación cerrada")
        self.root.destroy()

    def _despues_de_accion(self) -> None:
        self._guardar_estado()
        self.refrescar()

    def _ruta_estado(self) -> Path:
        return self.base / f"estado_{nombre_seguro(self.usuario)}.json"

    def _guardar_estado(self) -> None:
        try:
            escribir_json_atomico(self._ruta_estado(), self.tracker.exportar_estado())
        except OSError:
            log.exception("No se pudo guardar el estado")

    def cambiar_tema(self) -> None:
        self.cfg["tema"] = self._var_tema.get()
        guardar_config(self.base, self.cfg)
        self.construir_principal()

    def cambiar_titulos(self) -> None:
        self.cfg["capturar_titulos"] = bool(self._var_titulos.get())
        guardar_config(self.base, self.cfg)
        log.info("Captura de títulos: %s", self.cfg["capturar_titulos"])

    def abrir_admin(self) -> None:
        pwd = simpledialog.askstring("Administración", "Confirma tu contraseña:", show="•",
                                     parent=self.root)
        if pwd is None:
            return
        try:
            rol = self.usuarios.verificar(self.usuario, pwd)
        except ErrorUsuarios as e:
            messagebox.showerror(APP_NOMBRE, str(e))
            return
        if rol != "ADMIN":
            log.warning("Acceso al panel de administración denegado: %s", self.usuario)
            messagebox.showerror(APP_NOMBRE, "Contraseña incorrecta o sin permisos de administrador.")
            return
        PanelAdmin(self)


class PanelAdmin(tk.Toplevel):
    def __init__(self, ui: Interfaz):
        super().__init__(ui.root)
        self.ui = ui
        c = ui.c
        self.title("Administración")
        self.configure(bg=c["bg"])
        self.transient(ui.root)
        self.geometry("560x460")
        self.grab_set()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        nb.add(self._tab_usuarios(nb), text="Usuarios")
        nb.add(self._tab_manual(nb), text="Registro manual")

    # ------------------------------------------------ usuarios
    def _tab_usuarios(self, nb) -> tk.Frame:
        ui, c = self.ui, self.ui.c
        f = tk.Frame(nb, bg=c["panel"], padx=12, pady=12)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)
        f.grid_rowconfigure(1, weight=1)

        ui._label(f, "Usuarios", font=FUENTE_NEGRITA).grid(row=0, column=0, sticky="w")
        self.lista_u = tk.Listbox(f, bg=c["campo"], fg=c["fg"], selectbackground=c["acento"],
                                  font=FUENTE, exportselection=False, relief="solid", bd=1)
        self.lista_u.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        acc = tk.Frame(f, bg=c["panel"])
        acc.grid(row=2, column=0, sticky="we", padx=(0, 10), pady=(6, 0))
        ui._boton(acc, "Restablecer contraseña", self._reset_pwd).pack(fill="x", pady=2)
        ui._boton(acc, "Eliminar", self._eliminar, "peligro").pack(fill="x", pady=2)

        form = tk.Frame(f, bg=c["panel"])
        form.grid(row=0, column=1, rowspan=3, sticky="nsew")
        ui._label(form, "Nuevo usuario", font=FUENTE_NEGRITA).pack(anchor="w")
        self.e_user = ui._campo(form, "Usuario")
        self.e_pass = ui._campo(form, "Contraseña", show="•")
        self.e_pass2 = ui._campo(form, "Confirmar contraseña", show="•")
        ui._label(form, "Rol").pack(anchor="w")
        self.cb_rol = ttk.Combobox(form, values=ROLES, state="readonly")
        self.cb_rol.set("USUARIO")
        self.cb_rol.pack(fill="x", pady=(0, 10))
        ui._boton(form, "Crear usuario", self._crear).pack(fill="x")

        self._recargar_usuarios()
        return f

    def _recargar_usuarios(self) -> None:
        self._usuarios = self.ui.usuarios.listar()
        self.lista_u.delete(0, tk.END)
        for u, rol in self._usuarios:
            self.lista_u.insert(tk.END, f"{u}  ({rol})")
        if hasattr(self, "cb_usuario"):
            self.cb_usuario.config(values=[u for u, _ in self._usuarios])

    def _seleccionado(self) -> str | None:
        sel = self.lista_u.curselection()
        if not sel:
            messagebox.showinfo("Usuarios", "Selecciona un usuario de la lista.", parent=self)
            return None
        return self._usuarios[sel[0]][0]

    def _crear(self) -> None:
        if self.e_pass.get() != self.e_pass2.get():
            messagebox.showerror("Usuarios", "Las contraseñas no coinciden.", parent=self)
            return
        try:
            self.ui.usuarios.crear(self.e_user.get(), self.e_pass.get(), self.cb_rol.get())
        except ErrorUsuarios as e:
            messagebox.showerror("Usuarios", str(e), parent=self)
            return
        for e in (self.e_user, self.e_pass, self.e_pass2):
            e.delete(0, tk.END)
        self._recargar_usuarios()
        messagebox.showinfo("Usuarios", "Usuario creado.", parent=self)

    def _reset_pwd(self) -> None:
        u = self._seleccionado()
        if not u:
            return
        p1 = simpledialog.askstring("Restablecer", f"Nueva contraseña para {u}:", show="•", parent=self)
        if p1 is None:
            return
        p2 = simpledialog.askstring("Restablecer", "Confírmala:", show="•", parent=self)
        if p1 != p2:
            messagebox.showerror("Usuarios", "Las contraseñas no coinciden.", parent=self)
            return
        try:
            self.ui.usuarios.cambiar_password(u, p1)
        except ErrorUsuarios as e:
            messagebox.showerror("Usuarios", str(e), parent=self)
            return
        messagebox.showinfo("Usuarios", "Contraseña actualizada.", parent=self)

    def _eliminar(self) -> None:
        u = self._seleccionado()
        if not u:
            return
        if u == self.ui.usuario:
            messagebox.showerror("Usuarios", "No puedes eliminar tu propio usuario.", parent=self)
            return
        if not messagebox.askyesno("Usuarios", f"¿Eliminar a {u}? Sus registros no se borran.",
                                   parent=self):
            return
        try:
            self.ui.usuarios.eliminar(u)
        except ErrorUsuarios as e:
            messagebox.showerror("Usuarios", str(e), parent=self)
            return
        self._recargar_usuarios()

    # ------------------------------------------------ registro manual
    def _tab_manual(self, nb) -> tk.Frame:
        ui, c = self.ui, self.ui.c
        f = tk.Frame(nb, bg=c["panel"], padx=12, pady=12)
        ui._label(f, "Agrega tiempo que no se registró (queda marcado como MANUAL).",
                  fg=c["sutil"]).pack(anchor="w", pady=(0, 8))

        ui._label(f, "Usuario").pack(anchor="w")
        self.cb_usuario = ttk.Combobox(f, values=[u for u, _ in self._usuarios], state="readonly")
        self.cb_usuario.set(ui.usuario)
        self.cb_usuario.pack(fill="x", pady=(0, 10))

        self.e_fecha = ui._campo(f, "Fecha (AAAA-MM-DD)")
        self.e_fecha.insert(0, date.today().isoformat())

        ui._label(f, "Tipo de tarea").pack(anchor="w")
        cats = ui.cfg["categorias_productivas"] + ui.cfg["categorias_no_productivas"]
        self.cb_tipo = ttk.Combobox(f, values=cats, state="readonly")
        self.cb_tipo.set(cats[0])
        self.cb_tipo.pack(fill="x", pady=(0, 10))

        self.e_tarea = ui._campo(f, "ID de tarea / comentario")
        self.e_min = ui._campo(f, "Minutos")
        ui._boton(f, "Guardar registro", self._guardar_manual).pack(fill="x")
        return f

    def _guardar_manual(self) -> None:
        try:
            fecha = date.fromisoformat(self.e_fecha.get().strip())
        except ValueError:
            messagebox.showerror("Registro manual", "Fecha inválida. Usa AAAA-MM-DD.", parent=self)
            return
        if fecha > date.today():
            messagebox.showerror("Registro manual", "La fecha no puede ser futura.", parent=self)
            return
        try:
            minutos = float(self.e_min.get().strip().replace(",", "."))
        except ValueError:
            messagebox.showerror("Registro manual", "Minutos inválidos.", parent=self)
            return
        usuario = self.cb_usuario.get()
        if usuario not in [u for u, _ in self._usuarios]:
            messagebox.showerror("Registro manual", "Selecciona un usuario.", parent=self)
            return
        try:
            self.ui.tracker.registrar_manual(
                usuario, fecha, self.cb_tipo.get(), self.e_tarea.get()[:200], minutos,
                registrado_por=self.ui.usuario,
            )
        except ErrorTracker as e:
            messagebox.showerror("Registro manual", str(e), parent=self)
            return
        log.info("Registro manual: %s %s %s min por %s", usuario, fecha, minutos, self.ui.usuario)
        self.e_tarea.delete(0, tk.END)
        self.e_min.delete(0, tk.END)
        self.ui.refrescar()
        messagebox.showinfo("Registro manual", "Registro agregado.", parent=self)


# ==================================================================== arranque
def configurar_log(base: Path) -> None:
    h = RotatingFileHandler(base / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h])


def main() -> None:
    deteccion.activar_dpi()
    base = carpeta_app()
    configurar_log(base)
    log.info("Inicio %s %s", APP_NOMBRE, __version__)

    root = tk.Tk()
    bloqueo = instancia.adquirir(base)
    if bloqueo is None:
        root.withdraw()
        messagebox.showwarning(APP_NOMBRE, f"{APP_NOMBRE} ya está abierto en este equipo.")
        root.destroy()
        return

    cfg = cargar_config(base)
    ui = Interfaz(root, base, cfg)
    ui.arrancar()
    root.mainloop()
    bloqueo.close()


if __name__ == "__main__":
    main()
