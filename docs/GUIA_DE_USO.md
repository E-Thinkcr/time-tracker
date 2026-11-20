# Guía de uso — TimeTracker

Esta guía explica, paso a paso y sin necesidad de saber programar, cómo instalar TimeTracker, registrar tu tiempo, administrar usuarios y ver los resultados en el dashboard de Power BI.

**Contenido**

1. [Instalación](#1-instalación)
2. [Primer inicio: crear el administrador](#2-primer-inicio-crear-el-administrador)
3. [Uso diario](#3-uso-diario)
4. [Administración](#4-administración-solo-admin)
5. [Configuración](#5-configuración)
6. [Dashboard de Power BI](#6-dashboard-de-power-bi)
7. [Preguntas frecuentes](#7-preguntas-frecuentes)

---

## 1. Instalación

### Opción A: usar el `.exe` (recomendada para el equipo)

Una persona con Python genera el ejecutable una sola vez:

1. Instala **Python 3.10 o superior** desde [python.org](https://www.python.org/downloads/). Durante la instalación marca la casilla **"Add Python to PATH"**.
2. Descarga el proyecto: en GitHub, botón verde **Code → Download ZIP**, y descomprímelo.
3. Haz doble clic en **`build.bat`**. El archivo instala lo necesario, corre las pruebas y genera el ejecutable.
4. Cuando termine, el ejecutable estará en **`dist\TimeTracker.exe`**.

Ese único archivo se copia a cualquier PC con Windows **y funciona sin instalar Python**.

### Opción B: ejecutar desde el código

```bash
python app.py
```

> Solo se puede abrir **una copia** de la app a la vez en cada equipo, para que el tiempo no se cuente doble.

---

## 2. Primer inicio: crear el administrador

La primera vez que se abre aparece la pantalla **"Primera configuración"**:

1. Escribe un **Usuario** (por ejemplo, `admin`).
2. Escribe una **Contraseña** de **mínimo 8 caracteres, con letras y números**.
3. Confírmala y presiona **Crear administrador**.
4. Inicia sesión con ese usuario.

Después, desde el panel de administración, el administrador crea las cuentas del resto del equipo (ver [sección 4](#4-administración-solo-admin)).

> **Seguridad:** las contraseñas se guardan cifradas. Si alguien falla la contraseña 5 veces, el inicio de sesión se bloquea 30 segundos.

---

## 3. Uso diario

### La ventana principal

| Zona | Qué muestra |
|---|---|
| **Usuario / Fecha** | Quién está registrando y el día de hoy. |
| **Estado** | **ACTIVO**, **EN PAUSA**, **DETENIDO** o **SIN INICIAR**. |
| **App actual** | El programa que estás usando (Excel, Outlook, Web…). Se detecta solo. |
| **Tarea** | El tipo de tarea y su ID o comentario. |
| **Reloj grande** | El tiempo de la tarea actual. |
| **Total del día / Productivo / No productivo** | Los acumulados de hoy. |

### Empezar una tarea

1. Haz clic en el botón de la tarea:
   - **PRODUCTIVAS:** Task, Meeting, Peer Assistance, Peercheck, Sales Assistance, Maintenance.
   - **NO PRODUCTIVAS:** Soporte IT, Break, Lunch, Bathroom.
2. Si es productiva, la app pide un **ID o comentario** (por ejemplo, el número de ticket `TSK-45210`). Escríbelo y presiona **OK**.
3. El reloj empieza a contar. Mientras trabajas, la app reparte el tiempo según el programa que realmente estés usando.

### Cambiar de tarea

Haz clic en otra tarea. Si ya hay una en curso, la app pregunta qué hacer con ella:

- **Sí:** la **pausa**, para retomarla después.
- **No:** la **finaliza**.
- **Cancelar:** no cambia nada.

### Pausar, reanudar y finalizar

| Botón | Qué hace |
|---|---|
| **⏸ Pausar** | Detiene la tarea actual y la pasa a la lista **PAUSADAS**. |
| **▶ Reanudar** | Retoma la tarea seleccionada en **PAUSADAS**. También puedes hacer **doble clic** sobre ella. El tiempo se suma, nunca se duplica. |
| **⏹ Finalizar tarea** | Termina la tarea actual y la pasa a **FINALIZADAS HOY**. |

### Terminar el día

Presiona **Terminar el día y cerrar**: finaliza la tarea en curso, guarda todo y cierra la app. Las tareas **pausadas se conservan** para el día siguiente.

> Si cierras la ventana con la **X**, la tarea en curso se pausa y la puedes reanudar al volver a abrir. Si la PC se apaga de golpe, la app recupera la sesión la próxima vez.

### Menús

| Menú | Opciones |
|---|---|
| **Archivo** | Abrir la carpeta de registros, abrir la carpeta de configuración, Salir. |
| **Ver** | Tema oscuro o tema claro. |
| **Admin** | Panel de administración. También permite guardar los títulos de las ventanas (apagado por defecto, por privacidad). |
| **Ayuda** | Acerca de. |

---

## 4. Administración (solo ADMIN)

Abre **Admin → Panel de administración…** y confirma tu contraseña.

### Pestaña "Usuarios"

- **Crear:** llena Usuario, Contraseña, Confirmar contraseña, elige el **Rol** (`USUARIO` o `ADMIN`) y presiona **Crear usuario**.
- **Restablecer contraseña:** selecciona al usuario en la lista y presiona el botón.
- **Eliminar:** selecciona al usuario y presiona **Eliminar**. No puedes eliminar tu propio usuario.

### Pestaña "Registro manual"

Sirve para agregar tiempo que no se registró, por ejemplo una capacitación fuera de la PC:

1. Elige el **Usuario**.
2. Escribe la **Fecha** en formato `AAAA-MM-DD`. No puede ser una fecha futura.
3. Elige el **Tipo de tarea** y escribe el **ID o comentario**.
4. Escribe los **Minutos** y presiona **Guardar registro**.

Estos registros quedan marcados como **MANUAL**, con el nombre de quien los agregó.

---

## 5. Configuración

La configuración y los datos se guardan en `%LOCALAPPDATA%\TimeTracker\`. Para abrir esa carpeta usa **Archivo → Abrir carpeta de configuración**.

El archivo **`config.json`** se crea solo la primera vez. Lo puedes editar con el Bloc de notas, con la app cerrada:

| Opción | Para qué sirve | Ejemplo |
|---|---|---|
| `carpeta_datos` | Dónde se guardan los usuarios y registros. Vacío significa la carpeta local. | `"C:\\Users\\Ana\\OneDrive\\Equipo\\TimeTracker"` |
| `categorias_productivas` | Los botones verdes. | `["Task", "Meeting"]` |
| `categorias_no_productivas` | Los botones de pausas. | `["Break", "Lunch"]` |
| `capturar_titulos` | Guardar el título de la ventana (sitio web, archivo abierto). | `false` |
| `max_hueco_segundos` | Después de cuántos segundos sin señal (PC suspendida) se deja de contar. | `300` |
| `tema` | `OSCURO` o `CLARO`. | `"OSCURO"` |

**Para trabajar en equipo:** pon en `carpeta_datos` la misma carpeta compartida en todas las PCs (por ejemplo, una de OneDrive o SharePoint sincronizada). Cada persona escribe su propio archivo por día, así que no hay conflictos.

### Los archivos de registros

Se guarda **un CSV por usuario y por día**, por ejemplo `registros_ana_2026-11-18.csv`, con estas columnas:

`fecha, usuario, inicio, fin, tipo_tarea, tarea_id, categoria, sistema, proceso, titulo, segundos, minutos, origen, registrado_por`

Se pueden abrir en Excel, aunque lo ideal es analizarlos en Power BI.

---

## 6. Dashboard de Power BI

El repositorio incluye un dashboard listo en la carpeta **`dashboard/`**, con datos ficticios para probarlo.

### Abrirlo por primera vez

1. Instala **Power BI Desktop**, que es gratis, desde la Microsoft Store.
2. Abre **`dashboard\TimeTracker.pbip`**.
3. Ve a **Inicio → Transformar datos → Editar parámetros**.
4. En **`CarpetaRegistros`** escribe la ruta de la carpeta con los CSV:
   - Para probar: la carpeta **`datos_ejemplo`** del proyecto. Ejemplo: `C:\Users\TuUsuario\Downloads\time-tracker\datos_ejemplo`
   - Para datos reales: la carpeta **`registros`** de la app (o tu `carpeta_datos`).
5. Presiona **Aceptar** y luego **Actualizar** (**Refresh**).

### Qué muestra

**Página "Resumen"**

- Tarjetas con las **Horas**, el **% Productivo**, las **Horas por jornada**, los **Tasks atendidos** y los **Minutos por Task**.
- Las horas por día, productivas y no productivas.
- El **% productivo por usuario**, ordenado de mayor a menor.
- Las horas por tipo de tarea, las horas productivas por aplicación y las horas no productivas por tipo.

**Página "Detalle por usuario"**

- Una tabla comparativa con jornadas, horas, % productivo, Tasks, minutos por Task y % de tiempo manual.
- Un mapa de las **horas productivas por hora del día y día de la semana**.
- El **% productivo por semana** comparado con la **meta del 80 %**.

Usa los filtros de arriba (**usuario** y **Fecha**) para ver a una persona o un periodo.

### Generar nuevos datos de ejemplo

```bash
python datos_ejemplo/generar_datos.py
```

---

## 7. Preguntas frecuentes

**"TimeTracker ya está abierto en este equipo."**
Ya hay una copia abierta; búscala en la barra de tareas. Solo se permite una a la vez.

**Olvidé mi contraseña.**
Un administrador la puede restablecer en **Admin → Panel de administración → Usuarios**.

**Olvidé la contraseña del único administrador.**
Cierra la app, renombra el archivo `usuarios.json` de la carpeta de datos (`%LOCALAPPDATA%\TimeTracker\datos`, o tu `carpeta_datos`), por ejemplo a `usuarios_viejo.json`, y abre la app. Volverá a pedir crear un administrador. Los registros no se pierden.

**La "App actual" dice "Desconocido".**
La detección automática funciona solo en Windows. En otros sistemas el tiempo se registra igual, pero sin el nombre del programa.

**¿Se cuenta el tiempo si la PC se suspende?**
No. Si pasan más de `max_hueco_segundos` sin actividad de la app (por ejemplo, con la PC suspendida), ese tiempo no se cuenta.

**Power BI muestra "(Blank)" o no carga datos.**
Revisa que el parámetro `CarpetaRegistros` apunte a una carpeta que tenga archivos `registros_*.csv`, y presiona **Actualizar**.
