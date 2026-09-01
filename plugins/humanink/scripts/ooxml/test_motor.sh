#!/usr/bin/env bash
# test_motor.sh — pruebas del motor sobre un .docx sintético, sin depender de ningún manuscrito.
#
# VIVE JUNTO AL CÓDIGO QUE PRUEBA, y no en otro repo, por un motivo comprobado: estaba en
# `humanink-reescritura`, que recibe el motor por copia, y esa copia llevaba meses atrasada — la
# mejor prueba del motor corría contra una versión antigua. Aquí eso no puede pasar.
#
# El material real (39 builds de una novela) no viaja en el repo: es obra del autor. Estas pruebas generan su propio documento con tablas, imágenes y
# estilos, y comprueban lo que de verdad puede romperse: que el formato sobreviva, que el diff
# sea a nivel de palabra, que el ancla falle en vez de aplicarse mal, y que rechazar todo
# devuelva EXACTAMENTE el estado anterior.
set -u
SRC="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { printf "  ✓ %s\n" "$1"; pass=$((pass+1)); }
ko()  { printf "  ✗ %s — %s\n" "$1" "${2:-}"; fail=$((fail+1)); }

echo "▶ Motor de reescritura quirúrgica — pruebas"

# python-docx solo hace falta para FABRICAR el documento de prueba; el motor no lo usa ni viaja
# empaquetado. Sin él se recurre al fixture commiteado, para que esto corra en cualquier máquina.
if ! python3 -c "import docx" 2>/dev/null; then
  if [ -f "$SRC/fixtures/base.docx" ]; then
    cp "$SRC/fixtures/base.docx" "$TMP/base.docx"
  else
    echo "  ⚠ sin python-docx y sin fixture: no se puede fabricar el documento de prueba"; exit 1
  fi
fi
[ -f "$TMP/base.docx" ] || python3 - "$TMP" <<'PY'
import sys
from docx import Document
from docx.shared import Pt
d = Document()
d.add_heading("Capítulo Uno", level=1)
for i in range(40):
    p = d.add_paragraph(f"Párrafo {i} del documento de prueba. ")
    r = p.add_run("Un fragmento en cursiva que debe sobrevivir.")
    r.italic = True
    p.add_run(f" Y una cola distinta para el párrafo {i}.")
d.add_heading("Capítulo Dos", level=1)
t = d.add_table(rows=2, cols=2); t.cell(0,0).text = "celda"
d.add_paragraph("Frase final con una palabra concreta: cianotipo.")
d.save(sys.argv[1] + "/base.docx")
PY
[ -f "$TMP/base.docx" ] && ok "documento de prueba generado" || { ko "generar documento"; exit 1; }

cat > "$TMP/lote.json" <<'JSON'
[
 {"op":"reemplazar","parrafo":3,"huella":"Párrafo 2 del documento",
  "buscar":"cola distinta","reemplazar":"terminación diferente",
  "autor":"Prueba · reemplazo","motivo":"test"},
 {"op":"insertar_despues","parrafo":5,"huella":"Párrafo 4 del documento",
  "texto":["Párrafo insertado uno.","Párrafo insertado dos."],"autor":"Prueba · inserción"},
 {"op":"borrar_parrafo","parrafo":8,"huella":"Párrafo 7 del documento","autor":"Prueba · poda"},
 {"op":"reemplazar","parrafo":9999,"huella":"esta huella no existe en ninguna parte",
  "buscar":"x","reemplazar":"y","autor":"Prueba · debe fallar"}
]
JSON

# ── marcado ──
OUTM=$(python3 "$SRC/intervene.py" "$TMP/base.docx" "$TMP/marcado.docx" \
        --lote "$TMP/lote.json" --marcado --json 2>/dev/null)
