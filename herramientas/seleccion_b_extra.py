"""Rango a 3 meses y stop de las acciones de la cartera 1/3 que NO están en la lista de la regla B:
UNH (entró en lugar de MU porque el CEDEAR de MU es muy caro; vendida por stop el 19/11/2026) y WDC (entró por UNH).
Pedido de Francisco 19/11/2026: que en la terminal tengan la misma información que las demás.
Mismo cálculo que seleccion_b.py, con precios de Yahoo hasta el día en que entró cada una:
stop = precio − 1,5 ATR de 14 días (si la cartera no lo tiene), rango 3 meses = ± volatilidad diaria de 60 días × √63 (escala log).
Magic Formula / suba 12 meses: del ranking del 09/11 (seleccion_b_2026-11-09_ampliado.csv).
Uso: python seleccion_b_extra.py   (después de cartera_tercios.py o cambio_stop.py)
Salida: seleccion_b_extra_cedears.csv (mismas columnas que seleccion_b_cedears.csv, grupo = "reemplazo");
        completa el stop de las nuevas en cartera_tercios.csv
"""
import json, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
b = pd.read_csv(AQUI / "seleccion_b_cedears.csv")
ter = pd.read_csv(AQUI / "cartera_tercios.csv")
rk = pd.read_csv(AQUI / f"seleccion_b_{b.fecha.iloc[0]}_ampliado.csv").set_index("t")
SECTOR = {"UNH": "Health Care", "WDC": "Information Technology"}


def ohlc(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=1y&interval=1d"
    r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    return pd.DataFrame({k: q[k] for k in ("high", "low", "close")}, index=pd.to_datetime(r["timestamp"], unit="s").normalize()).dropna()


filas = []
for k, r in ter[(ter.parte == "B") & ~ter.ticker.isin(b.ticker)].iterrows():
    t = r.ticker
    f0 = r.desde if isinstance(r.desde, str) else b.fecha.iloc[0]
    d = ohlc(t); d = d[d.index < f0] if isinstance(r.desde, str) else d[d.index <= f0]  # entró durante el día: hasta el cierre anterior
    c = d.close
    atr = pd.concat([d.high - d.low, (d.high - c.shift()).abs(), (d.low - c.shift()).abs()], axis=1).max(axis=1).rolling(14).mean().iloc[-1]
    s3 = float(np.log(c).diff().iloc[-60:].std() * np.sqrt(63))
    p = float(r.precio_entrada)
    stop = float(r.stop) if pd.notna(r.stop) else round(p - 1.5 * atr, 2)
    ter.loc[k, "stop"] = stop
    filas.append({"fecha": f0, "revision": b.revision.iloc[0], "puesto": int(rk.n[t]), "grupo": "reemplazo", "ticker": t,
                  "empresa": r.nombre, "sector": SECTOR.get(t, ""), "precio": p, "suba_12m": round(float(rk.imp[t]), 4),
                  "peso": round(float(r.peso) * 3, 3), "stop": stop, "stop_pct": round(stop / p - 1, 4),
                  "piso_3m": round(p * np.exp(-s3), 2), "techo_3m": round(p * np.exp(s3), 2), "rango_3m_pct": round(s3 * 100, 1),
                  "monto_diario_musd": round(float(rk.monto[t]), 1), "balance": "", "cedear": t, "ratio": r.ratio,
                  "mf_puesto": round(float(rk.mf[t]) * 100, 1), "rend_ganancias": "", "per": round(float(rk.pe[t]), 1)})
pd.DataFrame(filas, columns=b.columns).to_csv(AQUI / "seleccion_b_extra_cedears.csv", index=False)
ter.to_csv(AQUI / "cartera_tercios.csv", index=False)
print(pd.DataFrame(filas)[["ticker", "fecha", "precio", "stop", "piso_3m", "techo_3m", "mf_puesto", "per"]].to_string(index=False))
