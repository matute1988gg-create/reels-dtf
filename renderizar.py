"""Paso 4: captura la plantilla con Playwright frame a frame y la manda por pipe a FFmpeg."""
import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

W, H, FPS = 1080, 1920, 30
HTML = Path("plantilla_reel.html")
SALIDA = Path("output/reel_dtf.mp4")


def comando_ffmpeg(datos: dict, salida: Path) -> list[str]:
    """Video entra por stdin (JPEGs). El audio se arma con un tramo por paso, cada uno
    rellenado con silencio hasta su duración exacta, así queda todo sincronizado."""
    segmentos = [datos["intro"]] + datos["pasos"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-"]
    filtros, etiquetas = [], []
    for i, s in enumerate(segmentos):
        cmd += ["-i", s["audio"]]
        slot = s["fin"] - s["inicio"]
        filtros.append(
            f"[{i + 1}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"apad=whole_dur={slot:.3f},atrim=duration={slot:.3f}[a{i}]")
        etiquetas.append(f"[a{i}]")
    dur_outro = datos["outro"]["fin"] - datos["outro"]["inicio"]
    filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={dur_outro:.3f}[aout_final]")
    etiquetas.append("[aout_final]")
    filtros.append("".join(etiquetas) + f"concat=n={len(etiquetas)}:v=0:a=1[aout]")

    cmd += ["-filter_complex", ";".join(filtros),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
            "-t", f"{datos['duracion_total']:.3f}", "-movflags", "+faststart", str(salida)]
    return cmd


def main():
    datos = json.loads(Path("datos_video.json").read_text(encoding="utf-8"))
    SALIDA.parent.mkdir(exist_ok=True)
    total = round(datos["duracion_total"] * FPS)
    print(f"Renderizando {total} frames ({datos['duracion_total']:.1f}s a {FPS} fps)...")

    ffmpeg = subprocess.Popen(comando_ffmpeg(datos, SALIDA), stdin=subprocess.PIPE)

    with sync_playwright() as p:
        args = ["--font-render-hinting=none", "--disable-gpu"]
        try:
            navegador = p.chromium.launch(args=args)
        except Exception:
            print("Chromium de Playwright no está instalado, uso Microsoft Edge.")
            navegador = p.chromium.launch(channel="msedge", args=args)
        pagina = navegador.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pagina.goto(HTML.resolve().as_uri())
        pagina.evaluate("d => window.setData(d)", datos)
        pagina.evaluate("document.fonts.ready.then(() => true)")

        try:
            for k in range(total):
                pagina.evaluate("t => window.renderAtTime(t)", k / FPS)
                ffmpeg.stdin.write(pagina.screenshot(type="jpeg", quality=95))
                if k % 150 == 0:
                    print(f"  frame {k}/{total}", flush=True)
        except BrokenPipeError:
            sys.exit("FFmpeg se cerró antes de tiempo (mirá el error de arriba).")
        finally:
            navegador.close()

    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        sys.exit("FFmpeg terminó con error.")
    print(f"Listo: {SALIDA}")


if __name__ == "__main__":
    main()
