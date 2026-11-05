"""Resultado de los balances que ya se presentaron: si superó lo esperado y cuánto se movió la acción.

Toma los balances del calendario (seguimiento/proximos_balances[_small].csv) y los de las elegidas que ya tienen fecha
pasada, le pide a Finnhub el resultado (EPS real vs. estimado) y a Yahoo los cierres, y calcula:
  - reacción: del último cierre antes del balance al cierre del primer día que el mercado lo pudo operar
    (antes de abrir: ese mismo día; después de cerrar: el día siguiente; sin hora: toma los dos días);
  - lo mismo para el índice (SPY o IWM), para ver si se movió por el balance o por el mercado;
  - hasta hoy: del cierre previo al balance al último cierre.
Va acumulando en seguimiento/resultados_balances.csv (un balance no se pierde aunque salga del calendario).

Correr después de datos_dashboard.py (lee datos.json) y antes de volver a armarlo:
    datos_dashboard.py → bajar_precios.py → resultados_balances.py → datos_dashboard.py
Necesita la clave de Finnhub en la variable FINNHUB_API_KEY (o el entorno que ya la inyecta).
"""
import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
SEG = AQUI.resolve().parent / "seguimiento"
SALIDA = SEG / "resultados_balances.csv"
hoy = date.today().isoformat()


def finnhub(ruta, **params):
    if os.environ.get("FINNHUB_API_KEY"):  # en el entorno de Claude la clave la pone el proxy
        params["token"] = os.environ["FINNHUB_API_KEY"]
    url = f"https://finnhub.io/api/v1/{ruta}?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def cierres(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t.replace('.', '-')}?range=3mo&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
        f = [datetime.fromtimestamp(s, timezone.utc).date().isoformat() for s in r["timestamp"]]
        return t, pd.Series(r["indicators"]["adjclose"][0]["adjclose"], index=f, dtype=float).dropna()
    except Exception:
        return t, pd.Series(dtype=float)


# ---------- qué balances mirar ----------
filas = []
for nombre, mercado in (("proximos_balances.csv", "sp"), ("proximos_balances_small.csv", "small")):
    if (SEG / nombre).exists():
        b = pd.read_csv(SEG / nombre).fillna("")
        for f in b[b["fecha"] <= hoy].itertuples():
            filas.append({"ticker": f.ticker, "fecha": f.fecha, "hora": f.hora, "mercado": mercado,
                          "prob_superar": f.prob_superar, "mov_tipico_pct": f.movimiento_tipico_pct})
d = json.loads((AQUI / "datos.json").read_text())
eleg = ([(p["ticker"], p.get("balance", ""), "small") for p in d["predicciones"]]
        + [(x["t"], x.get("bal", ""), "sp") for x in d["sp"]["top"]]
        + [(x["t"], x.get("bal", ""), "sp") for x in d.get("cedears", {}).get("top", [])])
ya = {(f["ticker"], f["fecha"]) for f in filas}
for t, f, m in eleg:
    if f and f <= hoy and (t, f) not in ya:
        filas.append({"ticker": t, "fecha": f, "hora": "", "mercado": m, "prob_superar": None, "mov_tipico_pct": None})
        ya.add((t, f))
previos = pd.read_csv(SALIDA).fillna("") if SALIDA.exists() else pd.DataFrame()
if len(previos):  # los que ya tienen reacción completa no se vuelven a calcular
    listos = {(r.ticker, r.fecha) for r in previos.itertuples() if r.reaccion != ""}
    filas = [f for f in filas if (f["ticker"], f["fecha"]) not in listos]
if not filas:
    print("No hay balances nuevos para resolver.")
    raise SystemExit

# ---------- resultado según Finnhub ----------
desde = min(f["fecha"] for f in filas)
cal = {}
a = date.fromisoformat(desde)
while a.isoformat() <= hoy:  # de a una semana, el calendario completo es grande
    b = min(a + timedelta(days=6), date.today())
    for c in finnhub("calendar/earnings", **{"from": a.isoformat(), "to": b.isoformat()}).get("earningsCalendar", []):
        cal[(c["symbol"], c["date"])] = c
    a = b + timedelta(days=1)


def buscar(t, f):  # mismo día, o hasta 3 días de diferencia si Finnhub corrió la fecha
    for k in (0, 1, -1, 2, -2, 3, -3):
        c = cal.get((t, (date.fromisoformat(f) + timedelta(days=k)).isoformat()))
        if c:
            return c
    return None


# ---------- precios ----------
with ThreadPoolExecutor(8) as ex:
    PX = dict(ex.map(cierres, sorted({f["ticker"] for f in filas} | {"SPY", "IWM"})))


def reaccion(s, f, hora):
    """Cierre antes del balance y cierre del día en que el mercado reaccionó."""
    if s.empty:
        return None, None, None
    antes = s[s.index < f] if hora != "después de cerrar" else s[s.index <= f]
    despues = s[s.index >= f] if hora == "antes de abrir" else s[s.index > f]
    if antes.empty or despues.empty:
        return (antes.index[-1] if len(antes) else None), None, None
    return antes.index[-1], despues.index[0], despues.iloc[0] / antes.iloc[-1] - 1


nuevas = []
for f in filas:
    c = buscar(f["ticker"], f["fecha"])
    if not c or c.get("epsActual") is None:
        continue  # todavía no publicó o Finnhub no lo tiene
    hora = f["hora"] or {"bmo": "antes de abrir", "amc": "después de cerrar"}.get(c.get("hour"), "")
    s, ref = PX.get(f["ticker"], pd.Series(dtype=float)), ("IWM" if f["mercado"] == "small" else "SPY")
    d0, d1, r = reaccion(s, c["date"], hora)
    r_ref = (PX[ref][d1] / PX[ref][d0] - 1) if r is not None and d0 in PX[ref] and d1 in PX[ref] else None
    est, real = c.get("epsEstimate"), c.get("epsActual")
    nuevas.append({**f, "fecha": c["date"], "hora": hora, "eps_estimado": est, "eps_real": real,
                   "supero": "" if est is None else ("sí" if real > est else "no"),
                   "sorpresa_pct": None if not est else round(100 * (real - est) / abs(est), 1),
                   "ventas_estimado": c.get("revenueEstimate"), "ventas_real": c.get("revenueActual"),
                   "dia_reaccion": d1 or "", "reaccion": None if r is None else round(r, 4),
                   "indice": ref, "reaccion_indice": None if r_ref is None else round(r_ref, 4),
                   "hasta_hoy": None if d0 is None or s.empty else round(s.iloc[-1] / s[d0] - 1, 4),
                   "precio_hoy": None if s.empty else round(s.iloc[-1], 2), "actualizado": hoy})

out = pd.DataFrame(nuevas)
if len(previos):
    out = pd.concat([previos[~previos.set_index(["ticker", "fecha"]).index.isin(
        out.set_index(["ticker", "fecha"]).index if len(out) else [])], out], ignore_index=True)
out.sort_values(["fecha", "ticker"]).to_csv(SALIDA, index=False)
listos = out["reaccion"].replace("", None).notna().sum() if len(out) else 0
print(f"{len(nuevas)} resueltos ahora · {len(out)} en total · {listos} con reacción · esperando que el mercado reaccione o sin precio:",
      sorted({f['ticker'] for f in nuevas if f['reaccion'] is None}))
