---
name: kdp-audit
description: "Auditor de fichas de Amazon KDP — auditoría completa de la página de un libro en Amazon a partir de su ASIN. Analiza título, subtítulo y palabras clave, BSR y categorías con la posición exacta en cada una, calidad de portada y visibilidad en miniatura, ISBN propio o de KDP, reseñas y valoración media, formatos y traducciones disponibles, cumplimiento de la política de metadatos de KDP, precio por formato, inscripción en KDP Select y antigüedad de la publicación, y lo compara con tres o más competidores mejor posicionados en las mismas categorías. Entrega una nota por aspecto y una global sobre 100, un plan de mejoras priorizado en Word y un audit.json legible por máquina para seguir la evolución. Úsalo cuando el autor pida auditar o revisar una ficha de Amazon, dé un ASIN, o mencione BSR, posición por categorías, KDP Select, portada, reseñas o comparación con la competencia."
allowed-tools: Bash, Read, Write, ToolSearch
argument-hint: "<ASIN o URL de Amazon> [--marketplace amazon.es|amazon.com|…]"
disable-model-invocation: true
model: sonnet
effort: medium
---

<!-- AI-TRANSPARENCY-50-1 -->
> **Primera respuesta — transparencia de IA (Reglamento europeo de IA, art. 50(1)).** Abre tu primerísima respuesta en este comando con esta línea EXACTA, en español, y continúa normalmente:
>
> ℹ️ Estás colaborando con una IA. Este colaborador de HumanInk (v1.9.8-club) funciona sobre Claude, de Anthropic — te asiste, pero el autor eres tú y tú decides. (Reglamento (UE) 2024/1689, art. 50)

<!-- HI-GATE -->
> **Licencia.** Antes de nada, busca en tu contexto la línea `HUMANINK_LICENSE:` que deja el arranque
> de sesión. Si dice `valid`, sigue con normalidad y **no menciones nada de esto**.
>
> Si dice otra cosa —`missing`, `expired`, `tier_no_valido`…—, **no ejecutes el trabajo**: responde
> únicamente con el texto de la línea `HUMANINK_GATE:` y para ahí. No resumas ni improvises una
> versión propia del mensaje: está redactado para que el autor sepa qué hacer.
>
> Si la línea `HUMANINK_LICENSE:` **no aparece**, comprueba en disco y sigue si no puedes:
>
> ```bash
> cat "$HOME/.humanink/license-state" 2>/dev/null || echo desconocido
> ```
>
> `valid` o `desconocido` → adelante. Ante la duda se trabaja: un fallo nuestro no puede dejar a un
> autor sin su herramienta de escribir.

# Auditoría de ficha de libro en Amazon KDP

## Cuándo usar este skill

Cuando el autor pida analizar, auditar o mejorar la ficha de un libro publicado en Amazon (propio o
de la competencia), dé un ASIN o una URL de Amazon, pregunte por su BSR, categorías, reseñas,
keywords, portada, o quiera saber cómo mejorar el posicionamiento frente a la competencia.

## Por qué existe

Una ficha bien optimizada es la principal palanca de ventas orgánicas en KDP: título/subtítulo con
las keywords correctas, categorías bien elegidas, portada legible en miniatura y cumplimiento de las
políticas de metadatos afectan directamente al BSR y a la conversión. Este skill sistematiza una
auditoría completa con un scoring reproducible, para decidir con datos y no con intuición.

## Flujo de trabajo

### 1. Datos de entrada

Mínimo: el **ASIN** (o una URL de la que extraerlo) y el **marketplace** (pregunta cuál si no está
claro; no asumas — el catálogo del autor puede vivir en .es, .com, .com.mx…). Si solo hay un título,
búscalo primero en Amazon para confirmar el ASIN correcto antes de continuar.

### 2. Obtener los datos de la ficha (navegación con Claude in Chrome)

El paso más importante. Amazon no tiene API pública para esto: la fuente es la propia página.

1. Carga las herramientas de Chrome si están diferidas: `ToolSearch` con
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__tabs_create_mcp`.
2. Navega a `https://www.<marketplace>/dp/<ASIN>` y extrae el contenido real con
   `get_page_text` / `read_page`. **Nunca infieras datos de memoria** — los datos de Amazon cambian
   constantemente y una auditoría con datos inventados no vale nada.
3. Si la extensión de Chrome no está conectada o la página no carga, dilo claramente y pide al autor
   que pegue el texto de la ficha o adjunte capturas (título, "Detalles del producto", rating y
   reseñas, desplegable de formatos). Nunca rellenes huecos con datos no verificados.
4. La miniatura real de la portada se evalúa en la **página de resultados de búsqueda** (no en la
   imagen grande de la ficha): busca el libro por título y mira cómo se ve en pequeño.
5. Para los competidores (paso 5), navega a una de las categorías del libro y anota los 3 mejor
   posicionados que no sean el propio.

Extrae y anota, punto por punto: título y subtítulo completos · autor/sello · categorías con el
puesto exacto en cada una ("Nº X en [Categoría]") · BSR general · nº de reseñas y valoración media ·
formatos con su precio (Kindle, tapa blanda, tapa dura, audiolibro) · idiomas/traducciones ·
ISBN-13/ISBN-10 y nombre del sello · fecha de publicación · si aparece Kindle Unlimited (señal de
KDP Select) · descripción completa.

