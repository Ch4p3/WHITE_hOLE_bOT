import json, os, pandas as pd
R = '/home/claude/white_hole_bot/guiones'
ESM = dict(idioma="es", velocidad=0.95, kokoro=dict(voz="em_alex", lang="es", velocidad=1.0), serie="Aprende a leer el mercado")
MES = {10: "oct", 11: "nov"}
d = pd.read_csv('/tmp/datos/NVDA_diario.csv', index_col=0, parse_dates=True)['2026-10-01':]
SER = [[f"{x.day} {MES[x.month]}", round(float(v), 2)] for x, v in d['Close'].items()]
idx = {k: i for i, (k, _) in enumerate(SER)}; I = lambda s: idx[s]
REAL = dict(tipo="mercado", serie=SER, fuente="Cierres diarios NVDA · Yahoo Finance", ymin=100, ymax=255,
            fechas=[I("6 oct"), I("12 nov"), I("25 nov")])
def M(dia, t, pos, c="green", nota=None, sync=None):
    m = dict(i=I(dia), texto=t, pos=pos, color=c, sync=sync)
    if nota: m["nota"] = nota
    return m
W = {"top": M("6 oct", "▼", "arriba", "warm"), "1": M("16 oct", "1", "abajo"), "2": M("21 oct", "2", "arriba"),
     "3": M("10 nov", "3", "abajo"), "4": M("11 nov", "4", "arriba"), "5": M("20 nov", "5", "abajo"),
     "A": M("23 nov", "A", "arriba", "warm"), "B": M("25 nov", "B", "abajo", "warm")}
def ws(*k, notas=None):
    out = []
    for x in k:
        m = dict(W[x])
        if notas and x in notas: m["nota"] = notas[x]
        out.append(m)
    return out
