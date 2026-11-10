"""Selección trimestral con la regla nueva (impulso de 12 meses), aprobada por Francisco el 10/11/2026.

S&P 500 y CEDEARs:
  - Entre las acciones que hoy están en el S&P 500 (para CEDEARs: las que además tienen CEDEAR en BYMA), se ordenan
    por cuánto subieron en los últimos 12 meses sin contar el último mes.
  - Las 5 primeras son las PRINCIPALES (la regla probada). Las 6 a 10 son las SIGUIENTES (para seguir, más indicadores).
  - Peso sugerido: proporcional a la raíz del monto operado por día (más plata en las más grandes), dentro de cada grupo.
  - Stop: precio − 1,5 × ATR(14). Se revisa cada 3 meses: la que cerró bajo su stop se vende y entra la siguiente.
  - Rango a 3 meses (63 ruedas): ±1 desvío con la volatilidad de los últimos 60 días. No es una predicción de suba:
    es cuánto se puede mover (2 de cada 3 veces debería quedar adentro).

Uso: python seleccion_trimestral.py CARPETA_PRECIOS   (sp500.csv.gz de rotacion/bajar_largo.py: fecha,t,o,h,l,c,v)
Salida: seleccion_sp500.csv, seleccion_cedears.csv
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
BASE = AQUI.parent
px = pd.read_csv(Path(sys.argv[1]) / "sp500.csv.gz", parse_dates=["fecha"]).drop_duplicates(["t", "fecha"])
W = {k: px.pivot(index="fecha", columns="t", values=k) for k in "hlcv"}
c = W["c"].ffill(limit=5)
hoy = c.index[-1]
cons = pd.read_csv(BASE / "sp500/constituyentes.csv").rename(columns={"Symbol": "ticker", "Security": "empresa", "GICS Sector": "sector"})
cons["ticker"] = cons.ticker.str.replace(".", "-", regex=False).map(lambda t: t.replace("-", ".") if t.replace("-", ".") in c.columns else t)
miembros = [t for t in cons.ticker if t in c.columns]
rango = pd.concat([W["h"] - W["l"], (W["h"] - c.shift()).abs(), (W["l"] - c.shift()).abs()]).groupby(level=0).max()
atr = rango.rolling(14).mean().iloc[-1]
monto = (c * W["v"]).rolling(60, min_periods=20).mean().iloc[-1]
mom12 = (c.shift(21) / c.shift(252) - 1).iloc[-1]
vol = np.log(c).diff().iloc[-60:].std()
ult = c.iloc[-1]
ok = (ult >= 2) & (monto >= 1e6) & atr.notna() & mom12.notna()
byma = pd.read_csv(BASE / "sp500/cedears_byma_2026-09-16.csv")
SIMB = {"BRKB": "BRK.B", "DISN": "DIS", "BA.C": "BAC", "TRVV": "TRV"}
byma["ticker"] = byma.cedear.map(lambda x: SIMB.get(x, x))
ratio = dict(zip(byma.ticker, byma.ratio)); cedear = dict(zip(byma.ticker, byma.cedear))
bal = pd.read_csv(BASE / "seguimiento/proximos_balances.csv")
bal = bal[pd.to_datetime(bal.fecha) >= hoy].sort_values("fecha").drop_duplicates("ticker").set_index("ticker").fecha
info = cons.set_index("ticker")
REVISION = (hoy + pd.DateOffset(months=3)).date().isoformat()


def elegir(universo, nombre):
    u = [t for t in universo if ok.get(t, False)]
    orden = mom12[u].sort_values(ascending=False)
    top = orden.head(10).index.tolist()
    filas = []
    for k, t in enumerate(top):
        grupo = "principal" if k < 5 else "siguiente"
        g = top[:5] if k < 5 else top[5:]
        raiz = np.sqrt(monto[g]); peso = float(raiz[t] / raiz.sum())
        s3 = float(vol[t] * np.sqrt(63))
        filas.append({"fecha": hoy.date().isoformat(), "revision": REVISION, "puesto": k + 1, "grupo": grupo, "ticker": t,
                      "empresa": info.empresa.get(t, ""), "sector": info.sector.get(t, ""), "precio": round(float(ult[t]), 2),
                      "suba_12m": round(float(mom12[t]), 4), "peso": round(peso, 3), "stop": round(float(ult[t] - 1.5 * atr[t]), 2),
                      "stop_pct": round(float(-1.5 * atr[t] / ult[t]), 4), "piso_3m": round(float(ult[t] * np.exp(-s3)), 2),
                      "techo_3m": round(float(ult[t] * np.exp(s3)), 2), "rango_3m_pct": round(s3 * 100, 1),
                      "monto_diario_musd": round(float(monto[t]) / 1e6, 1), "balance": bal.get(t, ""),
                      "cedear": cedear.get(t, ""), "ratio": ratio.get(t, "")})
    d = pd.DataFrame(filas)
    d.to_csv(AQUI / f"seleccion_{nombre}.csv", index=False)
    print(nombre, f"({len(u)} posibles)"); print(d[["puesto", "grupo", "ticker", "empresa", "precio", "suba_12m", "peso", "stop", "piso_3m", "techo_3m", "cedear"]].to_string(index=False))


print("precios al", hoy.date())
elegir(miembros, "sp500")
elegir([t for t in miembros if t in cedear], "cedears")
