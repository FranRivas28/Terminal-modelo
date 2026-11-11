"""Cartera simulada de seguimiento 1/3 SPY + 1/3 QQQ + 1/3 regla B, en CEDEARs.
- 11/11/2026 (pedido de Francisco): la terminal sigue la cartera del PDF de USD 1.000
  (pdf_tercios_1000.py -> cartera_tercios_1000usd.csv): cantidades enteras de CEDEARs, MU reemplazada por UNH
  (el CEDEAR de MU es muy caro para USD 1.000). La versión anterior (USD 10.000 con MU) quedó en cartera_tercios_10000_conMU.csv.
- Compra al cierre del 09/11/2026; se rebalancea en cada revisión trimestral.
Uso: python cartera_tercios.py   (después de pdf_tercios_1000.py)
Salida: cartera_tercios.csv
"""
from pathlib import Path
import pandas as pd

AQUI = Path(__file__).parent
CAPITAL = 1_000
b = pd.read_csv(AQUI / "seleccion_b_cedears.csv")
INICIO, REVISION = b.fecha.iloc[0], b.revision.iloc[0]
c = pd.read_csv(AQUI / "cartera_tercios_1000usd.csv")
nombres = {"SPY": "S&P 500 (SPY)", "QQQ": "Nasdaq-100 (QQQ)"}
d = pd.DataFrame({"inicio": INICIO, "revision": REVISION,
                  "parte": c.parte.replace({"Regla B": "B"}), "ticker": c.t,
                  "nombre": [nombres.get(t, e) for t, e in zip(c.t, c.e)],
                  "peso": (c.usd / CAPITAL).round(4), "monto_usd": c.usd.round(2),
                  "precio_entrada": c.px, "cedears": c.n, "ratio": c.ratio,
                  "precio_cedear": c.pc.round(2), "stop": c.stop, "capital": CAPITAL})
d.to_csv(AQUI / "cartera_tercios.csv", index=False)
print(d.to_string(index=False))
