"""Serie diaria "El mercado hoy" (español): Bitcoin + Nvidia con datos reales de Yahoo Finance.

Lunes: plan de la semana (pivotes semanales + medias móviles).
Martes: ¿se cumplió? + RSI.  Miércoles: ¿se cumplió? + MACD.  Jueves: ¿se cumplió? + cruce de medias.
Viernes: resultado de la semana.
Los niveles salen SIEMPRE de la semana anterior completa (pivotes clásicos), así que cualquier día
se pueden recalcular sin guardar estado.

Uso:  python scripts/gen_mercado_diario.py --datos DIR_CSV [--fecha AAAA-MM-DD] [--salida DIR]
      (si no pasas --datos, descarga con yfinance)
"""
import os, sys, json, argparse, datetime as dt
import pandas as pd
from num2words import num2words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ACTIVOS = [("BTC-USD", "BTC_USD", "Bitcoin", "BITCOIN", 100), ("NVDA", "NVDA", "Nvidia", "NVIDIA", 0.01)]


# ---------------------------------------------------------------- números en palabras
def palabras(n):
    s = num2words(int(n), lang="es")
    return s.replace("veintiuno mil", "veintiún mil").replace("uno mil", "un mil").replace("ciento mil", "cien mil")

def dinero_voz(v, paso):
    if paso >= 1:
        return palabras(round(v / paso) * paso) + " dólares"
    return palabras(round(v)) + " dólares"  # en voz, Nvidia al dólar entero (en pantalla va con centavos)

def dinero_txt(v, paso):
    if paso >= 1:
        return "$" + f"{round(v / paso) * paso:,.0f}".replace(",", ".")
    return "$" + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def pct_voz(p):
    p = abs(p)
    ent, dec = int(p), int(round((p - int(p)) * 10))
    if dec == 10: ent, dec = ent + 1, 0
    return palabras(ent) + (f" coma {palabras(dec)}" if dec else "") + " por ciento"

def pct_txt(p):
    return (f"{p:+.1f}%").replace(".", ",")


# ---------------------------------------------------------------- indicadores
def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def macd(c):
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    s = m.ewm(span=9, adjust=False).mean()
    return m, s, m - s


def cargar(datos, simbolo, nombre):
    if datos:
        df = pd.read_csv(os.path.join(datos, f"{nombre}_diario.csv"), index_col=0, parse_dates=True)
    else:
        import yfinance as yf
        df = yf.download(simbolo, period="2y", interval="1d", auto_adjust=False, progress=False)
        if hasattr(df.columns, "levels"): df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def analizar(df, hoy, paso):
    lunes = hoy - dt.timedelta(days=hoy.weekday())
    lunes_ant = lunes - dt.timedelta(days=7)
    df = df[df.index <= pd.Timestamp(hoy)]
    prev = df[(df.index >= pd.Timestamp(lunes_ant)) & (df.index < pd.Timestamp(lunes))]
    sem = df[df.index >= pd.Timestamp(lunes)]
    H, L, C = prev["High"].max(), prev["Low"].min(), prev["Close"].iloc[-1]
    P = (H + L + C) / 3
    niv = dict(P=P, R1=2 * P - L, S1=2 * P - H, R2=P + (H - L), S2=P - (H - L))
    c = df["Close"]
    ma20, ma50 = c.rolling(20).mean(), c.rolling(50).mean()
    r = rsi(c); m, s, h = macd(c)
    v = df.tail(40)
    idx = v.index
    r2 = lambda ser: [None if pd.isna(x) else round(float(x), 4) for x in ser.reindex(idx)]
    serie = [[f"{x.day} {MES[x.month - 1]}", round(float(y), 2)] for x, y in v["Close"].items()]
    precio = float(c.iloc[-1])
    out = dict(
        serie=serie, precio=precio, fecha_ult=c.index[-1], niv=niv, prev_cierre=float(C),
        ma20=r2(ma20), ma50=r2(ma50), rsi=r2(r), macd=r2(m), senal=r2(s), hist=r2(h),
        rsi_hoy=float(r.iloc[-1]), macd_hoy=float(m.iloc[-1]), senal_hoy=float(s.iloc[-1]),
        macd_ayer=float(m.iloc[-2]), senal_ayer=float(s.iloc[-2]),
        ma20_hoy=float(ma20.iloc[-1]), ma50_hoy=float(ma50.iloc[-1]),
        sem_max=float(sem["High"].max()) if len(sem) else None,
        sem_min=float(sem["Low"].min()) if len(sem) else None,
        cambio_sem=(precio / float(C) - 1) * 100,
        cambio_dia=(precio / float(c.iloc[-2]) - 1) * 100,
    )
    vals = [q[1] for q in serie] + [niv["R1"], niv["S1"]]
    lo, hi = min(vals), max(vals)
    out["ymin"], out["ymax"] = lo - (hi - lo) * 0.08, hi + (hi - lo) * 0.10
    return out


