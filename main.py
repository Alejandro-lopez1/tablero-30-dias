"""Tablero 30 días — App de escritorio (Tkinter, solo librería estándar).

- Modo completo: tablero de 30 días con semanas, checks y notas.
- Modo widget: ventana pequeña siempre visible con las tareas de HOY.
- Auto-renovación: al superar la fecha fin, archiva el ciclo en historial/ y genera
  uno nuevo de 30 días desde hoy con la plantilla semanal.
- Tareas editables: agregar / editar / borrar por día (✎ ✕ + Tarea) y editor de
  rutina semanal para los próximos ciclos.

Uso:
    python main.py            -> modo completo
    python main.py --widget   -> modo widget directo
"""
from __future__ import annotations
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from pathlib import Path

from ciclo import (
    guardar_estado, renovar_si_necesario,
    resumen, nuevo_estado, archivar, cargar_plantilla, guardar_plantilla,
    agregar_tarea, editar_tarea, eliminar_tarea, AREAS_SUGERIDAS,
)

# ---------- rutas ----------
def base_dir() -> Path:
    if getattr(sys, "frozen", False):  # .exe PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BASE = base_dir()
ESTADO = BASE / "estado.json"
HISTORIAL = BASE / "historial"
PLANTILLA = BASE / "plantilla.json"

BG, PANEL, PANEL2 = "#101318", "#171b22", "#1e242d"
TEXT, MUTED, LINE, ACCENT = "#eef2f6", "#9da7b4", "#303846", "#78a9ff"

HOY = date.today().isoformat()


