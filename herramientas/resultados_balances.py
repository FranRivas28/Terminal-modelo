"""Resultado de los balances que ya se presentaron: si superó lo esperado y cuánto se movió la acción.

    python resultados_balances.py [días]     # mira los últimos 28 días por defecto

Le pide a Finnhub el calendario de balances de los últimos días y se queda con los del S&P 500, los de las small caps
del universo (estudio/universo.csv) y los de las elegidas. Para cada uno que ya publicó:
  - resultado: ganancia por acción real contra la esperada (superó o no, y por cuánto);
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
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
BASE = AQUI.resolve().parent
SEG = BASE / "seguimiento"
SALIDA = SEG / "resultados_balances.csv"
DIAS = int(sys.argv[1]) if len(sys.argv) > 1 else 28
hoy = date.today()


def finnhub(ruta, **params):
    if os.environ.get("FINNHUB_API_KEY"):  # en el entorno de Claude la clave la pone el proxy
        params["token"] = os.environ["FINNHUB_API_KEY"]
    url = f"https://finnhub.io/api/v1/{ruta}?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def cierres(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t.replace('.', '-')}?range=3mo&interval=1d"
    for intento in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            r = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
            f = [datetime.fromtimestamp(s, timezone.utc).date().isoformat() for s in r["timestamp"]]
            return t, pd.Series(r["indicators"]["adjclose"][0]["adjclose"], index=f, dtype=float).dropna()
        except Exception:
            time.sleep(2 * (intento + 1))
    return t, pd.Series(dtype=float)


# ---------- a quiénes mirar ----------
d = json.loads((AQUI / "datos.json").read_text())
mercado = {}
if (BASE / "estudio" / "universo.csv").exists():
    mercado.update({t: "small" for t in pd.read_csv(BASE / "estudio" / "universo.csv").ticker})
if (BASE / "sp500" / "constituyentes.csv").exists():
    mercado.update({t.replace("-", "."): "sp" for t in pd.read_csv(BASE / "sp500" / "constituyentes.csv").Symbol})
mercado.update({x["t"]: "sp" for x in d.get("cedears", {}).get("top", [])})
mercado.update({x["t"]: "sp" for x in d["sp"]["top"]})
mercado.update({p["ticker"]: "small" for p in d["predicciones"]})

# probabilidad de superar (del calendario armado antes del balance) y movimiento típico (historial)
prob = {}
for nombre in ("proximos_balances.csv", "proximos_balances_small.csv"):
    if (SEG / nombre).exists():
        for f in pd.read_csv(SEG / nombre).itertuples():
            prob[(f.ticker, f.fecha)] = f.prob_superar
mov = {}
for nombre in ("eventos_balances.csv", "eventos_balances_small.csv"):
    ev = BASE / "sp500" / "balances" / nombre
    if ev.exists():
        e = pd.read_csv(ev)
        mov.update((100 * e.groupby("ticker").reaccion.apply(lambda s: s.abs().mean())).round(1).to_dict())

# ---------- calendario de Finnhub, de a una semana ----------
cal = []
a = hoy - timedelta(days=DIAS)
while a <= hoy:
    b = min(a + timedelta(days=6), hoy)
    cal += finnhub("calendar/earnings", **{"from": a.isoformat(), "to": b.isoformat()}).get("earningsCalendar", [])
    a = b + timedelta(days=1)
previos = pd.read_csv(SALIDA, dtype={"reaccion": float}) if SALIDA.exists() else pd.DataFrame()
listos = set(zip(previos[previos.reaccion.notna()].ticker, previos[previos.reaccion.notna()].fecha)) if len(previos) else set()
filas = [c for c in cal if c["symbol"] in mercado and c.get("epsActual") is not None and (c["symbol"], c["date"]) not in listos]
if not filas:
    print("No hay balances nuevos para resolver.")
    raise SystemExit

# ---------- precios ----------
with ThreadPoolExecutor(8) as ex:
    PX = dict(ex.map(cierres, sorted({c["symbol"] for c in filas} | {"SPY", "IWM"})))


def reaccion(s, f, hora):
    """Último cierre antes del balance y cierre del día en que el mercado reaccionó."""
    if s.empty:
        return None, None, None
    antes = s[s.index <= f] if hora == "después de cerrar" else s[s.index < f]
    despues = s[s.index >= f] if hora == "antes de abrir" else s[s.index > f]
    if antes.empty or despues.empty:
        return (antes.index[-1] if len(antes) else None), None, None
    return antes.index[-1], despues.index[0], despues.iloc[0] / antes.iloc[-1] - 1


nuevas = []
for c in filas:
    t, m = c["symbol"], mercado[c["symbol"]]
    hora = {"bmo": "antes de abrir", "amc": "después de cerrar"}.get(c.get("hour"), "")
    s, ref = PX.get(t, pd.Series(dtype=float)), ("IWM" if m == "small" else "SPY")
    d0, d1, r = reaccion(s, c["date"], hora)
    r_ref = (PX[ref][d1] / PX[ref][d0] - 1) if r is not None and d0 in PX[ref] and d1 in PX[ref] else None
    est, real = c.get("epsEstimate"), c.get("epsActual")
    nuevas.append({"ticker": t, "fecha": c["date"], "hora": hora, "mercado": m,
                   "prob_superar": prob.get((t, c["date"])), "mov_tipico_pct": mov.get(t),
                   "eps_estimado": est, "eps_real": real,
                   "supero": "" if est is None else ("sí" if real > est else "no"),
                   "sorpresa_pct": None if not est else round(100 * (real - est) / abs(est), 1),
                   "ventas_estimado": c.get("revenueEstimate"), "ventas_real": c.get("revenueActual"),
                   "dia_reaccion": d1 or "", "reaccion": None if r is None else round(r, 4),
                   "indice": ref, "reaccion_indice": None if r_ref is None else round(r_ref, 4),
                   "hasta_hoy": None if r is None else round(s.iloc[-1] / s[d0] - 1, 4),
                   "precio_hoy": None if s.empty else round(s.iloc[-1], 2), "actualizado": hoy.isoformat()})

out = pd.DataFrame(nuevas)
if len(previos):
    nuevos = set(zip(out.ticker, out.fecha))
    out = pd.concat([previos[[(t, f) not in nuevos for t, f in zip(previos.ticker, previos.fecha)]], out], ignore_index=True)
out = out.sort_values(["fecha", "ticker"])
out.to_csv(SALIDA, index=False)
espera = sorted(f["ticker"] for f in nuevas if f["reaccion"] is None)
print(f"{len(nuevas)} resueltos ahora · {len(out)} en total · {out.reaccion.notna().sum()} con reacción · "
      f"{len(espera)} esperando que el mercado reaccione (o sin precio)")
