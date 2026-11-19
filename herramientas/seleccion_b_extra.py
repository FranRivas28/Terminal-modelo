"""Rango a 3 meses y stop de las acciones de la cartera 1/3 que NO están en la lista de la regla B
(hoy: UNH, que entró en lugar de MU porque el CEDEAR de MU es muy caro). Pedido de Francisco 19/11/2026:
que en la terminal tengan la misma información que las demás (rango, stop, Magic Formula).
Mismo cálculo que seleccion_b.py: stop = el del ranking (precio − 1,5 ATR de 14 días), rango 3 meses = ± volatilidad
diaria de 60 días × √63 (escala log), peso según la cartera 1/3.
Uso: python seleccion_b_extra.py   (después de cartera_tercios.py y bajar_precios.py)
Salida: seleccion_b_extra_cedears.csv (mismas columnas que seleccion_b_cedears.csv, grupo = "reemplazo")
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).parent; BASE = AQUI.parent
b = pd.read_csv(AQUI / "seleccion_b_cedears.csv")
ter = pd.read_csv(AQUI / "cartera_tercios.csv")
rk = pd.read_csv(AQUI / f"seleccion_b_{b.fecha.iloc[0]}.csv").set_index("t")
px = json.loads((BASE / "dashboard/precios.json").read_text())
SECTOR = {"UNH": "Health Care"}
filas = []
for r in ter[(ter.parte == "B") & ~ter.ticker.isin(b.ticker)].itertuples():
    t, f0 = r.ticker, b.fecha.iloc[0]
    s = pd.Series(px["cierres"][t], index=pd.to_datetime(px["fechas"])).dropna()
    s = s[s.index <= f0]
    s3 = float(np.log(s).diff().iloc[-60:].std() * np.sqrt(63))
    p = float(r.precio_entrada)
    filas.append({"fecha": f0, "revision": b.revision.iloc[0], "puesto": int(rk.n[t]), "grupo": "reemplazo", "ticker": t,
                  "empresa": r.nombre, "sector": SECTOR.get(t, ""), "precio": p, "suba_12m": round(float(rk.imp12[t]) / 100, 4),
                  "peso": round(float(r.peso) * 3, 3), "stop": float(r.stop), "stop_pct": round(float(r.stop) / p - 1, 4),
                  "piso_3m": round(p * np.exp(-s3), 2), "techo_3m": round(p * np.exp(s3), 2), "rango_3m_pct": round(s3 * 100, 1),
                  "monto_diario_musd": round(float(rk.monto[t]), 1), "balance": "", "cedear": t, "ratio": r.ratio,
                  "mf_puesto": round(float(rk.mf_rank[t]), 1), "rend_ganancias": round(float(rk.ey[t]), 1), "per": round(float(rk.pe[t]), 1)})
d = pd.DataFrame(filas, columns=b.columns)
d.to_csv(AQUI / "seleccion_b_extra_cedears.csv", index=False)
print(d.T.to_string())
