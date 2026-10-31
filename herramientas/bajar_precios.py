"""Baja 6 meses de cierres diarios (Yahoo) de todas las acciones que aparecen en el dashboard -> precios.json.
Correr después de datos_dashboard.py y antes de volver a armarlo."""
import json
from pathlib import Path

import yfinance as yf

AQUI = Path(__file__).parent
d = json.loads((AQUI / "datos.json").read_text())
tickers = sorted(set([x["t"] for x in d["sp"]["top"]] + [p["ticker"] for p in d["predicciones"]]
                     + [e["t"] for e in d["small"]["lista_evitar"]] + [b["ticker"] for b in d["balances"]["sp"]["filas"]]
                     + [o["t"] for o in d["operaciones"][:30]] + ["SPY", "IWM"]))
px = yf.download([t.replace(".", "-") for t in tickers], period="6mo", interval="1d", auto_adjust=True, progress=False, threads=True)["Close"]
out = {"fechas": [str(f.date()) for f in px.index], "cierres": {}}
for t in tickers:
    s = px.get(t.replace(".", "-"))
    if s is not None and s.notna().sum() > 20:
        out["cierres"][t] = [None if v != v else round(float(v), 2) for v in s]
(AQUI / "precios.json").write_text(json.dumps(out))
print(len(out["cierres"]), "de", len(tickers), "con precios;", out["fechas"][-1])
