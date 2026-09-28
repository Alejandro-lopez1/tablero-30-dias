"""Lógica de ciclos de 30 días auto-renovables. Sin dependencias externas."""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path

PLANTILLA_SEMANAL = {
    # 0=Lun ... 6=Dom  (weekday() de Python)
    0: [("Freelance", "Contactar 5 comercios"),
        ("IT", "Revisar 2 vacantes"),
        ("Data", "SQL / ETL 60 min")],
    1: [("Freelance", "Preparar o enviar 1 propuesta"),
        ("IT", "Enviar 2 postulaciones"),
        ("Data", "Proyecto Data Engineering 60 min")],
    2: [("Freelance", "Contactar 5 comercios"),
        ("LinkedIn", "Crear o mejorar 1 pieza de contenido"),
        ("Data", "SQL 45 min")],
    3: [("Freelance", "Construir o mejorar el prototipo"),
        ("IT", "Enviar 2 postulaciones"),
        ("Data", "ETL / PostgreSQL 60 min")],
    4: [("Freelance", "Contactar 5 comercios"),
        ("IT", "Revisar métricas de postulaciones"),
        ("Data", "Proyecto práctico 60 min")],
    5: [("Freelance", "Preparar demo o caso de estudio"),
        ("Data", "Proyecto práctico 90 min")],
    6: [("Revisión", "Revisar ingresos, contactos y entrevistas"),
        ("Planificación", "Definir 3 prioridades de la semana")],
}

DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

AREAS_SUGERIDAS = ["Freelance", "IT", "Data", "LinkedIn", "Estudio",
                   "Revisión", "Planificación", "Familia", "Organización", "General"]


def plantilla_por_defecto() -> dict[int, list[list[str]]]:
    """Copia editable de la plantilla semanal ({0=Lun ... 6=Dom} -> [[area, texto], ...])."""
    return {k: [[a, t] for a, t in v] for k, v in PLANTILLA_SEMANAL.items()}


def cargar_plantilla(path: Path) -> dict[int, list[list[str]]]:
    """Lee plantilla.json; si no existe o está corrupta, crea una con los valores por defecto."""
    default = plantilla_por_defecto()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            plant = {}
            for k in range(7):
                items = raw.get(str(k), default[k])
                plant[k] = [[str(a), str(t)] for a, t in items if len(a) or len(t)]
                if not plant[k]:
                    plant[k] = [list(x) for x in default[k]]
            return plant
        except (json.JSONDecodeError, OSError, AttributeError, TypeError, ValueError):
            pass
    guardar_plantilla(path, default)
    return default


def guardar_plantilla(path: Path, plantilla: dict[int, list[list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {str(k): [[a, t] for a, t in plantilla.get(k, [])] for k in range(7)}
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)
    tmp.replace(path)


def generar_dias(fecha_inicio: date, n: int = 30,
                 plantilla: dict[int, list[list[str]]] | None = None) -> list[dict]:
    plantilla = plantilla or plantilla_por_defecto()
    dias = []
    for i in range(n):
        d = fecha_inicio + timedelta(days=i)
        tareas = [{"area": a, "text": t} for a, t in plantilla.get(d.weekday(), [])]
        dias.append({
            "date": d.isoformat(),
            "label": f"{DIAS_ES[d.weekday()]} {d.day:02d}/{d.month:02d}",
            "tasks": tareas,
        })
    return dias


def nuevo_estado(fecha_inicio: date,
                 plantilla: dict[int, list[list[str]]] | None = None) -> dict:
    dias = generar_dias(fecha_inicio, plantilla=plantilla)
    return {
        "inicio": fecha_inicio.isoformat(),
        "fin": (fecha_inicio + timedelta(days=29)).isoformat(),
        "days": dias,
        "checks": {},   # "idx-ti" -> True
        "notas": {},    # "idx" -> str
    }


def cargar_estado(path: Path, hoy: date | None = None,
                  plantilla: dict[int, list[list[str]]] | None = None) -> dict:
    hoy = hoy or date.today()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                st = json.load(f)
            if "days" in st and "inicio" in st and "fin" in st:
                return st
        except (json.JSONDecodeError, OSError):
            pass
    st = nuevo_estado(hoy, plantilla=plantilla)
    guardar_estado(path, st)
    return st


def guardar_estado(path: Path, estado: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)
    tmp.replace(path)


def necesita_renovar(estado: dict, hoy: date | None = None) -> bool:
    hoy = hoy or date.today()
    try:
        fin = date.fromisoformat(estado["fin"])
    except (KeyError, ValueError):
        return True
    return hoy > fin


def resumen(estado: dict) -> dict:
    total = sum(len(d["tasks"]) for d in estado["days"])
    done = sum(1 for v in estado.get("checks", {}).values() if v)
    pct = round(done * 100 / total) if total else 0
    return {"total": total, "done": done, "pct": pct}


def archivar(path_estado: Path, path_historial_dir: Path, estado: dict) -> Path:
    path_historial_dir.mkdir(parents=True, exist_ok=True)
    r = resumen(estado)
    nombre = f"ciclo_{estado.get('inicio', 'sin-fecha')}_{estado.get('fin', '')}__{r['done']}-{r['total']}.json"
    dest = path_historial_dir / nombre
    with open(dest, "w", encoding="utf-8") as f:
        json.dump({**estado, "resumen": r,
                   "archivado_el": datetime.now().isoformat(timespec="seconds")},
                  f, ensure_ascii=False, indent=1)
    return dest


def renovar_si_necesario(path_estado: Path, path_historial_dir: Path,
                         hoy: date | None = None,
                         plantilla: dict[int, list[list[str]]] | None = None
                         ) -> tuple[dict, bool, Path | None]:
    """Devuelve (estado, renovado, ruta_archivo). Si el ciclo terminó, archiva y crea uno nuevo desde hoy."""
    hoy = hoy or date.today()
    estado = cargar_estado(path_estado, hoy, plantilla=plantilla)
    if necesita_renovar(estado, hoy):
        arch = archivar(path_estado, path_historial_dir, estado)
        estado = nuevo_estado(hoy, plantilla=plantilla)
        guardar_estado(path_estado, estado)
        return estado, True, arch
    return estado, False, None


# ---------- edición de tareas del ciclo actual ----------
def agregar_tarea(estado: dict, idx: int, area: str, texto: str) -> None:
    estado["days"][idx]["tasks"].append({"area": area, "text": texto})


def editar_tarea(estado: dict, idx: int, ti: int, area: str, texto: str) -> None:
    estado["days"][idx]["tasks"][ti] = {"area": area, "text": texto}


def eliminar_tarea(estado: dict, idx: int, ti: int) -> None:
    """Borra la tarea y reacomoda los checks (claves 'idx-ti') de ese día."""
    tareas = estado["days"][idx]["tasks"]
    if not 0 <= ti < len(tareas):
        raise IndexError("tarea inexistente")
    del tareas[ti]
    checks = estado.get("checks", {})
    nuevos: dict[str, bool] = {}
    for k, v in checks.items():
        try:
            i, j = (int(x) for x in str(k).split("-", 1))
        except ValueError:
            nuevos[k] = v
            continue
        if i != idx:
            nuevos[k] = v
        elif j < ti:
            nuevos[k] = v
        elif j > ti:
            nuevos[f"{i}-{j - 1}"] = v
        # j == ti: se descarta el check de la tarea borrada
    estado["checks"] = nuevos
