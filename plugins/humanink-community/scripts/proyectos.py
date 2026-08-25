#!/usr/bin/env python3
"""La cartera de proyectos de HumanInk: declarar, listar y cambiar de proyecto.

    python3 scripts/proyectos.py declarar <carpeta> [--nombre X] [--clave Y]
    python3 scripts/proyectos.py listar [--json]
    python3 scripts/proyectos.py activar <nombre-o-ruta>
    python3 scripts/proyectos.py activo [--json]

Existe porque había DOS nociones de «proyecto» sin relación entre sí:

  · la cartera (`proyectos.json`): nombre, área, estado, hitos — y **ninguna ruta**. Una tarjeta de
    planificación desconectada del disco.
  · el proyecto AWAP: una carpeta con su `.awap/` — sin nombre, sin hitos, y con la ruta viviendo
    dentro de la variable de un proceso que se pierde al reiniciar.

Nada las unía, así que el autor tenía que escribir la ruta en cada comando y no había forma de
preguntar «¿qué proyectos tengo?». Aquí está la clave común: `~/.humanink/estado.json`, que leen
tanto las herramientas MCP como `hi-args.py`.

El registro es local a propósito. Es del autor, funciona sin red, y no hay ninguna razón para que
la lista de libros que alguien está escribiendo viaje a ninguna parte.
"""
import json
import os
import re
import subprocess
import sys

ESTADO = os.path.expanduser("~/.humanink/estado.json")
AQUI = os.path.dirname(os.path.abspath(__file__))


def leer():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("proyectos", [])
    d.setdefault("activo", None)
    return d


def escribir(d):
    os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
    tmp = ESTADO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ESTADO)   # atómico: un Ctrl-C a media escritura no deja el registro a medias


def ident(ruta):
    """Identificador estable a partir de la ruta. Sobrevive a renombrar el proyecto."""
    import hashlib
    return hashlib.sha256(os.path.abspath(ruta).encode()).hexdigest()[:12]


def inventario(carpeta):
    try:
        out = subprocess.run(
            [sys.executable, os.path.join(AQUI, "inventario.py"), carpeta, "--json"],
            capture_output=True, text=True, timeout=60,
        )
        return json.loads(out.stdout) if out.returncode == 0 else {}
    except Exception:
        return {}


def declarar(carpeta, nombre=None, clave=None):
    carpeta = os.path.abspath(os.path.expanduser(carpeta))
    if not os.path.isdir(carpeta):
        return {"error": f"No existe la carpeta: {carpeta}"}
    d = leer()
    inv = inventario(carpeta)
    pid = ident(carpeta)
    proyecto = {
        "id": pid,
        "nombre": nombre or os.path.basename(carpeta),
        "clave": clave,               # el nombre en clave; el título real no viaja
        "ruta": carpeta,
        "tipo": inv.get("tipo", "from_scratch"),
        "manuscrito": (inv.get("manuscrito") or {}).get("fichero"),
        "palabras": (inv.get("manuscrito") or {}).get("palabras"),
        "versiones": inv.get("versiones", 0),
        "faltan": inv.get("faltan", []),
        "deducibles": inv.get("deducibles", []),
    }
    d["proyectos"] = [p for p in d["proyectos"] if p.get("id") != pid] + [proyecto]
    d["activo"] = {"id": pid, "ruta": carpeta, "nombre": proyecto["nombre"]}
    escribir(d)
    return proyecto


def activar(quien):
    d = leer()
    q = quien.lower()
    ruta = os.path.abspath(os.path.expanduser(quien))
    for p in d["proyectos"]:
        if p["id"] == quien or p["ruta"] == ruta or q in p["nombre"].lower():
            d["activo"] = {"id": p["id"], "ruta": p["ruta"], "nombre": p["nombre"]}
            escribir(d)
            return p
    return {"error": f"No tengo ningún proyecto que case con «{quien}». Decláralo primero."}


def imprimir_lista(d):
    if not d["proyectos"]:
        print("\n  No hay proyectos declarados todavía.\n")
        return
    act = (d.get("activo") or {}).get("id")
    print()
    for p in d["proyectos"]:
        marca = "▸" if p["id"] == act else " "
        pal = f"{p['palabras']:,}".replace(",", ".") if p.get("palabras") else "—"
        v = f" · {p['versiones']} versiones" if p.get("versiones", 0) > 1 else ""
        tipo = "manuscrito" if p["tipo"] == "manuscript_first" else "desde cero"
        print(f"  {marca} {p['nombre'][:30]:32s} {pal:>9} pal.{v}")
        print(f"      {tipo} · {p['ruta']}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.split("\n\n")[1])
        sys.exit(1)
    cmd = sys.argv[1]
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    def opt(n):
        m = [a for a in sys.argv if a.startswith(f"--{n}=")]
        if m:
            return m[0].split("=", 1)[1]
        if f"--{n}" in sys.argv:
            i = sys.argv.index(f"--{n}")
            return sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        return None

    if cmd == "declarar":
        r = declarar(args[0] if args else ".", opt("nombre"), opt("clave"))
    elif cmd == "activar":
        r = activar(args[0]) if args else {"error": "Dime qué proyecto activar."}
    elif cmd == "activo":
        r = leer().get("activo") or {"error": "No hay proyecto activo."}
    elif cmd == "listar":
        d = leer()
        if "--json" in sys.argv:
            print(json.dumps(d, ensure_ascii=False, indent=1))
        else:
            imprimir_lista(d)
        sys.exit(0)
    else:
        print(f"  No conozco «{cmd}».")
        sys.exit(1)

    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif "error" in r:
        print("  " + r["error"])
    else:
        print(f"  ✓ {r.get('nombre', r.get('ruta'))}")
        if r.get("deducibles"):
            print("    deducibles del manuscrito: " + " · ".join(r["deducibles"]))
    sys.exit(1 if "error" in r else 0)
