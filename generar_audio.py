"""Paso 2: voz en off por paso (edge-tts) + duraciones exactas (ffprobe) -> datos_video.json."""
import asyncio
import json
import subprocess
import time
from pathlib import Path

import edge_tts

VOZ = "es-AR-TomasNeural"
VELOCIDAD = "+12%"
PAUSA_INTRO = 0.45   # aire después del gancho
PAUSA_PASO = 0.35    # aire después de cada paso
DURACION_OUTRO = 3.5 # placa final sin voz

TEMP = Path("temp")


def duracion(ruta: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(ruta)],
        capture_output=True, text=True, check=True).stdout
    return float(out.strip())


async def _tts(texto: str, destino: Path):
    await edge_tts.Communicate(texto, VOZ, rate=VELOCIDAD).save(str(destino))


def generar(texto: str, destino: Path):
    for intento in range(1, 4):
        try:
            asyncio.run(_tts(texto, destino))
            return
        except Exception as ex:
            print(f"  edge-tts falló (intento {intento}): {ex}")
            if intento == 3:
                raise
            time.sleep(3 * intento)


def main():
    datos = json.loads(Path("datos_video.json").read_text(encoding="utf-8"))
    TEMP.mkdir(exist_ok=True)

    # audio_0 = gancho (título), audio_1..n = pasos
    bloques = [("intro", datos["titulo"], PAUSA_INTRO)] + [
        (i, p["texto_voz"], PAUSA_PASO) for i, p in enumerate(datos["pasos"])]

    t = 0.0
    for n, (ref, texto, pausa) in enumerate(bloques):
        ruta = TEMP / f"audio_{n}.mp3"
        generar(texto, ruta)
        dur = duracion(ruta)
        info = {"audio": str(ruta), "duracion_audio": round(dur, 3),
                "inicio": round(t, 3), "fin": round(t + dur + pausa, 3)}
        if ref == "intro":
            datos["intro"] = info
        else:
            datos["pasos"][ref].update(info)
        t = info["fin"]
        print(f"  audio_{n}: {dur:.2f}s (de {info['inicio']}s a {info['fin']}s)")

    datos["outro"] = {"inicio": round(t, 3), "fin": round(t + DURACION_OUTRO, 3)}
    datos["duracion_total"] = datos["outro"]["fin"]
    Path("datos_video.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Duración total del reel: {datos['duracion_total']:.1f}s")


if __name__ == "__main__":
    main()