class TableroApp:
    def __init__(self, root: tk.Tk, arrancar_widget: bool = False):
        self.root = root
        self.plantilla = cargar_plantilla(PLANTILLA)
        self.estado, renovado, arch = renovar_si_necesario(
            ESTADO, HISTORIAL, plantilla=self.plantilla)
        root.title("Tablero 30 días — Trabajo + Freelance + Data")

        self.modo = "widget" if arrancar_widget else "full"
        self._vars_checks: dict[str, tk.BooleanVar] = {}

        self._estilo()
        self._build_full()
        self._build_widget()

        if renovado:
            self._refrescar_todo()
            messagebox.showinfo(
                "Nuevo ciclo",
                f"El ciclo anterior terminó y se archivó en:\n{arch.name}\n\n"
                f"Nuevo ciclo: {self.estado['inicio']} → {self.estado['fin']}")
        else:
            self._refrescar_todo()

        self._mostrar_modo(self.modo)
        # Revisar renovación + cambio de día cada 60 s
        self.root.after(60_000, self._tick)

    # ----- estilo -----
    def _estilo(self):
        s = ttk.Style(self.root)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=TEXT)
        s.configure("Card.TLabel", background=PANEL, foreground=TEXT)
        s.configure("Muted.TLabel", background=BG, foreground=MUTED)
        s.configure("MutedCard.TLabel", background=PANEL, foreground=MUTED)
        s.configure("Accent.TLabel", background=BG, foreground=ACCENT)
        s.configure("TButton", background=PANEL2, foreground=TEXT,
                    bordercolor=LINE, focusthickness=0)
        s.map("TButton", background=[("active", "#28303c")])
        s.configure("Horizontal.TProgressbar", background=ACCENT,
                    troughcolor="#2a3039", bordercolor=BG)
        self.root.configure(bg=BG)

    # ================= MODO COMPLETO =================
    def _build_full(self):
        self.full = ttk.Frame(self.root)
        head = ttk.Frame(self.full)
        head.pack(fill="x", padx=14, pady=(12, 6))

        ttk.Label(head, text="Tablero de 30 días",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.lbl_rango = ttk.Label(head, style="Muted.TLabel")
        self.lbl_rango.pack(anchor="w")

        stats = ttk.Frame(head)
        stats.pack(fill="x", pady=(8, 4))
        nums = []
        for txt in ("hechas", "totales", "avance"):
            box = ttk.Frame(stats, style="Card.TFrame", padding=8)
            box.pack(side="left", padx=(0, 8))
            num = ttk.Label(box, style="Card.TLabel", font=("Segoe UI", 14, "bold"))
            num.pack(anchor="w")
            ttk.Label(box, text=txt, style="MutedCard.TLabel").pack(anchor="w")
            nums.append(num)
        self.lbl_done, self.lbl_total, self.lbl_pct = nums

        self.bar = ttk.Progressbar(head, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=(6, 4))

        btns = ttk.Frame(head)
        btns.pack(fill="x", pady=4)
        for txt, cmd in (("◧ Modo widget", lambda: self._mostrar_modo("widget")),
                         ("↻ Nuevo ciclo", self._nuevo_ciclo_manual),
                         ("Rutina semanal", self._editar_rutina),
                         ("Desmarcar todo", self._limpiar),
                         ("Hoy", self._ir_hoy)):
            ttk.Button(btns, text=txt, command=cmd).pack(side="left", padx=(0, 6))

        # zona scroll
        cont = ttk.Frame(self.full)
        cont.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.canvas = tk.Canvas(cont, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.dias_frame = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.dias_frame, anchor="nw")
        self.dias_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
                             lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self.day_widgets: dict[int, ttk.Frame] = {}

    def _ir_hoy(self):
        w = self.day_widgets.get(self._indice_hoy())
        if w is not None:
            self.canvas.update_idletasks()
            y = w.winfo_rooty() - self.dias_frame.winfo_rooty()
            self.canvas.yview_moveto(max(0, y / max(1, self.dias_frame.winfo_height())))

    # ================= MODO WIDGET =================
    def _build_widget(self):
        self.widget = ttk.Frame(self.root, padding=10)
        top = ttk.Frame(self.widget)
        top.pack(fill="x")
        ttk.Label(top, text="Hoy", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.w_fecha = ttk.Label(top, style="Muted.TLabel")
        self.w_fecha.pack(side="left", padx=(6, 0))
        ttk.Button(top, text="⛶", width=3,
                   command=lambda: self._mostrar_modo("full")).pack(side="right")

        self.w_prog = ttk.Label(self.widget, style="Accent.TLabel",
                                font=("Segoe UI", 9, "bold"))
        self.w_prog.pack(anchor="w", pady=(4, 2))
        self.w_bar = ttk.Progressbar(self.widget, mode="determinate", maximum=100)
        self.w_bar.pack(fill="x", pady=(0, 6))

        self.w_tareas = ttk.Frame(self.widget, style="Card.TFrame", padding=8)
        self.w_tareas.pack(fill="both", expand=True)

        pie = ttk.Frame(self.widget)
        pie.pack(fill="x", pady=(8, 0))
        ttk.Button(pie, text="↻ ciclo", command=self._nuevo_ciclo_manual).pack(side="left")
        self.var_top = tk.BooleanVar(value=True)
        ttk.Checkbutton(pie, text="Siempre visible", variable=self.var_top,
                        command=self._aplicar_topmost).pack(side="right")

    def _aplicar_topmost(self):
        self.root.attributes("-topmost", bool(self.var_top.get()) and self.modo == "widget")

    # ================= común =================
    def _mostrar_modo(self, modo: str):
        self.modo = modo
        if modo == "widget":
            self.full.pack_forget()
            self.widget.pack(fill="both", expand=True)
            self.root.geometry("330x460")
            self.root.minsize(300, 380)
            self.root.attributes("-topmost", bool(self.var_top.get()))
            # esquina inferior derecha
            self.root.update_idletasks()
            x = self.root.winfo_screenwidth() - 350
            y = self.root.winfo_screenheight() - 520
            self.root.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        else:
            self.widget.pack_forget()
            self.full.pack(fill="both", expand=True)
            self.root.geometry("1080x700")
            self.root.minsize(800, 550)
            self.root.attributes("-topmost", False)

    def _tick(self):
        nuevo, renovado, arch = renovar_si_necesario(
            ESTADO, HISTORIAL, plantilla=self.plantilla)
        if renovado:
            self.estado = nuevo
            self._refrescar_todo()
            messagebox.showinfo("Nuevo ciclo",
                                f"Ciclo completado. Nuevo ciclo:\n{self.estado['inicio']} → {self.estado['fin']}")
        elif nuevo["inicio"] != self.estado["inicio"]:
            self.estado = nuevo
            self._refrescar_todo()
        else:
            self._refrescar_todo(light=True)
        self.root.after(60_000, self._tick)

    def _indice_hoy(self) -> int:
        for i, d in enumerate(self.estado["days"]):
            if d["date"] >= HOY or d["date"] == date.today().isoformat():
                if d["date"] == date.today().isoformat():
                    return i
        # fallback: primer día no futuro
        hoy = date.today().isoformat()
        for i, d in enumerate(self.estado["days"]):
            if d["date"] == hoy:
                return i
        return 0

    def _refrescar_todo(self, light: bool = False):
        r = resumen(self.estado)
        self.lbl_rango.configure(text=f"{self.estado['inicio']} → {self.estado['fin']} · Empleo IT · Freelance · Data Engineering")
        self.lbl_done.configure(text=str(r["done"]))
        self.lbl_total.configure(text=str(r["total"]))
        self.lbl_pct.configure(text=f"{r['pct']}%")
        self.bar["value"] = r["pct"]
        if light:
            self._pintar_widget()
            return
        # reconstruir días (full)
        for w in self.dias_frame.winfo_children():
            w.destroy()
        self.day_widgets.clear()
        self._vars_checks.clear()
        hoy = date.today().isoformat()
        for w0 in range(0, len(self.estado["days"]), 7):
            grupo = self.estado["days"][w0:w0 + 7]
            ttk.Label(self.dias_frame,
                      text=f"Semana {w0 // 7 + 1} · {grupo[0]['label']} → {grupo[-1]['label']} ({len(grupo)} días)",
                      style="Accent.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 4))
            for idx in range(w0, min(w0 + 7, len(self.estado["days"]))):
                d = self.estado["days"][idx]
                es_hoy = d["date"] == hoy
                card = ttk.Frame(self.dias_frame, style="Card.TFrame", padding=8,
                                 borderwidth=2 if es_hoy else 1, relief="solid")
                card.pack(fill="x", pady=3)
                self.day_widgets[idx] = card
                done = sum(1 for j in range(len(d["tasks"])) if self.estado["checks"].get(f"{idx}-{j}"))
                top = ttk.Frame(card, style="Card.TFrame")
                top.pack(fill="x")
                ttk.Label(top, text=d["label"] + ("  •  HOY" if es_hoy else ""),
                          style="Card.TLabel",
                          font=("Segoe UI", 10, "bold")).pack(side="left")
                ttk.Button(top, text="+ Tarea",
                           command=lambda i=idx: self._dialogo_tarea(i, None)).pack(side="right")
                ttk.Label(top, text=f"{done}/{len(d['tasks'])}",
                          style="MutedCard.TLabel").pack(side="right", padx=(0, 8))
                for j, t in enumerate(d["tasks"]):
                    key = f"{idx}-{j}"
                    var = tk.BooleanVar(value=bool(self.estado["checks"].get(key)))
                    self._vars_checks[key] = var
                    fila_t = tk.Frame(card, bg=PANEL)
                    fila_t.pack(fill="x", pady=1)
                    fila_t.grid_columnconfigure(0, weight=1)
                    cb = tk.Checkbutton(fila_t, text=f"[{t['area']}] {t['text']}",
                                        variable=var, anchor="w", justify="left",
                                        wraplength=620, bg=PANEL, fg=TEXT,
                                        selectcolor=PANEL2, activebackground=PANEL,
                                        activeforeground=TEXT, font=("Segoe UI", 9),
                                        command=lambda k=key: self._toggle(k))
                    cb.grid(row=0, column=0, sticky="ew")
                    tk.Button(fila_t, text="✎ Editar", font=("Segoe UI", 8), width=8,
                              bg=PANEL2, fg=TEXT, relief="flat", activebackground="#28303c",
                              command=lambda i=idx, k=j: self._dialogo_tarea(i, k)
                              ).grid(row=0, column=1, padx=(8, 3), sticky="e")
                    tk.Button(fila_t, text="✕", font=("Segoe UI", 8), width=3,
                              bg=PANEL2, fg=TEXT, relief="flat", activebackground="#28303c",
                              command=lambda i=idx, k=j: self._quitar_tarea(i, k)
                              ).grid(row=0, column=2, sticky="e")
                txt = tk.Text(card, height=2, bg="#11151b", fg=TEXT,
                              insertbackground=TEXT, relief="flat",
                              font=("Segoe UI", 8))
                txt.insert("1.0", self.estado.get("notas", {}).get(str(idx), ""))
                txt.pack(fill="x", pady=(6, 0))
                txt.bind("<FocusOut>", lambda e, i=idx, w=txt: self._guardar_nota(i, w))
        self._pintar_widget()

    def _pintar_widget(self):
        for w in self.w_tareas.winfo_children():
            w.destroy()
        hoy = date.today().isoformat()
        idx = next((i for i, d in enumerate(self.estado["days"]) if d["date"] == hoy), None)
        r = resumen(self.estado)
        if idx is None:
            self.w_fecha.configure(text="")
            self.w_prog.configure(text=f"Ciclo terminado ({r['pct']}%) — se generará uno nuevo")
            self.w_bar["value"] = r["pct"]
            return
        d = self.estado["days"][idx]
        self.w_fecha.configure(text=d["label"])
        hechas = sum(1 for j in range(len(d["tasks"])) if self.estado["checks"].get(f"{idx}-{j}"))
        self.w_prog.configure(text=f"Hoy {hechas}/{len(d['tasks'])} · Total {r['done']}/{r['total']} ({r['pct']}%)")
        self.w_bar["value"] = r["pct"]
        for j, t in enumerate(d["tasks"]):
            key = f"{idx}-{j}"
            var = tk.BooleanVar(value=bool(self.estado["checks"].get(key)))
            cb = tk.Checkbutton(self.w_tareas, text=f"[{t['area']}] {t['text']}",
                                variable=var, anchor="w", justify="left", wraplength=260,
                                bg=PANEL, fg=TEXT, selectcolor=PANEL2,
                                activebackground=PANEL, activeforeground=TEXT,
                                font=("Segoe UI", 9),
                                command=lambda k=key, v=var: self._toggle_widget(k, v))
            cb.pack(fill="x", anchor="w", pady=2)

    def _toggle(self, key: str):
        self.estado["checks"][key] = bool(self._vars_checks[key].get())
        if not self.estado["checks"][key]:
            del self.estado["checks"][key]
        guardar_estado(ESTADO, self.estado)
        self._refrescar_todo(light=False)

    def _toggle_widget(self, key: str, var: tk.BooleanVar):
        if var.get():
            self.estado["checks"][key] = True
        else:
            self.estado["checks"].pop(key, None)
        guardar_estado(ESTADO, self.estado)
        self._refrescar_todo(light=False)

    def _guardar_nota(self, idx: int, w: tk.Text):
        self.estado.setdefault("notas", {})[str(idx)] = w.get("1.0", "end").strip()
        guardar_estado(ESTADO, self.estado)

    # ---------- tareas editables ----------
    def _areas_conocidas(self) -> list[str]:
        areas = list(AREAS_SUGERIDAS)
        for tareas in self.plantilla.values():
            for a, _t in tareas:
                if a not in areas:
                    areas.append(a)
        for d in self.estado["days"]:
            for t in d["tasks"]:
                if t["area"] not in areas:
                    areas.append(t["area"])
        return areas

    def _dialogo_tarea(self, idx: int, ti: int | None):
        """Agregar (ti=None) o editar una tarea de un día del ciclo actual."""
        es_nueva = ti is None
        actual = {"area": "", "text": ""} if es_nueva else self.estado["days"][idx]["tasks"][ti]
        win = tk.Toplevel(self.root)
        win.title("Agregar tarea" if es_nueva else "Editar tarea")
        win.configure(bg=BG)
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Área:").pack(anchor="w", padx=12, pady=(12, 2))
        cmb = ttk.Combobox(win, values=self._areas_conocidas(), width=30)
        cmb.set(actual["area"])
        cmb.pack(padx=12, fill="x")
        ttk.Label(win, text="Tarea:").pack(anchor="w", padx=12, pady=(8, 2))
        ent = ttk.Entry(win, width=34)
        ent.insert(0, actual["text"])
        ent.pack(padx=12, fill="x")
        ent.focus_set()

        def guardar(_e=None):
            area = cmb.get().strip() or "General"
            texto = ent.get().strip()
            if not texto:
                messagebox.showwarning("Falta texto", "Escribí el texto de la tarea.", parent=win)
                return
            if es_nueva:
                agregar_tarea(self.estado, idx, area, texto)
            else:
                editar_tarea(self.estado, idx, ti, area, texto)
            guardar_estado(ESTADO, self.estado)
            win.destroy()
            self._refrescar_todo()

        ttk.Button(win, text="Guardar", command=guardar).pack(pady=12)
        ent.bind("<Return>", guardar)
        win.bind("<Escape>", lambda _e: win.destroy())

    def _quitar_tarea(self, idx: int, ti: int):
        t = self.estado["days"][idx]["tasks"][ti]
        if messagebox.askyesno("Eliminar", f"¿Eliminar «{t['text']}»?"):
            eliminar_tarea(self.estado, idx, ti)
            guardar_estado(ESTADO, self.estado)
            self._refrescar_todo()

    # ---------- rutina semanal (próximos ciclos) ----------
    def _editar_rutina(self):
        win = tk.Toplevel(self.root)
        win.title("Rutina semanal (próximos ciclos)")
        win.configure(bg=BG)
        win.geometry("470x500")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Rutina semanal — se usa al generar los próximos ciclos",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        ttk.Label(win, style="Muted.TLabel",
                  text="No cambia los días ya generados: esos se editan con ✎ en cada tarjeta."
                  ).pack(anchor="w", padx=12)
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        sel = tk.IntVar(value=date.today().weekday())
        marco = ttk.Frame(win)
        marco.pack(fill="x", padx=12, pady=(6, 0))
        lista = tk.Listbox(win, height=12)
        lista.pack(fill="both", expand=True, padx=12, pady=8)

        def mostrar():
            lista.delete(0, "end")
            for a, t in self.plantilla[sel.get()]:
                lista.insert("end", f"[{a}] {t}")

        for i, n in enumerate(dias):
            ttk.Radiobutton(marco, text=n[:3], variable=sel, value=i,
                            command=mostrar).pack(side="left")
        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Button(btns, text="+ Agregar",
                   command=lambda: (self._dialogo_rutina(win, sel.get(), None), mostrar())
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="✎ Editar",
                   command=lambda: (self._dialogo_rutina(win, sel.get(),
                                                         lista.curselection()[0] if lista.curselection() else None),
                                    mostrar()) if lista.curselection() else None
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="✕ Borrar",
                   command=lambda: self._borrar_rutina(sel.get(), lista, mostrar)
                   ).pack(side="left")
        ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=(0, 12))
        mostrar()

    def _borrar_rutina(self, wd: int, lista: tk.Listbox, mostrar):
        s = lista.curselection()
        if not s:
            return
        a, t = self.plantilla[wd][s[0]]
        if messagebox.askyesno("Borrar", f"¿Quitar «[{a}] {t}» de la rutina?"):
            del self.plantilla[wd][s[0]]
            guardar_plantilla(PLANTILLA, self.plantilla)
            mostrar()

    def _dialogo_rutina(self, parent: tk.Toplevel, wd: int, ti: int | None):
        if ti is None and parent is None:
            return
        es_nueva = ti is None
        actual = ["", ""] if es_nueva else list(self.plantilla[wd][ti])
        w = tk.Toplevel(parent)
        w.title("Agregar a rutina" if es_nueva else "Editar rutina")
        w.configure(bg=BG)
        w.transient(parent)
        w.grab_set()
        ttk.Label(w, text="Área:").pack(anchor="w", padx=12, pady=(12, 2))
        cmb = ttk.Combobox(w, values=self._areas_conocidas(), width=30)
        cmb.set(actual[0])
        cmb.pack(padx=12, fill="x")
        ttk.Label(w, text="Tarea:").pack(anchor="w", padx=12, pady=(8, 2))
        ent = ttk.Entry(w, width=34)
        ent.insert(0, actual[1])
        ent.pack(padx=12, fill="x")
        ent.focus_set()

        def guardar(_e=None):
            area = cmb.get().strip() or "General"
            texto = ent.get().strip()
            if not texto:
                messagebox.showwarning("Falta texto", "Escribí el texto de la tarea.", parent=w)
                return
            if es_nueva:
                self.plantilla[wd].append([area, texto])
            else:
                self.plantilla[wd][ti] = [area, texto]
            guardar_plantilla(PLANTILLA, self.plantilla)
            w.destroy()

        ttk.Button(w, text="Guardar", command=guardar).pack(pady=12)
        ent.bind("<Return>", guardar)

    def _limpiar(self):
        if messagebox.askyesno("Confirmar", "¿Desmarcar todas las tareas?"):
            self.estado["checks"] = {}
            guardar_estado(ESTADO, self.estado)
            self._refrescar_todo()

    def _nuevo_ciclo_manual(self):
        if not messagebox.askyesno("Nuevo ciclo",
                                   "¿Archivar el ciclo actual y empezar uno nuevo de 30 días desde hoy?"):
            return
        arch = archivar(ESTADO, HISTORIAL, self.estado)
        self.estado = nuevo_estado(date.today(), plantilla=self.plantilla)
        guardar_estado(ESTADO, self.estado)
        self._refrescar_todo()
        messagebox.showinfo("Nuevo ciclo", f"Archivado en {arch.name}\nNuevo ciclo iniciado.")


def main():
    root = tk.Tk()
    TableroApp(root, arrancar_widget="--widget" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
