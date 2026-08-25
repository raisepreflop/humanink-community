#!/usr/bin/env python3
"""La puerta de licencia.

Lo que se protege aquí es un equilibrio, no una función: **cerrar cuando la licencia ha caducado de
verdad y abrir siempre que la duda sea nuestra**. Un autor sin red, con el servidor caído o con el
fichero de estado corrupto tiene que poder seguir escribiendo su libro. Cerrarle la herramienta por
un fallo de nuestra infraestructura es peor que cualquier uso indebido que pudiéramos evitar.

    python3 scripts/test_licencia.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(AQUI, "..", "hooks")
FALLOS = []


def check(nombre, ok, extra=""):
    print(f"  {'✓' if ok else '✗'} {nombre}{'  ' + str(extra) if extra else ''}")
    if not ok:
        FALLOS.append(nombre)


def correr(home, verify="http://127.0.0.1:9/nada", gate_conf=None):
    """Ejecuta el hook con un HOME de mentira y un servidor inalcanzable salvo que se diga otra cosa."""
    hooks = os.path.join(home, "hooks")
    os.makedirs(hooks, exist_ok=True)
    for f in ("license-lib.sh", "license-gate.sh"):
        with open(os.path.join(HOOKS, f), encoding="utf-8") as a, \
             open(os.path.join(hooks, f), "w", encoding="utf-8") as b:
            b.write(a.read())
    if gate_conf:
        with open(os.path.join(hooks, "gate.conf"), "w", encoding="utf-8") as f:
            f.write(gate_conf)
    r = subprocess.run(["bash", os.path.join(hooks, "license-gate.sh")],
                       capture_output=True, text=True,
                       env=dict(os.environ, HOME=home, HUMANINK_VERIFY_URL=verify))
    return r.stdout, r.returncode


def licencia(home, **campos):
    d = {"key": "K-1", "email": "a@b.c", "tier": "humanink",
         "expires_at": None, "checked_at": int(time.time()),
         "last_valid": True, "last_error": None}
    d.update(campos)
    os.makedirs(os.path.join(home, ".humanink"), exist_ok=True)
    with open(os.path.join(home, ".humanink", "license.json"), "w", encoding="utf-8") as f:
        json.dump(d, f)


print("La puerta cierra cuando debe\n")

with tempfile.TemporaryDirectory() as h:
    out, code = correr(h)
    check("sin licencia: pide activar", "HUMANINK_LICENSE: missing" in out and "activate" in out)
    check("y explica dónde está la clave", "email de tu compra" in out)

with tempfile.TemporaryDirectory() as h:
    # Validada hace ocho días y sin red: fuera de la gracia de siete.
    licencia(h, checked_at=int(time.time()) - 8 * 86400)
    out, _ = correr(h)
    check("más de 7 días sin poder verificar: cierra", "offline_expirado" in out)

with tempfile.TemporaryDirectory() as h:
    licencia(h, tier="reescritura")
    out, _ = correr(h, gate_conf='TIERS_OK="humanink certificate-pro community"\n')
    check("una clave de otro producto no abre este", "tier_no_valido" in out)
    check("y lo dice sin culpar al autor", "otro producto" in out)

print("\nLa puerta abre cuando la duda es nuestra\n")

with tempfile.TemporaryDirectory() as h:
    licencia(h)                       # validada hace un momento
    out, _ = correr(h)
    check("validada hace poco: no molesta al servidor", "HUMANINK_LICENSE: valid" in out)
    check("y no enseña ningún aviso", "HUMANINK_GATE" not in out)

with tempfile.TemporaryDirectory() as h:
    # Validada hace dos días, sin red: dentro de la gracia. El autor sigue trabajando.
    licencia(h, checked_at=int(time.time()) - 2 * 86400)
    out, _ = correr(h)
    check("sin red y dentro de la gracia: sigue abierta", "valid" in out and "sin conexión" in out)
    check("no cierra por falta de red", "HUMANINK_GATE" not in out)

with tempfile.TemporaryDirectory() as h:
    # Fichero de estado corrupto: es un fallo nuestro, no del autor.
    os.makedirs(os.path.join(h, ".humanink"))
    with open(os.path.join(h, ".humanink", "license.json"), "w") as f:
        f.write("{roto")
    out, code = correr(h)
    check("estado corrupto: no revienta", code == 0)
    check("y no deja al autor fuera de su libro", "HUMANINK_GATE" not in out or "missing" in out)

print("\nNunca aborta la sesión\n")

for nombre, hacer in [
    ("sin licencia", lambda h: None),
    ("caducada", lambda h: licencia(h, last_valid=False, last_error="expired")),
    ("estado ilegible", lambda h: licencia(h, checked_at="no-es-un-numero")),
]:
    with tempfile.TemporaryDirectory() as h:
        hacer(h)
        _, code = correr(h)
        check(f"{nombre}: sale con 0", code == 0, f"exit={code}")

with tempfile.TemporaryDirectory() as h:
    # Sin las librerías al lado, el hook no puede hacer nada — y aun así no debe romper.
    os.makedirs(os.path.join(h, "hooks"))
    with open(os.path.join(HOOKS, "license-gate.sh"), encoding="utf-8") as a, \
         open(os.path.join(h, "hooks", "license-gate.sh"), "w", encoding="utf-8") as b:
        b.write(a.read())
    r = subprocess.run(["bash", os.path.join(h, "hooks", "license-gate.sh")],
                       capture_output=True, text=True, env=dict(os.environ, HOME=h))
    check("sin la librería al lado: sale con 0 y calla", r.returncode == 0 and not r.stdout.strip())

if FALLOS:
    print("\n".join(["", "FALLOS:"] + [f"  - {f}" for f in FALLOS]))
    sys.exit(1)
print("\nlicencia: todo en verde")
