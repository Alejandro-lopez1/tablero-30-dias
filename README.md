# Tablero 30 días — App de escritorio

Tablero de 30 días para organizar tu semana y no olvidar ningún pendiente.
App de escritorio para Windows con Tkinter (solo librería estándar, sin dependencias para correrla).

## Funciones

- **Tablero completo**: 30 días en semanas, con checks, notas por día y barra de avance.
- **Modo widget**: ventana pequeña siempre visible con las tareas de HOY.
- **Auto-renovación**: al terminar el ciclo se archiva en `historial/` y se genera uno nuevo de 30 días desde hoy.
- **Tareas editables**: en cada día `+ Tarea` agrega, `✎ Editar` modifica y `✕` borra (los checks se reacomodan solos).
- **Rutina semanal editable**: botón `Rutina semanal` para cambiar la plantilla Lun–Dom que se usa en los próximos ciclos (no toca los días ya generados).

## Uso rápido (sin instalar nada)

```bat
python main.py            :: tablero completo
python main.py --widget   :: modo widget directo
```

O doble clic en `abrir_tablero.bat` / `abrir_widget.bat`.

## El .exe

Descargalo desde **Releases** (`Tablero30Dias.exe`). No requiere Python.
Para ponerlo como widget: ejecutalo con `--widget`, o corre `crear_accesos_directos.ps1`
(clic derecho > Ejecutar con PowerShell) para crear accesos en el Escritorio y en Inicio con Windows.

```powershell
.\Tablero30Dias.exe --widget
```

## Generar el .exe vos mismo

```powershell
.\build_exe.ps1
```

Queda en `dist/Tablero30Dias.exe`. Requiere `pip install -r requirements.txt`.

## Archivos de datos (se crean solos, no se suben al repo)

| Archivo          | Qué guarda                              |
|------------------|-----------------------------------------|
| `estado.json`    | Ciclo actual: días, checks y notas      |
| `plantilla.json` | Rutina semanal para próximos ciclos     |
| `historial/`     | Ciclos anteriores archivados            |

## Estructura

```text
├── main.py                     # App Tkinter (tablero + widget)
├── ciclo.py                    # Ciclos, plantilla y edición de tareas
├── requirements.txt            # Solo PyInstaller (para el .exe)
├── build_exe.ps1               # Genera dist/Tablero30Dias.exe
├── crear_accesos_directos.ps1  # Accesos en Escritorio e Inicio
├── abrir_tablero.bat / abrir_widget.bat
└── README.md
```
