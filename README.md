# White Hole · fábrica de Shorts

Sistema 100 % gratis que genera un Short animado cada día y te lo manda a Telegram,
listo para subir a YouTube, TikTok y Facebook.

## Cómo funciona

1. En `guiones/pendientes/` hay una cola de guiones (archivos `.json`).
2. Todos los días a las **7:23 a. m. (hora Colombia)**, GitHub Actions toma el primero de la cola,
   genera la voz (Piper, gratis), anima cada escena con código y arma el video con FFmpeg.
3. El video te llega a **Telegram** con el título, la descripción, los hashtags y las fuentes.
4. El guion pasa a `guiones/publicados/` para no repetirse.
5. Si la cola se vacía, el bot te avisa por Telegram.

## Primera vez

- Secretos en **Settings → Secrets and variables → Actions**: `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`.
- Escríbele cualquier mensaje a tu bot en Telegram (si no, no te puede escribir).
- Para probar ya mismo: pestaña **Actions → Short diario → Run workflow**.

## Formato de un guion

```json
{
  "titulo": "Título para YouTube",
  "descripcion": "Descripción corta",
  "hashtags": "#tech #shorts",
  "fuentes": ["https://..."],
  "velocidad": 0.9,
  "escenas": [
    {"texto": "Lo que dice la voz.", "visual": {"tipo": "title", "lines": ["TEXTO", "GRANDE"], "sync": "voz"}}
  ]
}
```

`sync` = palabra del texto en la que aparece ese elemento (sincroniza animación y voz).

### Plantillas (`tipo`)

| tipo | qué muestra | parámetros principales |
|---|---|---|
| `title` | texto grande que entra deslizándose | `lines`, `pre`, `colors`, `size`, `sync` |
| `counter` | número que cuenta hasta un valor | `from`, `to`, `decimals`, `prefix`, `suffix`, `label`, `note` |
| `bars` | barras comparativas | `items: [{label, value, value_text, color, sync}]`, `note` |
| `versus` | dos tarjetas lado a lado | `left`, `right` (`label`, `value`, `sub`, `color`), `badge` |
| `equation` | operación paso a paso con resultado | `lines: [{text, sub, color, sync}]`, `result` |
| `bigword` | una palabra protagonista | `word`, `sub`, `sub2`, `pre`, `size` |
| `card` | tarjeta + panel con barra de progreso | `title`, `tag`, `panel: {label, value, progress}` |
| `outro` | cierre + botón de seguir | `lines`, `syncs`, `button` |

Colores disponibles: `blue`, `ice`, `white`, `grey`, `warm`.

## Probar en tu PC

```bash
pip install -r requirements.txt
# descarga la voz una vez (ver el workflow) en la carpeta voices/
python scripts/daily.py --prueba
```

## Estructura

```
engine/make_short.py      motor de video (plantillas, voz, subtítulos, música)
scripts/daily.py          tarea diaria (elegir guion → render → Telegram)
.github/workflows/        programación diaria en GitHub Actions
guiones/pendientes/       cola de guiones
guiones/publicados/       guiones ya enviados
assets/fonts/             tipografía Inter (licencia OFL)
assets/marca/             logos del canal
```
