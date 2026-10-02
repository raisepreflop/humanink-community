"""_utf8.py — la salida del motor, SIEMPRE en UTF-8, diga lo que diga el sistema.

En Windows, cuando la salida de Python va a otro programa (el motor del Studio, la consola de Claude
Code), se escribe en la página de códigos del sistema (cp1252), no en UTF-8. Quien la lee espera
UTF-8: cada tilde, cada «ñ» y cada comilla llegaban rotas, y en cuanto había que imprimir un carácter
que cp1252 no tiene («→», «✓», «ő», un emoji) el motor moría con un UnicodeEncodeError y el autor
veía «El motor de documentos falló (1)» (2-oct-2026, primer libro corregido en un Windows de verdad).

Está aquí, y no en `cli.py`, porque `cli.py` es solo UNA de las puertas: el Studio entra por ella, pero
las skills del plugin llaman a cada módulo por su ruta (`python3 scripts/ooxml/intervene.py …`). Cada
punto de entrada llama a esta función al empezar su `main()`; `test_salida_utf8.py` los recorre todos
y falla si a alguno le falta. El intérprete embebido de Windows ignora PYTHONIOENCODING, así que se
arregla dentro (y el Studio lo arranca además con «-X utf8»).
"""
import sys


def salida_en_utf8():
    """La salida y los errores (y la entrada, si alguien la lee) en UTF-8. Llamarla dos veces no hace
    nada, y nunca lanza: si la salida no es un fichero de texto de verdad (una prueba que la captura),
    se queda como está."""
    for flujo in (sys.stdin, sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass
