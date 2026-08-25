#!/usr/bin/env python3
"""Pruebas del troceado en escenas y de las tres categorías de cambio.

Existe porque sobre los manuscritos reales de LDDLL el resultado fue «0 añadidas, 0 borradas,
15 modificadas»: correcto para un ensayo que crece por dentro, pero incapaz de distinguir una
categoría bien implementada de una que nunca dispara. Estas pruebas fuerzan las tres.

La regla es del autor y no lleva ningún umbral afinado a ojo:
    100 % nuevo      -> añadida
    100 % quitado    -> borrada
    cualquier cosa por debajo del 100 % -> modificada

    python3 scripts/ooxml/test_escenas.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comparar as C  # noqa: E402

FALLOS = []


def check(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(f"  {'✓' if ok else '✗'} {nombre:38s} {obtenido}")
    if not ok:
        FALLOS.append(f"{nombre}: esperado {esperado}, obtenido {obtenido}")


def cambios(a, b):
    """Llama a la función del motor. NO reimplementa la clasificación: la primera versión de
    este fichero copiaba aquí la tabla insert/delete/replace y seguía en verde con el motor
    roto a mano — una prueba que no puede fallar no prueba nada."""
    return [e["tipo"] for e in C.cambios_de_escena(a, b)]


BASE = ["Escena uno alfa.", "Sigue uno.", "***", "Escena dos beta.", "***", "Escena tres gamma."]

print("Troceado")
check("tres escenas, la primera de dos", [len(e) for e in C.escenas_de(BASE)], [2, 1, 1])
check("sin separadores: una escena", [len(e) for e in C.escenas_de(["Uno.", "Dos."])], [2])
check("vacío no revienta", C.escenas_de([]), [])
check("solo separadores", C.escenas_de(["***", "---"]), [])

print("\nCategorías")
check("escena 100 % nueva", cambios(BASE, BASE + ["***", "Escena cuatro."]), ["añadida"])
check("escena quitada al 100 %",
      cambios(BASE, ["Escena uno alfa.", "Sigue uno.", "***", "Escena tres gamma."]), ["borrada"])
check("una palabra distinta",
      cambios(BASE, ["Escena uno alfa.", "Sigue uno.", "***", "Escena dos BETA.", "***",
                     "Escena tres gamma."]), ["modificada"])
check("idénticas: ningún cambio", cambios(BASE, list(BASE)), [])

print("\nOtros separadores")
check("--- separa igual que ***", [len(e) for e in C.escenas_de(["A.", "---", "B."])], [1, 1])
check("### separa igual que ***", [len(e) for e in C.escenas_de(["A.", "###", "B."])], [1, 1])

if FALLOS:
    print("\n".join(["", "FALLOS:"] + [f"  - {f}" for f in FALLOS]))
    sys.exit(1)
print("\nescenas: todo en verde")