# ---------------------------------------------------------------- textos
def estado_rsi(x):
    if x >= 70: return "sobrecompra", "por encima de setenta: zona de sobrecompra. Subió muy rápido y suele frenar o corregir"
    if x <= 30: return "sobreventa", "por debajo de treinta: zona de sobreventa. Cayó muy rápido y suele rebotar"
    if x >= 55: return "fuerza", "por encima de cincuenta: los compradores mandan, pero sin exceso"
    if x <= 45: return "debilidad", "por debajo de cincuenta: los vendedores mandan, pero sin pánico"
    return "neutral", "cerca de cincuenta: ni compradores ni vendedores tienen el control"

def estado_macd(a):
    cruce_alc = a["macd_ayer"] <= a["senal_ayer"] and a["macd_hoy"] > a["senal_hoy"]
    cruce_baj = a["macd_ayer"] >= a["senal_ayer"] and a["macd_hoy"] < a["senal_hoy"]
    if cruce_alc: return "CRUCE AL ALZA", "la línea azul acaba de cruzar por encima de la naranja: un cruce al alza, señal de que el impulso cambia a favor de los compradores", "green"
    if cruce_baj: return "CRUCE A LA BAJA", "la línea azul acaba de cruzar por debajo de la naranja: un cruce a la baja, el impulso se pasa a los vendedores", "warm"
    if a["macd_hoy"] > a["senal_hoy"]: return "IMPULSO ALCISTA", "la línea azul va por encima de la naranja y las barras están en verde: el impulso sigue a favor de los compradores", "green"
    return "IMPULSO BAJISTA", "la línea azul va por debajo de la naranja y las barras están en rojo: el impulso sigue del lado de los vendedores", "warm"

def tendencia(a):
    if a["precio"] > a["ma50"][-1] if a["ma50"][-1] else False:
        return "por encima de su media de cincuenta días, o sea, en tendencia de subida"
    return "por debajo de su media de cincuenta días, o sea, en tendencia de bajada"

def veredicto(a, paso, final=False):
    n, mx, mn = a["niv"], a["sem_max"], a["sem_min"]
    if mx is None: return "sin datos", "todavía no hay velas de esta semana", "grey"
    tr, ts = mx >= n["R1"], mn <= n["S1"]
    if tr and ts: return "TOCÓ LOS DOS", f"tocó los dos niveles: subió hasta {dinero_voz(mx, paso)} y bajó hasta {dinero_voz(mn, paso)}. Semana de mucha volatilidad", "warm"
    if tr: return "ESCENARIO ALCISTA ✓", f"superó la resistencia: llegó hasta {dinero_voz(mx, paso)}. Se cumplió el escenario de subida", "green"
    if ts: return "ESCENARIO BAJISTA ✓", f"perdió el soporte: bajó hasta {dinero_voz(mn, paso)}. Se cumplió el escenario de bajada", "warm"
    if final: return "SEMANA DE RANGO", "no tocó ninguno de los dos niveles. Fue una semana de rango, sin romper ni para arriba ni para abajo", "grey"
    return "EN EL RANGO", "sigue atrapado entre el soporte y la resistencia. Ninguno de los dos escenarios se ha activado todavía", "grey"