apl=$(echo "$OUTM" | python3 -c 'import json,sys; print(json.load(sys.stdin)["aplicadas"])' 2>/dev/null || echo 0)
fal=$(echo "$OUTM" | python3 -c 'import json,sys; print(json.load(sys.stdin)["fallidas"])' 2>/dev/null || echo 0)
[ "$apl" = "3" ] && ok "3 intervenciones aplicadas (modo marcado)" || ko "aplicadas" "esperaba 3, salieron $apl"
[ "$fal" = "1" ] && ok "el ancla inexistente FALLA (no se aplica a ciegas)" || ko "ancla falsa" "debía fallar 1, fallaron $fal"

python3 "$SRC/verify_docx.py" "$TMP/marcado.docx" --base "$TMP/base.docx" >/dev/null 2>&1 \
  && ok "REVERSIBILIDAD: rechazar todo == documento base" || ko "reversibilidad" "verify_docx salió != 0"

python3 - "$TMP" "$SRC" <<'PY' && ok "formato preservado (cursivas, tabla, encabezados)" || ko "formato"
import sys, zipfile
sys.path.insert(0, sys.argv[2])
from lxml import etree
import docxtc as D
from docxtc import w
a = D.leer_xml(sys.argv[1] + "/base.docx"); b = D.leer_xml(sys.argv[1] + "/marcado.docx")
def rasgos(r):
    return (len(r.findall(f".//{w('tbl')}")),
            len(r.findall(f".//{w('i')}")),
            len({p.get(w('val')) for p in r.findall(f".//{w('pStyle')}")}))
assert rasgos(a) == rasgos(b), f"{rasgos(a)} != {rasgos(b)}"
PY

python3 - "$TMP" "$SRC" <<'PY' && ok "diff a nivel de palabra (no marca el párrafo entero)" || ko "granularidad"
import sys
sys.path.insert(0, sys.argv[2])
import docxtc as D
revs = [r for r in D.revisiones(sys.argv[1] + "/marcado.docx") if r[1] == "Prueba · reemplazo"]
textos = [r[4] for r in revs if r[4]]
assert textos, "sin marcas del reemplazo"
assert all(len(t.split()) <= 4 for t in textos), f"marcó de más: {textos}"
PY

python3 - "$TMP" "$SRC" <<'PY' && ok "autores de revisión separados (aceptar por bloques)" || ko "autores"
import sys
sys.path.insert(0, sys.argv[2])
import docxtc as D
a = D.autores(sys.argv[1] + "/marcado.docx")
assert len(a) == 3, f"esperaba 3 autores, hay {len(a)}: {a}"
PY

# ── firme ──
python3 - "$TMP" <<'PY'
import json
l = json.load(open(sys.argv[1] + "/lote.json")) if False else json.load(open(__import__("sys").argv[1] + "/lote.json"))
json.dump(l[:3], open(__import__("sys").argv[1] + "/lote-firme.json", "w"), ensure_ascii=False)
PY
python3 "$SRC/intervene.py" "$TMP/base.docx" "$TMP/firme.docx" \
  --lote "$TMP/lote-firme.json" >/dev/null 2>&1
python3 - "$TMP" "$SRC" <<'PY' && ok "modo firme: sin marcas, texto ya aplicado" || ko "modo firme"
import sys
sys.path.insert(0, sys.argv[2])
import docxtc as D
inv = D.inventario(sys.argv[1] + "/firme.docx")
assert inv["marcas"] == 0, f"debería no tener marcas, tiene {inv['marcas']}"
t = D.texto(sys.argv[1] + "/firme.docx", D.ACEPTAR)
assert "terminación diferente" in t and "Párrafo insertado uno." in t
PY

# ── escáner y comparador ──
python3 "$SRC/fase0_scan.py" "$TMP/base.docx" >/dev/null 2>&1 \
  && ok "fase0_scan corre sobre un documento limpio" || ko "fase0_scan"
python3 "$SRC/comparar.py" "$TMP/firme.docx" "$TMP/base.docx" >/dev/null 2>&1 \
  && ok "comparar mide dos builds" || ko "comparar"

# ── El puente nuevo: de dos textos a un lote, y del lote al documento ─────────────────────────

