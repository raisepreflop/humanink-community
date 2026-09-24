---
name: diagnostico
description: "Diagnóstico del equipo — comprueba qué tiene tu Cowork (o tu ordenador) para que HumanInk funcione: la versión de Python, los módulos que usan los colaboradores (Word, control de cambios, humanizador, portadas), las herramientas de maquetación, las fuentes, si llega a internet y si puede guardar en tu carpeta. No toca tus ficheros ni gasta nada. Úsalo cuando algo no salga, antes de una sesión del curso, o cuando el autor pregunte si su equipo está listo."
allowed-tools: Bash
argument-hint: ""
model: haiku
context: fork
background: false
---

<!-- AI-TRANSPARENCY-50-1 -->
> **Primera respuesta — transparencia de IA (Reglamento europeo de IA, art. 50(1)).** Abre tu primerísima respuesta en este comando con esta línea EXACTA, en español, y continúa normalmente:
>
> ℹ️ Estás colaborando con una IA. Este colaborador de HumanInk (v2.2.1-club) funciona sobre Claude, de Anthropic — te asiste, pero el autor eres tú y tú decides. (Reglamento (UE) 2024/1689, art. 50)

<!-- HI-PRESENCIA -->
> **Presencia — solo si en el contexto de esta sesión aparece la línea `HUMANINK_PRESENCIA: falta_email`.**
> Antes de ponerte a trabajar, pide al autor su email con estas palabras, y sigue después con lo suyo:
> «Para saber quién usa HumanInk en el Club, escribe tu email en un mensaje solo, sin nada más. No abre
> ni cierra nada: es solo para el censo.» Si no aparece esa línea, no menciones nada de esto. Si el
> autor no quiere darlo, trabaja igual. Si alguna vez quiere cambiarlo, basta con escribir
> «presencia nuevo@email» en un mensaje solo.
# Diagnóstico del equipo

Ejecuta este bloque tal cual, en un solo paso:

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-/-}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"   # como el resto: si el plugin no se puede leer, el espejo
echo "=== HumanInk: diagnóstico del equipo ==="
echo "Plugin: ${CLAUDE_PLUGIN_ROOT:-(sin CLAUDE_PLUGIN_ROOT)} · se lee: $( [ -d "${CLAUDE_PLUGIN_ROOT:-/-}/scripts" ] && echo sí || echo 'no, uso la copia de ~/.humanink')"
[ -f "$ROOT/.claude-plugin/plugin.json" ] && python3 -c "import json;print('Versión:', json.load(open('$ROOT/.claude-plugin/plugin.json')).get('version'))" 2>/dev/null
echo "Sistema: $(uname -sm)"
echo "Python: $(python3 --version 2>&1 || echo 'NO HAY python3')"
python3 - <<'PY'
import importlib
mods = [("docx", "Word con control de cambios (--tracked/--base)"), ("lxml", "leer y escribir el control de cambios; comparar versiones"),
        ("textstat", "legibilidad del humanizador (opcional)"), ("PIL", "portadas KDP (cover --wrap)")]
for m, para in mods:
    try:
        importlib.import_module(m); print(f"  ✓ {m:9} {para}")
    except Exception:
        print(f"  ✗ {m:9} {para}")
PY
echo "Herramientas de maquetación:"
for t in pandoc weasyprint chromium chromium-browser google-chrome epubcheck java; do
  command -v "$t" >/dev/null 2>&1 && echo "  ✓ $t" || echo "  ✗ $t"
done
echo "Fuentes: $(fc-list 2>/dev/null | wc -l | tr -d ' ') (fc-list) · macOS: $( [ -d /System/Library/Fonts ] && echo sí || echo no)"
echo "Conversor a Word: $( [ -f "$ROOT/scripts/md2docx.py" ] && echo "✓ $ROOT/scripts/md2docx.py" || echo '✗ no está')"
echo "Motor Word sin dependencias: $( [ -f "$ROOT/scripts/ooxml/crear.py" ] && echo '✓ ooxml/crear.py' || echo '✗ no está')"
echo "Internet: $(curl -s -o /dev/null -m 6 -w '%{http_code}' https://verify.humanink.io/health 2>/dev/null || echo 'sin red')"
d="$(pwd)"; t="$d/.humanink-prueba-$$"; (echo ok > "$t" && rm -f "$t") 2>/dev/null && echo "Guardar en la carpeta actual ($d): ✓" || echo "Guardar en la carpeta actual ($d): ✗"
echo "=== fin ==="
```

Después, resume en castellano y en pocas líneas, sin tecnicismos:

- **Qué funciona** y **qué no** en este equipo, traducido a lo que el autor va a hacer. Por ejemplo:
  «los informes en Word salen», «el corrector no puede marcar cambios en Word», «la maquetación en PDF
  no está disponible aquí».
- Si falta algo, **qué puede hacer**: en su propio ordenador, el comando para instalarlo; en Cowork,
  que se lo diga a Rais o lo comente en la comunidad, con esta salida copiada.
- No inventes nada que no salga en el bloque de arriba.