B50, B618 = 148.00, 142.45
F50, F618, CA = 183.94, 197.96, 188.17
esc = [
 dict(texto="Nvidia perdió casi la mitad de su valor en seis semanas, y luego subió treinta y uno por ciento en un solo día. ¿Fue puro caos, o siguió un patrón? Vamos onda por onda.",
      visual=dict(REAL, pre="NVIDIA · oct–nov 2026", titulo="−49% … Y +31,5%", vel=0.75)),
 dict(texto="Seis de octubre: máximo histórico, doscientos cuarenta y tres dólares. Todo el mundo quería Nvidia.",
      visual=dict(REAL, pre="6 de octubre", titulo="MÁXIMO: US$243", hasta=I("6 oct"), vel=0.5, precio_cabeza=False)),
 dict(texto="Onda uno: la primera caída, hasta unos doscientos trece. Doce por ciento, y todavía sin ninguna noticia grave. Muchos la vieron como una oportunidad.",
      visual=dict(REAL, pre="onda 1", titulo="PRIMERA CAÍDA: −12%", desde=I("6 oct"), hasta=I("16 oct"), marcas=ws("top", "1", notas={"1": "$213"}), precio_cabeza=False)),
 dict(texto="Onda dos: compraron la caída, y el precio rebotó hasta doscientos veintidós. Pero no recuperó el máximo.",
      visual=dict(REAL, pre="onda 2", titulo="REBOTE A $222", desde=I("16 oct"), hasta=I("21 oct"), marcas=ws("top", "1", "2", notas={"2": "$222"}), precio_cabeza=False)),
 dict(texto="Onda tres: el ocho de noviembre, la junta abre una investigación interna sobre su CEO, Jensen Huang. El doce, renuncia. El precio se desploma hasta ciento sesenta y seis. Y fíjate: en Elliott, la onda tres suele ser la más fuerte.",
      visual=dict(REAL, pre="onda 3 · investigación y renuncia", titulo="LA MÁS FUERTE: −25%", desde=I("21 oct"), hasta=I("10 nov"), marcas=ws("top", "1", "2", "3", notas={"3": "$166"}), precio_cabeza=False)),
 dict(texto="Onda cuatro: un rebote cortito, hasta ciento setenta y siete.",
      visual=dict(REAL, pre="onda 4", titulo="REBOTE CORTO", desde=I("10 nov"), hasta=I("11 nov"), marcas=ws("top", "1", "2", "3", "4", notas={"4": "$177"}), precio_cabeza=False, vel=0.4)),
 dict(texto="Onda cinco: el diecisiete llegan los primeros resultados sin Huang, el miedo sigue, y el veinte de noviembre toca ciento veinticuatro con cincuenta. En total, menos cuarenta y nueve por ciento.",
      visual=dict(REAL, pre="onda 5", titulo="FONDO: US$124,50", desde=I("11 nov"), hasta=I("20 nov"), marcas=ws("top", "1", "2", "3", "4", "5", notas={"5": "−49%"}), precio_cabeza=False)),
 dict(texto="Y el lunes veintitrés, la junta lo trae de vuelta. Treinta y uno coma cinco por ciento en un día: unos novecientos cincuenta mil millones de dólares. El récord de la historia.",
      visual=dict(tipo="bigword", pre="23 de noviembre: vuelve Huang", word="+31,5%", size=230, sync="treinta", sub="≈ US$950.000 millones en un día · récord", color="green")),
 dict(texto="¿Cumplió las reglas de Elliott? Las tres. La dos no pasó el inicio. La tres fue la más larga, cincuenta y seis dólares, contra treinta de la uno y cincuenta y tres de la cinco. Y la cuatro nunca tocó la zona de la uno.",
      visual=dict(tipo="lista", pastilla="NVIDIA", titulo="LAS 3 REGLAS", items=[
          dict(texto="La 2 no pasó el inicio: $222 < $243", emoji="✅", sync="dos"),
          dict(texto="La 3 fue la más larga: $56 vs $30 y $53", emoji="✅", sync="larga"),
          dict(texto="La 4 ($177) lejos de la 1 ($213)", emoji="✅", sync="cuatro")])),
 dict(texto="Después de cinco ondas viene una corrección de tres. El rebote del lunes llegó a ciento setenta y uno con cincuenta: justo el treinta y ocho por ciento de Fibonacci de toda la caída. Esa es la onda A.",
      visual=dict(REAL, pre="la corrección empieza", titulo="ONDA A = 38,2%", estatico=True, precio_cabeza=False,
                  marcas=ws("top", "1", "2", "3", "4", "5", "A", notas={"A": "$171,50"}),
                  niveles=[dict(precio=169.91, texto="38,2% Fibonacci", color="warm", sync="treinta")])),
 dict(texto="Ahora va la onda B, que suele devolver entre la mitad y el sesenta y dos por ciento de la A. O sea, entre ciento cuarenta y ocho y ciento cuarenta y dos. Y ayer ya tocó ciento cuarenta y uno.",
      visual=dict(REAL, pre="onda B: ¿dónde termina?", titulo="ZONA B: $142–148", estatico=True, precio_cabeza=False,
                  marcas=ws("top", "1", "2", "3", "4", "5", "A", "B", notas={"B": "$141"}),
                  niveles=[dict(precio=B50, texto="50% de la A · $148", color="grey", sync="mitad"),
                           dict(precio=B618, texto="61,8% · $142", color="grey", sync="sesenta")])),
 dict(texto="Si el patrón se cumple, viene la onda C hacia arriba. Primer objetivo: entre ciento ochenta y cuatro y ciento ochenta y ocho, donde coinciden la mitad de la caída y una C igual a la A. Segundo objetivo: unos ciento noventa y ocho, el sesenta y uno coma ocho por ciento.",
      visual=dict(REAL, pre="si se cumple: onda C", titulo="OBJETIVOS: $184–188 · $198", estatico=True, precio_cabeza=False,
                  marcas=ws("top", "1", "2", "3", "4", "5", "A", "B"),
                  niveles=[dict(precio=186, texto="objetivo 1 · $184–188", color="green", sync="primer"),
                           dict(precio=F618, texto="objetivo 2 · $198", color="green", sync="segundo")])),
 dict(texto="¿Y si se rompe? Si el precio baja de ciento veinticuatro con cincuenta, el conteo estaba mal. No vuelve a empezar: significa que la caída no había terminado, y lo más probable es que siga bajando. Ahí toca volver a contar.",
      visual=dict(REAL, pre="si se rompe", titulo="BAJO $124,50: SE RECUENTA", estatico=True, precio_cabeza=False,
                  marcas=ws("top", "1", "2", "3", "4", "5", "A", "B"),
                  niveles=[dict(precio=124.50, texto="invalidación · $124,50", color="warm", sync="ciento")])),
 dict(texto="Así que, el veredicto. Hoy, el patrón sigue vivo: el precio está en la onda B y por encima de ciento veinticuatro con cincuenta. Mientras no la pierda, Elliott apunta hacia arriba.",
      visual=dict(tipo="versus", left=dict(label="SE CUMPLE", value="$184–198", color="green", sync="vivo"), right=dict(label="SE ROMPE", value="< $124,50", color="warm", sync="pierda"))),
 dict(texto="Ojo: esto no es una recomendación de inversión. Es un mapa, no una promesa, y siempre con stop loss. ¿Tú crees que se cumple? Comenta SÍ o NO, y cuando se resuelva, te traigo la parte dos.",
      visual=dict(tipo="outro", lines=["¿SE CUMPLE", "LA ONDA C?"], syncs=[None, "cumple"], button="COMENTA SÍ O NO", button_sync="comenta")),
]
P1 = esc[0:9]; P2 = esc[9:]
P1[0]["texto"] = "Nvidia perdió casi la mitad de su valor en seis semanas, y luego subió treinta y uno por ciento en un día. ¿Caos, o un patrón? Vamos onda por onda."
P1[1]["texto"] = "Seis de octubre: máximo histórico, doscientos cuarenta y tres dólares."
P1.append(dict(texto="En la parte dos: hasta dónde podría subir si el patrón se cumple, y qué pasa si se rompe. Síguenos para no perdértela.",
     visual=dict(tipo="outro", lines=["PARTE 2:", "¿HASTA DÓNDE", "SUBIRÍA?"], syncs=[None, "dónde", "rompe"], button="SÍGUENOS", button_sync="síguenos")))