echo
echo "▶ De «original + propuesta» a control de cambios"

python3 "$SRC/cli.py" listar "$TMP/base.docx" --json > "$TMP/parrafos.json" 2>/dev/null \
  && ok "listar --json" || ko "listar --json"

python3 - "$TMP" <<'HUELLAS' && ok "todas las huellas son únicas en el documento" || ko "huellas"
import json, re, sys
d = json.load(open(sys.argv[1] + "/parrafos.json"))
norm = lambda s: re.sub(r"\s+", " ", s).strip()
textos = [norm(p["texto"]) for p in d["parrafos"]]
for p in d["parrafos"]:
    if not p["huella"]:
        continue
    veces = sum(1 for t in textos if norm(p["huella"]) in t)
    assert veces == 1, f"la huella del parrafo {p['i']} aparece en {veces} parrafos"
assert d["sha256"] and len(d["sha256"]) == 64
HUELLAS

# El caso que prueba la funcion entera: si esto pasa, el producto hace lo que promete.
python3 "$SRC/docxtc.py" "$TMP/base.docx" aceptar > "$TMP/original.txt"
python3 - "$TMP" <<'PROP'
import sys
lineas = open(sys.argv[1] + "/original.txt").read().splitlines()
salida = []
for l in lineas:
    if "\u00e1rrafo 5 del documento" in l:
        l = l.replace("cola distinta", "terminacion diferente")
    if "\u00e1rrafo 9 del documento" in l:
        continue                                    # este se borra entero
    salida.append(l)
salida.insert(3, "Un parrafo enteramente nuevo, que antes no existia.")
open(sys.argv[1] + "/propuesta.txt", "w").write("\n".join(salida) + "\n")
PROP

python3 "$SRC/cli.py" lote "$TMP/base.docx" --original "$TMP/original.txt" \
  --propuesta "$TMP/propuesta.txt" --autor "Prueba" --json > "$TMP/lote-full.json" 2>/dev/null \
  && ok "lote construido desde dos textos" || ko "lote"

python3 -c "
import json,sys
d=json.load(open('$TMP/lote-full.json'))
json.dump(d['lote'], open('$TMP/lote2.json','w'), ensure_ascii=False)
sys.exit(0 if not d['sin_ancla'] else 1)" \
  && ok "todo el cambio encuentra su ancla" || ko "quedan cambios sin ancla"

python3 "$SRC/cli.py" aplicar "$TMP/base.docx" "$TMP/b02.docx" --lote "$TMP/lote2.json" \
  --marcado --autor "Prueba" --json >/dev/null 2>&1 \
  && ok "el lote se aplica entero" || ko "aplicar el lote"

# ── LA PRUEBA. Todo lo demas importa solo si esta pasa. ───────────────────────────────────────
python3 - "$TMP" "$SRC" <<'IGUAL' && ok "ACEPTAR TODO EN WORD == la propuesta, palabra por palabra" || ko "aceptar != propuesta"
import subprocess, sys
tmp, src = sys.argv[1], sys.argv[2]
aceptado = subprocess.run(["python3", src + "/docxtc.py", tmp + "/b02.docx", "aceptar"],
                          capture_output=True, text=True).stdout.strip()
propuesta = open(tmp + "/propuesta.txt").read().strip()
if aceptado != propuesta:
    import difflib
    for l in difflib.unified_diff(propuesta.splitlines(), aceptado.splitlines(),
                                  "propuesta", "aceptado", lineterm="", n=0):
        print("     " + l)
    raise SystemExit(1)
IGUAL

python3 "$SRC/cli.py" verificar "$TMP/b02.docx" --base "$TMP/base.docx" >/dev/null 2>&1 \
  && ok "y el build pasa la verificacion completa" || ko "verificacion"

python3 "$SRC/cli.py" version >/dev/null 2>&1 && ok "cli.py version" || ko "cli.py version"

echo
echo "  $pass pasadas · $fail fallidas"
[ "$fail" -eq 0 ] || exit 1