def grafico(a, nombre, paso, **kw):
    v = dict(tipo="mercado", serie=a["serie"], ymin=a["ymin"], ymax=a["ymax"], estatico=True,
             fuente=f"Cierres diarios {nombre} · Yahoo Finance", fechas=[0, len(a["serie"]) - 1])
    v.update(kw)
    return v

def niveles(a, paso, sync_r=None, sync_s=None):
    n = a["niv"]
    return [dict(precio=round(n["R1"], 2), texto=f"resistencia {dinero_txt(n['R1'], paso)}", color="green", sync=sync_r),
            dict(precio=round(n["S1"], 2), texto=f"soporte {dinero_txt(n['S1'], paso)}", color="warm", sync=sync_s)]


def escenas_activo(dia, a, nombre, NOMBRE, paso, primero):
    n = a["niv"]; esc = []
    precio_v, precio_t = dinero_voz(a["precio"], paso), dinero_txt(a["precio"], paso)
    if dia == 0:  # lunes: plan
        esc.append(dict(texto=f"{nombre}: está en {precio_v}, {tendencia(a)}." + (" La línea naranja es la media de veinte días y la gris la de cincuenta." if primero else ""),
                        visual=grafico(a, NOMBRE, paso, pre=f"{NOMBRE} · ahora", titulo=precio_t, estatico=False, vel=0.8,
                                       lineas=[dict(valores=a["ma20"], color="warm", texto="media 20", dy=-26),
                                               dict(valores=a["ma50"], color="grey", texto="media 50", dy=26)])))
        esc.append(dict(texto=f"El plan de la semana: resistencia en {dinero_voz(n['R1'], paso)}. Si la supera, el siguiente nivel es {dinero_voz(n['R2'], paso)}. "
                              f"Soporte en {dinero_voz(n['S1'], paso)}. Si lo pierde, puede buscar {dinero_voz(n['S2'], paso)}.",
                        visual=grafico(a, NOMBRE, paso, pre=f"{NOMBRE} · plan de la semana", titulo="2 PRECIOS CLAVE", precio_cabeza=False,
                                       niveles=niveles(a, paso, "resistencia", "soporte"))))
    elif dia in (1, 2, 3):  # seguimiento
        ver_t, ver_v, ver_c = veredicto(a, paso)
        esc.append(dict(texto=f"{nombre}: el lunes marcamos la resistencia en {dinero_voz(n['R1'], paso)} y el soporte en {dinero_voz(n['S1'], paso)}. Hoy está en {precio_v}, y {ver_v}.",
                        visual=grafico(a, NOMBRE, paso, pre=f"{NOMBRE} · ¿se cumplió?", titulo=ver_t, precio_cabeza=True,
                                       niveles=niveles(a, paso, "resistencia", "soporte"))))
        if dia == 1:
            est, frase = estado_rsi(a["rsi_hoy"])
            intro = "El RSI mide qué tan rápido ha subido o bajado el precio, de cero a cien. " if primero else ""
            esc.append(dict(texto=f"{intro}El RSI de {nombre} está en {palabras(round(a['rsi_hoy']))}, {frase}.",
                            visual=grafico(a, NOMBRE, paso, pre=f"{NOMBRE} · RSI", titulo=f"RSI {a['rsi_hoy']:.0f}: {est.upper()}", estatico=False, vel=0.8, precio_cabeza=False,
                                           indicador=dict(tipo="rsi", valores=a["rsi"], texto="RSI (14)"))))
        elif dia == 2:
            tit, frase, c = estado_macd(a)
            intro = "El MACD compara dos medias del precio, una rápida y una lenta: muestra hacia dónde va el impulso. " if primero else ""
            esc.append(dict(texto=f"{intro}En {nombre}, {frase}.",
                            visual=grafico(a, NOMBRE, paso, pre=f"{NOMBRE} · MACD", titulo=tit, estatico=False, vel=0.8, precio_cabeza=False,
                                           indicador=dict(tipo="macd", macd=a["macd"], senal=a["senal"], hist=a["hist"], texto="MACD (12, 26, 9)"))))
        else:
            arriba = a["ma20_hoy"] > a["ma50_hoy"]
            intro = "Las medias móviles suavizan el precio. Cuando la rápida, de veinte días, está encima de la lenta, de cincuenta, la tendencia de fondo es de subida. " if primero else ""
            frase = ("la media de veinte va por encima de la de cincuenta: el fondo sigue alcista" if arriba
                     else "la media de veinte va por debajo de la de cincuenta: el fondo sigue bajista")
            esc.append(dict(texto=f"{intro}En {nombre}, {frase}.",
                            visual=grafico(a, NOMBRE, paso, pre=f"{NOMBRE} · medias móviles", titulo="FONDO ALCISTA" if arriba else "FONDO BAJISTA", estatico=False, vel=0.8, precio_cabeza=False,
                                           lineas=[dict(valores=a["ma20"], color="warm", texto="media 20", dy=-26),
                                                   dict(valores=a["ma50"], color="grey", texto="media 50", dy=26)])))
    else:  # viernes: resultado
        ver_t, ver_v, ver_c = veredicto(a, paso, final=True)
        esc.append(dict(texto=f"{nombre}: en la semana va {'subiendo' if a['cambio_sem'] >= 0 else 'bajando'} un {pct_voz(a['cambio_sem'])}. El plan decía resistencia en {dinero_voz(n['R1'], paso)} y soporte en {dinero_voz(n['S1'], paso)}. Resultado: {ver_v}.",
                        visual=grafico(a, NOMBRE, paso, pre=f"{NOMBRE} · resultado de la semana", titulo=f"{ver_t} · {pct_txt(a['cambio_sem'])}", precio_cabeza=True,
                                       niveles=niveles(a, paso, "resistencia", "soporte"))))
    return esc


