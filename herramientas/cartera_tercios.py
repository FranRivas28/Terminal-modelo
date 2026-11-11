"""Cartera simulada de seguimiento (pedido de Francisco, 11/11/2026): un tercio SPY, un tercio QQQ y un tercio regla B.
- Capital: USD 10.000 el 09/11/2026 (mismo día que la selección B). La parte B usa la versión CEDEARs
  (seleccion_b_cedears.csv) para que todo se pueda comprar en BYMA, con los pesos de esa selección.
- Se rebalancea en cada revisión trimestral (vuelve a 1/3 cada parte y la parte B toma la selección nueva).
Uso: python cartera_tercios.py   (después de bajar_precios.py, que deja dashboard/precios.json)
Salida: cartera_tercios.csv
"""
import json
from pathlib import Path
import pandas as pd

AQUI = Path(__file__).parent
CAPITAL = 10_000
b = pd.read_csv(AQUI / "seleccion_b_cedears.csv")
INICIO, REVISION = b.fecha.iloc[0], b.revision.iloc[0]
px = json.loads((AQUI.parent / "dashboard" / "precios.json").read_text())
i = px["fechas"].index(INICIO)
filas = [{"parte": "SPY", "ticker": "SPY", "nombre": "S&P 500 (SPY)", "peso": 1 / 3},
         {"parte": "QQQ", "ticker": "QQQ", "nombre": "Nasdaq-100 (QQQ)", "peso": 1 / 3}]
filas += [{"parte": "B", "ticker": r.ticker, "nombre": r.empresa, "peso": r.peso / 3} for r in b.itertuples()]
d = pd.DataFrame(filas)
d["monto_usd"] = (d.peso * CAPITAL).round(2)
d["precio_entrada"] = [px["cierres"][t][i] for t in d.ticker]
d.insert(0, "inicio", INICIO); d.insert(1, "revision", REVISION)
d["peso"] = d.peso.round(4)
d.to_csv(AQUI / "cartera_tercios.csv", index=False)
print(d.to_string(index=False))
