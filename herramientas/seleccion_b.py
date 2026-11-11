"""Selección trimestral con la REGLA B ("Magic Formula entre las de impulso"), en prueba desde el 11/11/2026.

Cómo elige:
  - Entre las acciones del S&P 500 que están en la mitad de arriba por suba de 12 meses (sin contar el último mes),
    se ordenan por la Magic Formula de Greenblatt (promedio del puesto en rendimiento de ganancias EBIT/EV y en
    retorno sobre el capital EBIT/(capital de trabajo + activo fijo)), con balances publicados a esa fecha.
  - Las 5 primeras forman la cartera. Peso, stop, rango a 3 meses y revisión: igual que la regla de impulso
    (ver seleccion_trimestral.py).
  - Se descartan las que tienen el activo fijo en cero en el balance (dato roto que infla el retorno sobre capital;
    el 9/11/2026 eso pasó con APA).
Prueba 2011-2026 (rotacion/mejoras_sharpe_sortino_calmar.pdf): Sharpe 0,83 (SPY 0,76), Sortino 1,20 (SPY 1,06),
Calmar 0,52 (SPY 0,41), peor caída −34%. Perdió contra SPY en 2023-2026. Se sigue en papel 2 trimestres.

Uso: python seleccion_b.py CARPETA_PRECIOS RANKING_B.csv
  RANKING_B.csv: candidatas ya ordenadas por la regla B (columnas t, mf_rank, imp_rank, ey, roc, pe), p. ej.
  seleccion_b_2026-11-09.csv (sale del motor de rotacion/t26_*.py con los balances de Finnhub).
Salida: seleccion_b_sp500.csv, seleccion_b_cedears.csv
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
BASE = AQUI.parent
DESCARTAR = {"APA": "activo fijo en cero en el balance (dato roto)"}
px = pd.read_csv(Path(sys.argv[1]) / "sp500.csv.gz", parse_dates=["fecha"]).drop_duplicates(["t", "fecha"])
rk = pd.read_csv(sys.argv[2])
W = {k: px.pivot(index="fecha", columns="t", values=k) for k in "hlcv"}
c = W["c"].ffill(limit=5)
hoy = c.index[-1]
cons = pd.read_csv(BASE / "sp500/constituyentes.csv").rename(columns={"Symbol": "ticker", "Security": "empresa", "GICS Sector": "sector"})
cons["ticker"] = cons.ticker.str.replace(".", "-", regex=False).map(lambda t: t.replace("-", ".") if t.replace("-", ".") in c.columns else t)
info = cons.set_index("ticker")
rango = pd.concat([W["h"] - W["l"], (W["h"] - c.shift()).abs(), (W["l"] - c.shift()).abs()]).groupby(level=0).max()
atr = rango.rolling(14).mean().iloc[-1]
monto = (c * W["v"]).rolling(60, min_periods=20).mean().iloc[-1]
mom12 = (c.shift(21) / c.shift(252) - 1).iloc[-1]
vol = np.log(c).diff().iloc[-60:].std()
ult = c.iloc[-1]
byma = pd.read_csv(BASE / "sp500/cedears_byma_2026-09-16.csv")
SIMB = {"BRKB": "BRK.B", "DISN": "DIS", "BA.C": "BAC", "TRVV": "TRV"}
byma["ticker"] = byma.cedear.map(lambda x: SIMB.get(x, x))
ratio = dict(zip(byma.ticker, byma.ratio)); cedear = dict(zip(byma.ticker, byma.cedear))
bal = pd.read_csv(BASE / "seguimiento/proximos_balances.csv")
bal = bal[pd.to_datetime(bal.fecha) >= hoy].sort_values("fecha").drop_duplicates("ticker").set_index("ticker").fecha
REVISION = (hoy + pd.DateOffset(months=3)).date().isoformat()
cand = [t for t in rk.t if t not in DESCARTAR and t in info.index and t in c.columns and pd.notna(atr.get(t))]
R = rk.set_index("t")


def elegir(universo, nombre):
    top = [t for t in cand if t in universo][:5]
    raiz = np.sqrt(monto[top])
    filas = []
    for k, t in enumerate(top):
        s3 = float(vol[t] * np.sqrt(63))
        filas.append({"fecha": hoy.date().isoformat(), "revision": REVISION, "puesto": k + 1, "grupo": "principal", "ticker": t,
                      "empresa": info.empresa.get(t, ""), "sector": info.sector.get(t, ""), "precio": round(float(ult[t]), 2),
                      "suba_12m": round(float(mom12[t]), 4), "peso": round(float(raiz[t] / raiz.sum()), 3),
                      "stop": round(float(ult[t] - 1.5 * atr[t]), 2), "stop_pct": round(float(-1.5 * atr[t] / ult[t]), 4),
                      "piso_3m": round(float(ult[t] * np.exp(-s3)), 2), "techo_3m": round(float(ult[t] * np.exp(s3)), 2),
                      "rango_3m_pct": round(s3 * 100, 1), "monto_diario_musd": round(float(monto[t]) / 1e6, 1),
                      "balance": bal.get(t, ""), "cedear": cedear.get(t, ""), "ratio": ratio.get(t, ""),
                      "mf_puesto": round(float(R.mf_rank[t]), 1), "rend_ganancias": round(float(R.ey[t]), 1),
                      "per": round(float(R.pe[t]), 1)})
    d = pd.DataFrame(filas)
    d.to_csv(AQUI / f"seleccion_b_{nombre}.csv", index=False)
    print(nombre); print(d[["puesto", "ticker", "empresa", "precio", "suba_12m", "peso", "stop_pct", "mf_puesto", "per", "cedear"]].to_string(index=False))


print("precios al", hoy.date(), "| descartadas:", DESCARTAR)
elegir(set(info.index), "sp500")
elegir(set(cedear), "cedears")
