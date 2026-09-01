#!/usr/bin/env python3
"""cli.py — la única puerta del motor OOXML.

POR QUÉ UN DESPACHADOR. Cada script del motor tiene su propio `argparse` y seguirá teniéndolo: el
plugin los invoca por ruta (`python3 scripts/ooxml/intervene.py …`) y eso no se toca. Pero el
empaquetado sí necesita una sola puerta: PyInstaller congela UN punto de entrada, y seis binarios
serían seis copias de libpython y unos doscientos Mach-O que firmar.

Así que esto no reimplementa nada. Reordena `sys.argv` y llama al `main()` que ya existe.

    ooxml version                      qué motor es este (va a la bitácora con cada aplicación)
    ooxml listar     <docx> --json     párrafos con su índice, su texto vivo y su huella
    ooxml lote       <docx> --original o.txt --propuesta p.txt --autor "X" --json
    ooxml aplicar    <in> <out> --lote L.json --marcado --autor "X" --json
    ooxml verificar  <nuevo> --base <anterior> --json
    ooxml comparar   <nuevo> <anterior> --json   |   --serie <carpeta> --json
    ooxml decisiones <anterior> <siguiente> --json
    ooxml inventario <docx>
"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# subcomando → (módulo, nombre del programa para los mensajes de error de argparse)
SUB = {
    "listar": ("intervene", "ooxml listar"),
    "aplicar": ("intervene", "ooxml aplicar"),
    "lote": ("lote", "ooxml lote"),
    "verificar": ("verify_docx", "ooxml verificar"),
    "comparar": ("comparar", "ooxml comparar"),
    "decisiones": ("decisiones", "ooxml decisiones"),
    "escanear": ("fase0_scan", "ooxml escanear"),
}

VERSION = "1.0.0"


def _hash_motor():
    """El hash del motor, para poder contestar dentro de un año a «qué versión escribió el b29».

    Se lee de MOTOR.sha256 si está (lo genera sync-motor.sh y viaja empaquetado); si no, se calcula
    de los fuentes. Sin él la pregunta no tiene respuesta, y es una pregunta del certificado.
    """
    aqui = os.path.dirname(os.path.abspath(__file__))
    manifiesto = os.path.join(aqui, "MOTOR.sha256")
    if os.path.exists(manifiesto):
        with open(manifiesto, encoding="utf-8") as f:
            return f.read().strip().split()[0]
    import hashlib
    h = hashlib.sha256()
    for nombre in sorted(os.listdir(aqui)):
        if nombre.endswith(".py"):
            with open(os.path.join(aqui, nombre), "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def _version():
    try:
        from lxml import etree
        v_lxml = ".".join(str(x) for x in etree.LXML_VERSION)
    except Exception:
        v_lxml = None
    print(json.dumps({
        "version": VERSION,
        "motor": _hash_motor(),
        "python": sys.version.split()[0],
        "lxml": v_lxml,
        "subcomandos": sorted(list(SUB) + ["version", "inventario"]),
    }, ensure_ascii=False))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 1
    sub, resto = argv[0], argv[1:]

    if sub == "version":
        return _version()
    if sub == "inventario":
        # docxtc no tiene argparse: su CLI es posicional.
        import docxtc
        if not resto:
            print("uso: ooxml inventario <fichero.docx>", file=sys.stderr)
            return 1
        print(json.dumps(docxtc.inventario(resto[0]), ensure_ascii=False, indent=2))
        return 0
    if sub not in SUB:
        print(f"subcomando desconocido: {sub}\n", file=sys.stderr)
        print(__doc__.strip(), file=sys.stderr)
        return 1

    modulo, prog = SUB[sub]
    # `listar` y `aplicar` son el mismo módulo: dentro de `intervene.py` los distingue la bandera
    # `--listar`, que aquí ya la dice el subcomando. Se inyecta para no duplicar su argparse.
    if sub == "listar" and "--listar" not in resto:
        resto = resto + ["--listar"]
    sys.argv = [prog] + resto          # el argparse de cada módulo, intacto
    return importlib.import_module(modulo).main() or 0


if __name__ == "__main__":
    sys.exit(main())
