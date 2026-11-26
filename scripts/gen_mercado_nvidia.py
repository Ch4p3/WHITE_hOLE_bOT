import json, os, pandas as pd
R = '/home/claude/white_hole_bot/guiones'
ESM = dict(idioma="es", velocidad=0.95, kokoro=dict(voz="em_alex", lang="es", velocidad=1.05), serie="Aprende a leer el mercado")
MES = {10: "oct", 11: "nov", 9: "sep"}
d = pd.read_csv('/tmp/datos/NVDA_diario.csv', index_col=0, parse_dates=True)['2026-10-01':]
SER = [[f"{x.day} {MES[x.month]}", round(float(v), 2)] for x, v in d['Close'].items()]
idx = {k: i for i, (k, _) in enumerate(SER)}
I = lambda s: idx[s]
FUENTE = "Cierres diarios NVDA · Yahoo Finance"
def lista(titulo, items, pastilla="LO QUE TE LLEVAS", **k):
    v = dict(tipo="lista", pastilla=pastilla, titulo=titulo, items=items); v.update(k); return v
def save(path, base, meta, esc):
    g = dict(base); g.update(meta); g["escenas"] = esc
    json.dump(g, open(os.path.join(R, path), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(path, sum(len(s["texto"].split()) for s in esc), "palabras")

# ---------- Esquema 5+3 (ilustrativo, NO son precios reales)
piv = [100, 130, 115, 175, 155, 195, 165, 180, 140]
ESQ = []
for a, b in zip(piv, piv[1:]):
    for j in range(6): ESQ.append(["", round(a + (b - a) * j / 6, 1)])
ESQ.append(["", piv[-1]])
EI = [0, 6, 12, 18, 24, 30, 36, 42, 48]
lab = ["", "1", "2", "3", "4", "5", "A", "B", "C"]
def marcas(hasta=9, sync=None):
    out = []
    for k in range(1, hasta):
        out.append(dict(i=EI[k], texto=lab[k], pos="arriba" if k in (1, 3, 5, 7) else "abajo",
                        color="green" if k <= 5 else "warm", sync=sync))
    return out
ESQV = dict(tipo="mercado", serie=ESQ, ymin=85, ymax=210, precio_cabeza=False, fuente="esquema ilustrativo")

save("es/pendientes/000c1_mercado_ondas_elliott.json", ESM, dict(
  titulo="Ondas de Elliott explicadas en 60 segundos 📈 (5 + 3)",
  descripcion="Las ondas de Elliott (Ralph Nelson Elliott, años 30) dicen que el mercado se mueve en un patrón que se repite: 5 ondas a favor de la tendencia y 3 de corrección. Las 3 reglas: 1) la onda 2 nunca supera el inicio de la onda 1; 2) la onda 3 nunca es la más corta entre 1, 3 y 5; 3) la onda 4 no entra en la zona de la onda 1. El conteo es subjetivo: úsalo como mapa, no como bola de cristal. Contenido educativo, no es asesoría financiera. En el próximo video lo aplicamos a la caída real de Nvidia 👇",
  hashtags="#trading #ondasdeelliott #bolsa #inversion #analisistecnico #WhiteHole #reels",
  fuentes=["https://www.investopedia.com/terms/e/elliottwavetheory.asp"]), [
  dict(texto="Cinco ondas a favor, tres en contra. Muchos traders creen que el mercado se mueve así. Se llama ondas de Elliott.",
       visual=dict(ESQV, pre="el patrón de Elliott", titulo="5 + 3", marcas=marcas(), vel=0.8)),
  dict(texto="Lo propuso Ralph Nelson Elliott en los años treinta: el precio refleja la psicología de la gente, del miedo a la euforia, una y otra vez.",
       visual=dict(tipo="bigword", pre="años 30 · Ralph Nelson Elliott", word="MIEDO → EUFORIA", size=130, sync="psicología", sub="y se repite")),
  dict(texto="Primero, cinco ondas de impulso. La uno, la tres y la cinco empujan. La dos y la cuatro son retrocesos.",
       visual=dict(ESQV, pre="impulso", titulo="5 ONDAS A FAVOR", hasta=30, marcas=marcas(6), vel=0.8)),
  dict(texto="Después, una corrección de tres: A, B y C. Y vuelve a empezar.",
       visual=dict(ESQV, pre="corrección", titulo="A · B · C", desde=30, marcas=marcas(), vel=0.6)),
  dict(texto="Tres reglas que nunca se rompen: la dos no pasa el inicio de la uno, la tres nunca es la más corta, y la cuatro no se mete en la zona de la uno.",
       visual=lista("LAS 3 REGLAS", [dict(texto="La 2 no pasa el inicio de la 1", sync="dos"),
                                     dict(texto="La 3 nunca es la más corta", sync="corta"),
                                     dict(texto="La 4 no toca la zona de la 1", sync="cuatro")], pastilla="NUNCA SE ROMPEN")),
  dict(texto="Y se combina con Fibonacci para estimar los retrocesos: treinta y ocho, cincuenta o sesenta y uno por ciento.",
       visual=dict(tipo="bigword", pre="se combina con Fibonacci", word="38% · 50% · 61,8%", size=120, sync="fibonacci", sub="zonas típicas de retroceso")),
  dict(texto="Lo honesto: dos traders pueden contar distinto. Úsalo como mapa, y siempre con stop loss.",
       visual=lista("ÚSALO BIEN", [dict(texto="Es un mapa, no una bola de cristal", emoji="🗺️", sync="mapa"),
                                   dict(texto="El conteo es subjetivo", emoji="🤔", sync="distinto"),
                                   dict(texto="Siempre con stop loss", emoji="🛑", sync="stop")], boton="GUÁRDALO", boton_sync="stop")),
  dict(texto="En el próximo video lo probamos con la caída real de Nvidia. Síguenos.",
       visual=dict(tipo="outro", lines=["¿NVIDIA", "RESPETÓ", "LAS ONDAS?"], syncs=[None, "probamos", "respetó"], button="SÍGUENOS", button_sync="síguenos")),
])

# ---------- Nvidia: la historia + ¿respetó Elliott? (precios reales)
fib = round(124.50 + 0.382 * (243.37 - 124.50), 2)
M = lambda dia, t, pos, c="green", sync=None: dict(i=I(dia), texto=t, pos=pos, color=c, sync=sync)
OLAS = [M("6 oct", "▼", "arriba", "warm"), M("16 oct", "1", "abajo"), M("21 oct", "2", "arriba"), M("10 nov", "3", "abajo"),
        M("11 nov", "4", "arriba"), M("20 nov", "5", "abajo")]
REAL = dict(tipo="mercado", serie=SER, fuente=FUENTE, ymin=100, ymax=255, fechas=[I("6 oct"), I("12 nov"), I("25 nov")])
save("es/pendientes/000c2_mercado_nvidia_elliott.json", ESM, dict(
  titulo="Nvidia perdió la confianza… ¿y respetó las ondas de Elliott? 📉📈",
  descripcion="Lo que pasó (precios de cierre reales, Yahoo Finance):\n• 6 oct 2026: máximo de US$243,37 (intradía).\n• 8 nov: la junta abre una investigación interna sobre su CEO.\n• 12 nov: Nvidia anuncia la renuncia de Jensen Huang.\n• 20 nov: mínimo de US$124,50 (−49% desde el máximo).\n• 23 nov: la junta lo trae de vuelta; la acción sube 31,5% en un día (≈US$950.000 millones, récord histórico).\n\nConteo de Elliott (uno posible, no el único): la caída hizo 5 ondas y cumple las 3 reglas; el rebote del 23 llegó a la zona del 38,2% de Fibonacci (onda A). El conteo se invalida si el precio pierde US$124,50.\n\n¿Qué son las ondas de Elliott? Mira el video anterior en el perfil.\nContenido educativo, no es recomendación de compra ni de venta. 👇",
  hashtags="#nvidia #bolsa #trading #ondasdeelliott #inversion #WhiteHole #reels",
  fuentes=["https://www.sec.gov/Archives/edgar/data/0001045810/000104581026000082/nvda-20261111.htm",
           "https://www.nbcnews.com/business/markets/stocks-rebound-ai-tech-selloff-nvidia-rcna610833",
           "https://finance.yahoo.com/quote/NVDA/history"]), [
  dict(texto="Nvidia perdió casi la mitad de su valor en seis semanas, y luego subió treinta y uno por ciento en un día. ¿Caos, o un patrón?",
       visual=dict(REAL, pre="NVIDIA · oct–nov 2026", titulo="−49% … Y +31,5%", vel=0.75)),
  dict(texto="Seis de octubre: máximo histórico, doscientos cuarenta y tres dólares.",
       visual=dict(REAL, pre="6 de octubre", titulo="MÁXIMO: US$243", hasta=I("6 oct"), vel=0.6, precio_cabeza=False)),
  dict(texto="El ocho de noviembre, la junta investiga a su CEO, Jensen Huang. El doce, renuncia.",
       visual=dict(REAL, pre="la investigación y la renuncia", titulo="SE VA JENSEN HUANG", desde=I("6 oct"), hasta=I("12 nov"), vel=0.8)),
  dict(texto="Se fue la confianza, salió la plata, y el veinte de noviembre tocó ciento veinticuatro dólares.",
       visual=dict(REAL, pre="se fue la confianza", titulo="MÍNIMO: US$124", desde=I("12 nov"), hasta=I("20 nov"), vel=0.7, precio_cabeza=False)),
  dict(texto="El lunes veintitrés lo trajeron de vuelta: treinta y uno coma cinco por ciento en un día. Unos novecientos cincuenta mil millones de dólares. Récord histórico.",
       visual=dict(tipo="bigword", pre="23 de noviembre: vuelve Huang", word="+31,5%", size=230, sync="treinta", sub="≈ US$950.000 millones en un día · récord", color="green")),
  dict(texto="¿Respetó las ondas de Elliott? La caída tuvo cinco ondas.",
       visual=dict(REAL, pre="¿respetó a Elliott?", titulo="LA CAÍDA: 5 ONDAS", hasta=I("20 nov"), marcas=OLAS, vel=0.6, precio_cabeza=False)),
  dict(texto="Y cumple las tres reglas: la dos no pasó el inicio, la tres fue la más larga, y la cuatro no tocó la zona de la uno.",
       visual=lista("LAS 3 REGLAS", [dict(texto="La 2 no pasó el inicio (222 < 243)", emoji="✅", sync="dos"),
                                     dict(texto="La 3 fue la más larga", emoji="✅", sync="larga"),
                                     dict(texto="La 4 no tocó la zona de la 1", emoji="✅", sync="cuatro")], pastilla="NVIDIA")),
  dict(texto="El rebote llegó a ciento setenta y un dólares: justo el treinta y ocho por ciento de Fibonacci. Esa sería la onda A.",
       visual=dict(REAL, pre="el rebote", titulo="ONDA A → 38,2%", estatico=True, precio_cabeza=False,
                   marcas=OLAS + [M("23 nov", "A", "arriba", "warm")],
                   niveles=[dict(precio=fib, texto="38,2% Fibonacci", color="warm", sync="treinta")])),
  dict(texto="Si se cumple, viene una B bajando y una C subiendo. Si pierde los ciento veinticuatro con cincuenta, el conteo se cae.",
       visual=dict(REAL, pre="lo que viene", titulo="¿B Y LUEGO C?", estatico=True, precio_cabeza=True,
                   marcas=OLAS + [M("23 nov", "A", "arriba", "warm"), M("25 nov", "B", "abajo", "warm")],
                   niveles=[dict(precio=124.50, texto="se invalida: US$124,50", color="warm", sync="pierde")])),
  dict(texto="La confianza mueve la plata, y la plata mueve el precio. Es educativo, no una recomendación. ¿Se cumple la onda C? Comenta SÍ o NO.",
       visual=dict(tipo="outro", lines=["CONFIANZA →", "PLATA →", "PRECIO"], syncs=[None, "plata", "precio"], button="¿SÍ O NO?", button_sync="comenta")),
])