### 3. Analizar cada aspecto

Abre `references/scoring-rubric.md` en cada auditoría (define pesos y criterios exactos — no los
repitas de memoria) y `references/kdp-policies.md` como checklist de cumplimiento. Matices:

- **Título/subtítulo**: ¿keyword principal presente? ¿legible, no un amontonamiento? ¿el subtítulo
  aporta contexto de búsqueda real?
- **Keywords backend**: no son públicas — decláralo como limitación metodológica. **OPCIONAL — solo
  si el autor tiene Publisher Rocket instalado** (pregúntaselo o compruébalo con las herramientas de
  computer-use si están disponibles): un Reverse ASIN Lookup del ASIN auditado muestra con qué
  términos ha vendido de verdad; si Amazon devuelve solo título+autor es señal objetiva de poca
  tracción orgánica — inclúyelo como hallazgo. Keyword Search con 1-2 términos semilla da candidatos
  para el plan de mejoras. Si pide activar licencia, que la introduzca el autor — nunca teclees
  credenciales por él. **Si no tiene Publisher Rocket, no pasa nada**: anota la limitación y sugiere
  revisar las keywords reales en su panel de KDP. La auditoría es completa igualmente.
- **BSR/categorías**: específica y poco saturada = más fácil rankear, pero demasiado nicho no refleja
  volumen real. Una categoría irrelevante elegida solo para rankear #1 se penaliza.
- **Portada**: legibilidad del título EN MINIATURA, género reconocible, diferenciación en el estante.
- **ISBN**: prefijo genérico + sello "Independently published" ≈ ISBN gratuito de KDP. Márcalo como
  interpretación razonada, no como hecho — solo el panel de KDP del autor lo confirma al 100%.
- **Antigüedad**: no puntúa aislada, da contexto (libro joven con buen BSR ≠ veterano estancado).
- **KDP Select**: si está inscrito, ¿tiene sentido para ese género (páginas leídas KU vs ancho de
  distribución)?

### 4. Comparar con 3+ competidores

De la(s) misma(s) categoría(s), los 3 con mejor BSR: título, puesto, reseñas, valoración, precio,
formatos, y qué hacen mejor. Es la base de varias recomendaciones del plan.

### 5. Calcular el scoring

Con la tabla de `references/scoring-rubric.md`, puntúa cada aspecto sobre su máximo y suma /100.
Si penalizas, cita exactamente qué criterio de la rúbrica no se cumple.

### 6. Generar los entregables (Word + JSON)

Escribe primero el informe en Markdown y conviértelo con el conversor del plugin:

```bash
python3 ~/.awos/md2docx.py "<informe>.md" "<informe>.docx" "Auditoría KDP — <título>"
```

Estructura del informe (siempre esta plantilla, en el idioma del autor):

```
# Auditoría de libro en Amazon KDP — [Título]
ASIN: … | Marketplace: … | Fecha: …
## 1. Resumen ejecutivo (scoring X/100 + calificación · 3 fortalezas · 3 urgencias)
## 2. Ficha del producto (datos extraídos)
## 3. Análisis por aspecto (puntuación + razonamiento)
## 4. Comparativa con la competencia
## 5. Tabla de scoring (aspecto | peso | puntos | motivo)
## 6. Plan de mejoras priorizado (acción · impacto · prioridad)
## 7. Cómo subir el scoring (orden esfuerzo/beneficio)
```

**Además del Word, escribe SIEMPRE `audit.json`** en la misma carpeta — es lo que permite comparar
la evolución del libro y pintar su histórico en un dashboard:

```json
{
  "asin": "B0XXXXXXXX", "titulo": "…", "marketplace": "amazon.es",
  "fecha": "YYYY-MM-DD", "global": 68, "calificacion": "Mejorable",
  "aspectos": {"titulo_subtitulo": 11, "categorias_bsr": 9, "portada": 7, "isbn": 4,
               "resenas": 8, "formatos": 6, "politicas_kdp": 9, "pricing": 7,
               "kdp_select": 3, "competencia": 4},
  "plan": ["acción 1 (alta)", "acción 2 (media)", "…"]
}
```

### 7. Guardar histórico

En la carpeta del proyecto del autor:
`AMAZON-KDP/Auditorias-Amazon/<ASIN>-<slug-del-titulo>/` → `<YYYY-MM-DD>-informe.docx`,
`<YYYY-MM-DD>-audit.json`, y `historico.md` (una línea por auditoría: fecha, scoring global,
2-3 cambios relevantes desde la anterior). Primera auditoría de un ASIN = crear el fichero con
cabecera y primera fila. Varios libros = un flujo completo e informes independientes por ASIN.

## Reglas

- Nunca inventes BSR, reseñas, precios ni nada no verificado en la ficha — si no se puede
  comprobar, dilo explícitamente en el informe.
- Cada informe lleva la fecha de captura: los datos de Amazon caducan rápido.
- Publisher Rocket es un **extra opcional**, jamás un requisito: sin él la auditoría sigue completa.
