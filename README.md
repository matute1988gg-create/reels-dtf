# Fábrica de Reels DTF (www.dtf-arg.com)

Corre 100% en GitHub Actions. Tema → Gemini → voz edge-tts → plantilla HTML animada → Playwright + FFmpeg → `reel_dtf.mp4`.

## Cómo usarlo
1. Subí estos archivos a un repositorio de GitHub.
2. Settings → Secrets and variables → Actions → New repository secret: `GEMINI_API_KEY` (gratis en https://aistudio.google.com/apikey).
3. Actions → **Reels DTF** → Run workflow → escribí el tema.
4. Al terminar, bajá el video desde **Artifacts → reel_dtf**.

## Recomendado: revisar los datos antes de publicar
Marcá **solo_guion** para que genere únicamente `datos_video.json` (rápido, 1 minuto). Revisá que las medidas, temperaturas y tiempos sean correctos para tu taller. Si hay que corregir algo, editá el JSON y avisame cómo querés cargar tus propios datos.

## Archivos
- `generar_guion.py`, `generar_audio.py`, `renderizar.py`: los 3 pasos del pipeline.
- `plantilla_reel.html`: el diseño (colores, textos y animaciones se editan acá).