def generar(datos, hoy):
    dia = hoy.weekday()
    if dia > 4: return None
    A = {}
    for sim, nom, nombre, NOMBRE, paso in ACTIVOS:
        A[nombre] = (analizar(cargar(datos, sim, nom), hoy, paso), nombre, NOMBRE, paso)
    fecha_v = f"{DIA[dia]} {palabras(hoy.day)} de {MES_LARGO[hoy.month - 1]}"
    fecha_t = f"{DIA[dia].upper()} {hoy.day} {MES[hoy.month - 1].upper()}"
    b = A["Bitcoin"][0]
    if dia == 0:
        hook = dict(texto=f"Plan de la semana para Bitcoin y Nvidia: los precios exactos que voy a vigilar, y qué pasa si se rompen.",
                    visual=grafico(b, "BITCOIN", 100, pre=f"EL MERCADO HOY · {fecha_t}", titulo="PLAN DE LA SEMANA", estatico=False, vel=0.9, precio_cabeza=False))
        titulo = f"Plan de la semana: Bitcoin y Nvidia ({hoy.day} {MES[hoy.month - 1]}) 📈"
    elif dia == 4:
        hook = dict(texto=f"Viernes de resultados: ¿se cumplió el plan de la semana en Bitcoin y Nvidia? Vamos a ver qué acertó y qué no.",
                    visual=grafico(b, "BITCOIN", 100, pre=f"EL MERCADO HOY · {fecha_t}", titulo="¿SE CUMPLIÓ EL PLAN?", estatico=False, vel=0.9, precio_cabeza=False))
        titulo = f"¿Se cumplió el plan? Bitcoin y Nvidia, resultado de la semana 🎯"
    else:
        ind = ["", "el RSI", "el MACD", "las medias móviles"][dia]
        hook = dict(texto=f"Bitcoin y Nvidia, {fecha_v}: ¿se está cumpliendo el plan del lunes? Y hoy te explico {ind} con el gráfico real.",
                    visual=grafico(b, "BITCOIN", 100, pre=f"EL MERCADO HOY · {fecha_t}", titulo="¿SE ESTÁ CUMPLIENDO?", estatico=False, vel=0.9, precio_cabeza=False))
        titulo = f"Bitcoin y Nvidia hoy: ¿se cumple el plan? + {ind.replace('el ', '').replace('las ', '').upper() if dia < 3 else 'medias móviles'} 📊"
    esc = [hook]
    for k, nombre in enumerate(("Bitcoin", "Nvidia")):
        a, nombre, NOMBRE, paso = A[nombre]
        esc += escenas_activo(dia, a, nombre, NOMBRE, paso, primero=(k == 0))
    cierre = {0: "Mañana te digo si se está cumpliendo. Recuerda: esto es educativo, no es recomendación de inversión. ¿Tú qué crees, sube o baja esta semana? Comenta.",
              4: "El lunes, plan nuevo. Recuerda: esto es educativo, no es recomendación de inversión. ¿Qué otra acción quieres que analice? Comenta.",
              }.get(dia, "Mañana seguimos. Esto es educativo, no es recomendación de inversión. ¿Qué acción quieres que analice? Comenta.")
    boton = {0: "¿SUBE O BAJA?", 4: "¿QUÉ ANALIZO?"}.get(dia, "¿QUÉ ANALIZO?")
    esc.append(dict(texto=cierre, visual=dict(tipo="outro", lines=["EDUCATIVO,", "NO ES", "RECOMENDACIÓN"], syncs=[None, None, None], button=boton, button_sync="comenta")))
    nv, nn = A["Bitcoin"][0]["niv"], A["Nvidia"][0]["niv"]
    desc = (f"Serie diaria «El mercado hoy» con precios reales (Yahoo Finance). Contenido educativo, no es recomendación de inversión.\n\n"
            f"Niveles de la semana (pivotes clásicos de la semana anterior):\n"
            f"• Bitcoin: resistencia {dinero_txt(nv['R1'], 100)} · soporte {dinero_txt(nv['S1'], 100)} · siguientes {dinero_txt(nv['R2'], 100)} / {dinero_txt(nv['S2'], 100)}\n"
            f"• Nvidia: resistencia {dinero_txt(nn['R1'], 0.01)} · soporte {dinero_txt(nn['S1'], 0.01)} · siguientes {dinero_txt(nn['R2'], 0.01)} / {dinero_txt(nn['S2'], 0.01)}")
    return dict(idioma="es", velocidad=0.95, kokoro=dict(voz="em_alex", lang="es", velocidad=1.05),
                serie="El mercado hoy", titulo=titulo, descripcion=desc,
                hashtags="#bitcoin #nvidia #trading #bolsa #analisistecnico #criptomonedas #WhiteHole #reels",
                fuentes=["https://finance.yahoo.com/quote/BTC-USD/", "https://finance.yahoo.com/quote/NVDA/"], escenas=esc)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos"); ap.add_argument("--fecha")
    ap.add_argument("--salida", default=os.path.join(ROOT, "guiones", "es", "pendientes"))
    a = ap.parse_args()
    hoy = dt.date.fromisoformat(a.fecha) if a.fecha else (dt.datetime.utcnow() - dt.timedelta(hours=5)).date()
    g = generar(a.datos, hoy)
    if not g: print("Fin de semana: no hay video de mercado."); sys.exit(0)
    os.makedirs(a.salida, exist_ok=True)
    out = os.path.join(a.salida, f"0000_mercado_{hoy.isoformat()}.json")
    json.dump(g, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", out, "|", g["titulo"])
