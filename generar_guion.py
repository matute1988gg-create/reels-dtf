"""Paso 1: tema -> datos_video.json (Gemini con Structured Outputs)."""
import json
import os
import re
import sys
import time

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Se prueban en orden; si Google retira uno, pasa al siguiente.
MODELOS = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.8-flash", "gemini-flash-latest"] if m]
TIPOS = {"ancho", "largo", "estampa", "resumen"}


class Paso(BaseModel):
    texto_voz: str = Field(description="Lo que dice la voz en este paso, 15 a 32 palabras, español rioplatense claro.")
    subtitulo_destacado: str = Field(description="Frase corta de 3 a 7 palabras para mostrar arriba, con la palabra clave entre asteriscos. Ej: Talle M: *50* cm de ancho")
    etiqueta_badge: str = Field(description="Etiqueta corta del badge: S, M, L, XL, o número de paso (1, 2, 3...). Máximo 4 caracteres.")
    medida_principal: str = Field(description="Dato principal del paso, corto. Ej: 46 x 71 cm, 160 °C, 300 DPI")
    tipo_animacion: str = Field(description="Uno de: ancho, largo, estampa, resumen")


class Guion(BaseModel):
    titulo: str = Field(description="Gancho inicial en forma de pregunta o promesa, máximo 10 palabras.")
    pasos: list[Paso]
    resumen_final: list[str] = Field(description="Exactamente 4 líneas clave, máximo 8 palabras cada una.")


PROMPT = """Sos el guionista de los Reels educativos de DTF-ARG (www.dtf-arg.com), un taller de estampado DTF textil de Argentina.

TEMA: {tema}

Armá el guion de un Reel vertical de unos 45 a 70 segundos.

Reglas:
- Español rioplatense claro y directo. Decí "remera" (nunca "playera").
- Entre 4 y 7 pasos. El ÚLTIMO paso es siempre un cierre de resumen con tipo_animacion "resumen".
- tipo_animacion: "ancho" si el paso habla del ancho de algo, "largo" si habla del largo, "estampa" para el resto
  (temperatura, presión, archivos, tiempos, DPI, etc.) y "resumen" solo en el último paso.
- medida_principal: si es una medida de prenda o estampa, usá el formato "ANCHO x LARGO cm" (ej: 46 x 71 cm).
- subtitulo_destacado: la palabra clave entre asteriscos, como en la descripción del campo.
- No inventes datos técnicos. Usá valores habituales y razonables del rubro; si no estás seguro, hablá de valores
  aproximados y decí "aproximadamente" en la voz.
- La voz no debe leer símbolos raros: escribí "grados", "centímetros", "por" en vez de °C, cm, x.
- resumen_final: exactamente 4 líneas cortas con lo más importante para guardar.
"""


def _rioplatense(txt: str) -> str:
    txt = re.sub(r"\bplayeras\b", "remeras", txt, flags=re.I)
    return re.sub(r"\bplayera\b", "remera", txt, flags=re.I)


def _marcar(sub: str) -> str:
    """Garantiza que haya una palabra entre *asteriscos* (la que va en amarillo)."""
    if re.search(r"\*[^*]+\*", sub):
        return sub
    palabras = sub.split()
    if not palabras:
        return sub
    con_numero = [k for k, w in enumerate(palabras) if any(c.isdigit() for c in w)]
    i = con_numero[0] if con_numero else max(range(len(palabras)), key=lambda k: len(palabras[k]))
    palabras[i] = f"*{palabras[i]}*"
    return " ".join(palabras)


def normalizar(d: dict) -> dict:
    d["titulo"] = _rioplatense(d["titulo"].strip())
    for p in d["pasos"]:
        p["texto_voz"] = _rioplatense(p["texto_voz"].strip())
        p["subtitulo_destacado"] = _marcar(_rioplatense(p["subtitulo_destacado"].strip()))
        p["etiqueta_badge"] = p["etiqueta_badge"].strip()[:6]
        p["medida_principal"] = p["medida_principal"].strip()
        if p["tipo_animacion"] not in TIPOS:
            p["tipo_animacion"] = "estampa"
    d["pasos"][-1]["tipo_animacion"] = "resumen"
    for p in d["pasos"][:-1]:
        if p["tipo_animacion"] == "resumen":
            p["tipo_animacion"] = "estampa"
    resumen = [_rioplatense(x.strip()) for x in d["resumen_final"] if x.strip()][:4]
    for p in d["pasos"]:
        if len(resumen) >= 4:
            break
        resumen.append(p["subtitulo_destacado"].replace("*", ""))
    d["resumen_final"] = resumen[:4]
    return d


def main():
    tema = os.environ.get("TEMA") or " ".join(sys.argv[1:])
    if not tema.strip():
        sys.exit("Falta el tema. Uso: python generar_guion.py \"Medidas de estampado según talle\"")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    ultimo_error = None
    modelo_idx = 0
    for intento in range(1, 5):
        modelo = MODELOS[modelo_idx]
        try:
            print(f"Usando modelo {modelo}")
            resp = client.models.generate_content(
                model=modelo,
                contents=PROMPT.format(tema=tema),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Guion,
                    temperature=0.6,
                ),
            )
            datos = normalizar(json.loads(resp.text))
            if not 3 <= len(datos["pasos"]) <= 8:
                raise ValueError(f"cantidad de pasos rara: {len(datos['pasos'])}")
            break
        except Exception as ex:
            ultimo_error = ex
            print(f"Intento {intento} falló: {ex}")
            if ("404" in str(ex) or "NOT_FOUND" in str(ex)) and modelo_idx + 1 < len(MODELOS):
                modelo_idx += 1  # modelo retirado: probar el siguiente sin esperar
                continue
            time.sleep(8 * intento)
    else:
        sys.exit(f"Gemini no devolvió un guion válido: {ultimo_error}")

    with open("datos_video.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"Guion listo: '{datos['titulo']}' con {len(datos['pasos'])} pasos -> datos_video.json")


if __name__ == "__main__":
    main()
