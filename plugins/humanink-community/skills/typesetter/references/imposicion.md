# Imposición de interior — páginas pares e impares

Criterios de la tradición editorial española, coincidentes con Chicago. Un interior bien
impuesto es lo que distingue un libro de un documento impreso, y es de lo primero que mira
un librero o un editor.

## Las cinco reglas

1. **Todo arranque abre en impar (recto).** Prólogo, partes, capítulos, apéndices y
   cualquier sección final. Nunca en par.
2. **Orden de preliminares:**

   | Pág. | Qué va |
   |---|---|
   | 1 | Portadilla — solo el título, en cuerpo pequeño |
   | 2 | Créditos y copyright (verso de la portadilla) |
   | 3 | Portada — título grande, subtítulo y autor, en impar |
   | 4 | Blanca de cortesía |
   | 5 | Arranque del texto (prólogo o capítulo 1), en impar |

3. **Las blancas de cortesía van totalmente blancas:** sin folio y sin cornisa.
4. **Las páginas de arranque no llevan cornisa**, pero sí folio al pie.
5. **Los preliminares no llevan folio visible.**

## Cómo está implementado

En `scripts/md2book-html.py`, dentro de la constante `CSS`.

```css
/* Arranques siempre en impar. Se declara DOS veces a propósito:
   `recto` sólo es válido en break-before (nivel 3); en la propiedad antigua
   page-break-before puede ignorarse. La antigua la soportan todos los motores. */
h1, .page-title, .page-dedication {
  page-break-before: right;   /* legacy: universal */
  break-before: recto;        /* moderno: mismo efecto */
}

/* Blancas totalmente limpias: sin folio (bottom-*) y sin cornisa (top-*) */
@page :blank {
  @top-left   { content: none } @top-center   { content: none } @top-right   { content: none }
  @bottom-left{ content: none } @bottom-center{ content: none } @bottom-right{ content: none }
}

/* Página de arranque: sin cornisa, con folio */
@page chapter-start { @top-left { content: none } @top-right { content: none } }
```

**Los preliminares son tres `<section>` seguidas** —portadilla → créditos → portada—, cada
una con `page-break-after: always`. **La blanca de la página 4 no se inserta**: la genera
sola el salto a impar del primer arranque. Meter blancas a mano es el error clásico: en
cuanto cambia algo antes, aparecen dobles.

## Verificación antes de entregar el PDF

```python
import re, subprocess
texto = subprocess.run(["pdftotext", PDF, "-"], capture_output=True, text=True).stdout
pags = texto.split("\f")

# 1) Los preliminares están en su sitio y la 4 va en blanco
assert not pags[3].strip(), "la página 4 debería ser una blanca de cortesía"

# 2) Ningún arranque cae en par
mal = [i for i, p in enumerate(pags, 1)
       if re.match(r"^(CAPÍTULO|.*PARTE|APÉNDICE|PRÓLOGO)", " ".join(p.split()))
       and i % 2 == 0]
assert not mal, f"aperturas en página par: {mal}"
```

## Consecuencia obligatoria: el lomo se recalcula DESPUÉS

Las blancas añaden páginas — en un libro de unos 16 capítulos, entre 10 y 20. El recuento
final cambia, y con él el grosor del lomo:

```
lomo_mm = páginas × 0.0635   (papel crema)
lomo_mm = páginas × 0.0572   (papel blanco)
```

**Nunca calcules el lomo antes de imponer.** Y cada vez que cambie el recuento hay que
regenerar la cubierta: pasarle a `/humanink:cover --wrap --pages N` el número de páginas
del PDF ya impuesto, no el del manuscrito. Un lomo mal calculado es rechazo directo en KDP.
