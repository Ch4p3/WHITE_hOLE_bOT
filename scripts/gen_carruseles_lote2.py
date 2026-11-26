import json, os, pandas as pd, re
ROOT = '/home/claude/white_hole_bot'
CP = os.path.join(ROOT, 'guiones/carruseles/pendientes'); os.makedirs(CP, exist_ok=True)
BASE = "https://ch4p3.github.io/WHITE_hOLE_bOT/r/"
def guardar(nombre, g):
    json.dump(g, open(os.path.join(CP, nombre), "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(nombre, len(g["slides"]), "láminas")

# ---------- 002 Abdomen
guardar("002_abdomen_casa.json", dict(idioma="es", personaje="monita", palabra="ABDOMEN", enlace=BASE + "abdomen/",
  titulo="Rutina de abdomen en casa (y la verdad sobre la barriga) 🔥",
  caption="Rutina de abdomen en casa (y la verdad sobre la barriga) 🔥\n\n3 ejercicios · 3 series · unos 10 minutos. Ojo: en un estudio, 6 semanas solo de abdominales no bajaron la grasa de la barriga, pero sí dieron más fuerza. La grasa baja con actividad diaria y alimentación; el abdomen fuerte se construye con esto.\n\n👉 Comenta ABDOMEN y te respondo con la rutina completa para imprimir.\n🔖 Guárdala para tu próximo entrenamiento.",
  hashtags="#abdomen #rutina #ejercicioencasa #core #fitness #WhiteHole",
  fuentes=["https://pubmed.ncbi.nlm.nih.gov/21804427/", "https://www.who.int/initiatives/behealthy/physical-activity"],
  slides=[
   dict(tipo="portada", pre="RUTINA EN CASA", titulo="ABDOMEN SIN EXCUSAS", sub="3 ejercicios · 10 min + la verdad sobre la barriga", pose="abdominal"),
   dict(tipo="texto", emoji="🔬", titulo="PRIMERO, LA VERDAD", puntos=[
       "Un grupo hizo abdominales 5 días por semana durante 6 semanas",
       "La grasa de la barriga NO cambió… pero ganaron fuerza",
       "La grasa baja de todo el cuerpo: actividad diaria + comida"], nota="Vispute y col., J Strength Cond Res, 2011"),
   dict(tipo="item", titulo="ABDOMINAL CORTO", dosis="3 × 15", pose="abdominal", t=0.55, puntos=["Sube solo los hombros del piso", "No jales el cuello con las manos"]),
   dict(tipo="item", titulo="PLANCHA", dosis="3 × 30 segundos", pose="plancha", t=0.5, puntos=["Cuerpo recto como una tabla", "Aprieta la barriga y los glúteos"]),
   dict(tipo="item", titulo="PUENTE DE GLÚTEO", dosis="3 × 15", pose="puente", t=0.55, puntos=["Protege tu espalda baja", "Aprieta 2 segundos arriba"]),
   dict(tipo="texto", emoji="⏱️", titulo="CÓMO HACERLA", puntos=[
       "3 veces por semana, 1 minuto de descanso entre series",
       "¿Fácil? Plancha de 45 s o abdominales más lentos",
       "Y camina todos los días: eso es lo que baja la grasa"], nota="Si tienes una lesión o dolor, consulta antes con un profesional de la salud."),
   dict(tipo="cierre", palabra="ABDOMEN", promesa="y te respondo con la rutina completa para imprimir")]))

# ---------- 003 7.000 pasos
guardar("003_7000_pasos.json", dict(idioma="es", personaje="monita", palabra="PASOS", enlace=BASE + "pasos/",
  titulo="No necesitas 10.000 pasos: la ciencia dice 7.000 👟",
  caption="No necesitas 10.000 pasos: la ciencia dice 7.000 👟\n\nUn metaanálisis de 57 estudios (The Lancet Public Health, 2025) encontró que, frente a 2.000 pasos al día, 7.000 se asociaron con 47% menos riesgo de muerte prematura, casi igual que 10.000. Y desde 4.000 ya hay beneficios.\n\n👉 Comenta PASOS y te envío el plan de 6 semanas para imprimir.\n🔖 Guárdalo y empieza hoy.",
  hashtags="#pasos #caminar #salud #habitos #ciencia #WhiteHole",
  fuentes=["https://pubmed.ncbi.nlm.nih.gov/40713949/"],
  slides=[
   dict(tipo="portada", pre="LA CIENCIA DICE", titulo="NO NECESITAS 10.000 PASOS", sub="con 7.000 ganas casi todo", pose="caminar"),
   dict(tipo="texto", emoji="📊", titulo="EL ESTUDIO", puntos=[
       "57 estudios · más de 160.000 adultos",
       "7.000 vs 2.000 pasos: −47% riesgo de muerte prematura",
       "Casi igual que con 10.000 · demencia: −38%"], nota="Ding y col., The Lancet Public Health, 2025. Es una asociación, no prueba causa y efecto."),
   dict(tipo="texto", emoji="🗓️", titulo="TU PLAN DE 6 SEMANAS", puntos=[
       "Semana 1: mide tus pasos normales (tu base)",
       "Semanas 2 a 5: súmale 1.000 cada semana",
       "Semana 6: apunta a 7.000 al día"], nota="¿Ya caminas más? Mantente; no hace falta llegar a 10.000."),
   dict(tipo="texto", emoji="🚶", titulo="TRUCOS PARA SUMAR PASOS", puntos=[
       "Camina 2 a 5 minutos después de cada comida",
       "Habla por teléfono caminando",
       "Escaleras en vez de ascensor · bájate una parada antes"]),
   dict(tipo="cierre", palabra="PASOS", promesa="y te envío el plan de 6 semanas para imprimir")]))

# ---------- 004 Nvidia: 3 precios para vigilar (precios reales)
MES = {10: "oct", 11: "nov"}
d = pd.read_csv('/tmp/datos/NVDA_diario.csv', index_col=0, parse_dates=True)['2026-10-01':]
SER = [[f"{x.day} {MES[x.month]}", round(float(v), 2)] for x, v in d['Close'].items()]
I = {k: i for i, (k, _) in enumerate(SER)}
def M(dia, t, pos, c="green", nota=None):
    m = dict(i=I[dia], texto=t, pos=pos, color=c)
    if nota: m["nota"] = nota
    return m
OLAS = [M("6 oct", "▼", "arriba", "warm"), M("16 oct", "1", "abajo"), M("21 oct", "2", "arriba"), M("10 nov", "3", "abajo"),
        M("11 nov", "4", "arriba"), M("20 nov", "5", "abajo"), M("23 nov", "A", "arriba", "warm"), M("25 nov", "B", "abajo", "warm")]
G = dict(tipo="mercado", serie=SER, fuente="Cierres diarios NVDA · Yahoo Finance", ymin=100, ymax=255, precio_cabeza=False,
         fechas=[I["6 oct"], I["12 nov"], I["25 nov"]], y_tope=520, y_base=1250)
VERDE = [[2, 145], [3, 143], [6, 158], [8, 153], [12, 172], [14, 166], [19, 187], [22, 198]]
guardar("004_nvidia_3_precios.json", dict(idioma="es", personaje="monita", palabra="NVIDIA", enlace=BASE + "nvidia-elliott/",
  titulo="Nvidia y las ondas de Elliott: 3 precios para vigilar 📈",
  caption="Nvidia y las ondas de Elliott: 3 precios para vigilar 📈\n\nLa caída de octubre-noviembre de 2026 hizo 5 ondas y cumplió las 3 reglas. Si el patrón se cumple, la onda C apuntaría a US$184–188 y luego a US$198. Si pierde US$124,50, el conteo se invalida. Precios reales de Yahoo Finance.\n\n⚠️ Contenido educativo, no es recomendación de inversión.\n👉 Comenta NVIDIA y te envío la guía completa de ondas de Elliott con el caso Nvidia.\n🔖 Guárdalo y vuelve en unas semanas a ver si se cumplió.",
  hashtags="#nvidia #bolsa #trading #ondasdeelliott #fibonacci #WhiteHole",
  fuentes=["https://finance.yahoo.com/quote/NVDA/history"],
  slides=[
   dict(tipo="portada", pre="NVIDIA · ONDAS DE ELLIOTT", titulo="3 PRECIOS PARA VIGILAR", sub="lo que diría el patrón · precios reales", emoji="📈"),
   dict(tipo="mercado", grafico=dict(G, pre="oct–nov 2026", titulo="LA CAÍDA: 5 ONDAS", marcas=OLAS),
        texto="De US$243 a US$124,50 (−49%) en 5 ondas. Después, el rebote A (+31,5% en un día) y la onda B."),
   dict(tipo="texto", emoji="✅", titulo="CUMPLE LAS 3 REGLAS", puntos=[
       "La onda 2 no pasó el inicio: US$222 < US$243",
       "La onda 3 fue la más larga: US$56 vs US$30 y US$53",
       "La onda 4 (US$177) no tocó la zona de la 1 (US$213)"]),
   dict(tipo="mercado", grafico=dict(G, pre="si se cumple", titulo="ONDA C → US$184–198", marcas=OLAS[6:], futuro=22, futuro_txt="proyección (sin fechas)",
        niveles=[dict(precio=186, texto="objetivo 1 · $184–188", color="green"), dict(precio=197.96, texto="objetivo 2 · $198", color="green"),
                 dict(precio=124.50, texto="invalidación · $124,50", color="warm")],
        proyecciones=[dict(puntos=VERDE, color="green")]),
        texto="Proyección ilustrativa: Elliott marca zonas de precio, no fechas."),
   dict(tipo="texto", emoji="👀", titulo="LOS 3 PRECIOS", puntos=[
       "US$142–148: zona donde debería girar la onda B",
       "Más de US$171,50: confirma que la onda C está en marcha",
       "Menos de US$124,50: el conteo se invalida"]),
   dict(tipo="texto", emoji="⚠️", titulo="LA PARTE HONESTA", puntos=[
       "Es un conteo posible, no el único",
       "Es un mapa, no una promesa: siempre con stop loss",
       "Contenido educativo, no recomendación de inversión"]),
   dict(tipo="cierre", palabra="NVIDIA", promesa="y te envío la guía de ondas de Elliott con el caso Nvidia")]))