P2.insert(0, dict(texto="Parte dos. En la parte uno vimos que la caída de Nvidia hizo cinco ondas y cumplió las tres reglas de Elliott. Ahora, lo que sigue.",
     visual=dict(REAL, pre="parte 2 · resumen", titulo="5 ONDAS ✓ 3 REGLAS ✓", estatico=True, precio_cabeza=False, marcas=ws("top", "1", "2", "3", "4", "5"))))
for sc in P2:
    v = sc["visual"]
    if v.get("tipo") == "mercado" and v.get("niveles") and any(n["precio"] in (B50, 186, 124.50) for n in v["niveles"]):
        v["marcas"] = ws("A", "B")
P2[2]["visual"]["niveles"] = [dict(precio=145.2, texto="zona B · $142–148", color="grey", sync="mitad")]
P2[2]["visual"]["marcas"] = ws("A", "B", notas={"B": "$141"})

FUT = dict(futuro=22, futuro_txt="proyección (sin fechas)")
VERDE = [[2, 145], [3, 143], [6, 158], [8, 153], [12, 172], [14, 166], [19, 187]]
ROTO = [[2, 143], [5, 131], [8, 117]]
base = dict(REAL, estatico=True, precio_cabeza=False, **FUT)
P2 = [
 dict(texto="Parte dos. La caída de Nvidia hizo cinco ondas y cumplió las tres reglas. Ahora, lo que viene.",
      visual=dict(base, pre="parte 2 · resumen", titulo="5 ONDAS ✓ 3 REGLAS ✓", marcas=ws("top", "1", "2", "3", "4", "5"))),
 dict(texto="El rebote del lunes llegó a ciento setenta y uno con cincuenta: el treinta y ocho por ciento de Fibonacci. Esa es la onda A.",
      visual=dict(base, pre="la corrección empieza", titulo="ONDA A = 38,2%", marcas=ws("top", "1", "2", "3", "4", "5", "A", notas={"A": "$171,50"}),
                  niveles=[dict(precio=169.91, texto="38,2% Fibonacci", color="warm", sync="treinta")])),
 dict(texto="La B suele devolver entre la mitad y el sesenta y dos por ciento de la A: de ciento cuarenta y ocho a ciento cuarenta y dos. Ayer tocó ciento cuarenta y uno.",
      visual=dict(base, pre="onda B: ¿dónde termina?", titulo="ZONA B: $142–148", marcas=ws("A", "B", notas={"B": "$141"}),
                  niveles=[dict(precio=145.2, texto="zona B · $142–148", color="grey", sync="mitad")])),
 dict(texto="Si se cumple, se vería así: la B termina en esa zona, y la C sube en cinco ondas pequeñas hasta el primer objetivo, de ciento ochenta y cuatro a ciento ochenta y ocho.",
      visual=dict(base, pre="si se cumple", titulo="ONDA C → $184–188", marcas=ws("A", "B"),
                  niveles=[dict(precio=186, texto="objetivo 1 · $184–188", color="green", sync="primer")],
                  proyecciones=[dict(puntos=VERDE, color="green", sync="así", dur=2.6,
                                     etiquetas=[dict(p=6, texto="C", k=1.0, size=44)])])),
 dict(texto="Ahí coinciden la mitad de la caída y una C igual a la A. Con fuerza, puede estirarse hasta ciento noventa y ocho. Ojo: Elliott marca precios, no fechas.",
      visual=dict(base, pre="si viene con fuerza", titulo="HASTA $198", marcas=ws("A", "B"),
                  niveles=[dict(precio=186, texto="objetivo 1 · $184–188", color="green"), dict(precio=F618, texto="objetivo 2 · $198", color="green", sync="estirarse")],
                  proyecciones=[dict(puntos=VERDE + [[22, 198]], color="green", sync="coinciden", dur=2.6,
                                     etiquetas=[dict(p=7, texto="$198", k=1.0, size=44)])])),
 dict(texto="¿Y si se rompe? Si baja de ciento veinticuatro con cincuenta, el conteo estaba mal: la caída no había terminado, y lo más probable es que siga bajando.",
      visual=dict(base, pre="si se rompe", titulo="BAJO $124,50: SE RECUENTA", marcas=ws("A", "B"),
                  niveles=[dict(precio=124.50, texto="invalidación · $124,50", color="warm", sync="baja")],
                  proyecciones=[dict(puntos=ROTO, color="warm", sync="baja", dur=1.8, etiquetas=[dict(p=2, texto="sigue bajando", pos="abajo", k=1.0)])])),
 dict(texto="Tres precios para vigilar: de ciento cuarenta y dos a ciento cuarenta y ocho, donde debería girar. Arriba de ciento setenta y uno con cincuenta, la C está en marcha. Y abajo de ciento veinticuatro con cincuenta, se invalida.",
      visual=dict(tipo="lista", pastilla="GUÁRDALO", titulo="3 PRECIOS PARA VIGILAR", items=[
          dict(texto="$142–148: zona de giro (B)", emoji="🔄", sync="cuarenta"),
          dict(texto="Más de $171,50: confirma la C", emoji="🚀", sync="arriba"),
          dict(texto="Menos de $124,50: se invalida", emoji="🛑", sync="abajo")])),
 dict(texto="Mi conclusión: hoy el patrón sigue vivo. Está en la B, dentro de su zona y lejos de la invalidación. Si supera ciento setenta y uno con cincuenta, apunta a ciento ochenta y cuatro, y después a ciento noventa y ocho.",
      visual=dict(tipo="versus", left=dict(label="SE CUMPLE", value="$184–198", color="green", sync="vivo"), right=dict(label="SE ROMPE", value="< $124,50", color="warm", sync="invalidación"))),
 dict(texto="Es un mapa, no una promesa, y no es recomendación de inversión. Guárdalo y vuelve en unas semanas. ¿Tú qué crees? Comenta SÍ o NO, y te traigo la parte tres.",
      visual=dict(tipo="outro", lines=["¿SE CUMPLE", "LA ONDA C?"], syncs=[None, "crees"], button="COMENTA SÍ O NO", button_sync="comenta")),
]
g = dict(ESM, titulo="Nvidia onda por onda: ¿se cumple Elliott? Objetivos y qué pasa si se rompe 📉📈",
  descripcion=("Análisis educativo con precios reales (Yahoo Finance). No es recomendación de inversión.\n\n"
   "📉 LA CAÍDA EN 5 ONDAS\n• 6 oct 2026: máximo de US$243,37.\n• Onda 1: hasta ~US$213 (−12%).\n• Onda 2: rebote a ~US$222.\n"
   "• Onda 3: 8 nov investigación interna, 12 nov renuncia de Jensen Huang → ~US$166 (−25%).\n• Onda 4: rebote a ~US$177.\n"
   "• Onda 5: 17 nov primeros resultados sin Huang → 20 nov US$124,50 (−49% desde el máximo).\n\n"
   "📈 LA CORRECCIÓN\n• 23 nov: vuelve Huang, +31,5% en un día (≈US$950.000 millones, récord). Onda A hasta US$171,50 = 38,2% de Fibonacci de la caída.\n"
   "• Onda B: suele retroceder 50–61,8% de la A → US$148–142,45. El 25 nov tocó US$141,17.\n\n👀 3 PRECIOS PARA VIGILAR: US$142–148 (zona de giro de la B) · más de US$171,50 (confirma la C) · menos de US$124,50 (se invalida).\n\n"
   "🎯 SI SE CUMPLE (onda C): objetivo 1 ≈ US$184–188 (50% de la caída ≈ US$183,94 y C = A ≈ US$188,17 si la B termina en US$141,17); objetivo 2 ≈ US$198 (61,8%).\n"
   "❌ SI SE ROMPE: por debajo de US$124,50 el conteo queda invalidado: la caída no había terminado y hay que recontar.\n\n"
   "La proyección del video es ilustrativa: Elliott marca zonas de precio, no fechas. Este es un conteo posible, no el único. ¿Qué son las ondas de Elliott? Mira el video anterior en el perfil. 👇"),
  hashtags="#nvidia #bolsa #trading #ondasdeelliott #fibonacci #inversion #WhiteHole #reels",
  fuentes=["https://www.sec.gov/Archives/edgar/data/0001045810/000104581026000082/nvda-20261111.htm",
           "https://www.nbcnews.com/business/markets/stocks-rebound-ai-tech-selloff-nvidia-rcna610833",
           "https://finance.yahoo.com/quote/NVDA/history"])
g1 = dict(g, titulo="Nvidia onda por onda, PARTE 1: ¿la caída respetó a Elliott? 📉", escenas=P1)
g2 = dict(g, titulo="Nvidia PARTE 2: ¿hasta dónde subiría si se cumple Elliott? 🎯", escenas=P2)
for name, gg in (("000c2_mercado_nvidia_parte1.json", g1), ("000c3_mercado_nvidia_parte2.json", g2)):
    json.dump(gg, open(os.path.join(R, "es/pendientes", name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(name, sum(len(x["texto"].split()) for x in gg["escenas"]), "palabras")
