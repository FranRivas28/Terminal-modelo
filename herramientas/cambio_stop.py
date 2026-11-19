"""Cambio por stop en la parte B de la cartera 1/3 (regla del PDF: si una acción cierra debajo de su stop, se vende ese
CEDEAR y la plata entra en la siguiente de la regla B que tenga CEDEAR).
19/11/2026 (pedido de Francisco): sale UNH (stop 380,77; cotizaba ~344) y entra WDC, la siguiente de la regla B con CEDEAR
en el ranking del 09/11 (seleccion_b_2026-11-09_ampliado.csv).
Precio de venta y de compra: cotización del momento (Finnhub). La plata de la venta pasa entera a la nueva (en CEDEARs
enteros alcanza para N; lo que sobra, ~1 USD, se cuenta junto con ella para que el valor no salte).
Uso: python cambio_stop.py VENDE COMPRA      -> actualiza cartera_tercios.csv (respaldo en cartera_tercios_antes_cambio_*.csv)
Después: seleccion_b_extra.py y el rearmado del dashboard (bajar_precios.py → datos_dashboard.py).
"""
import json, math, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

AQUI = Path(__file__).parent; BASE = AQUI.parent
VENDE, COMPRA = sys.argv[1], sys.argv[2]


def cot(t):
    params = {"symbol": t}
    if os.environ.get("FINNHUB_API_KEY"):
        params["token"] = os.environ["FINNHUB_API_KEY"]
    q = json.loads(urllib.request.urlopen("https://finnhub.io/api/v1/quote?" + urllib.parse.urlencode(params), timeout=20).read())
    return float(q["c"]), int(q["t"])


ct = pd.read_csv(AQUI / "cartera_tercios.csv")
for col in ("desde", "hasta", "precio_venta", "ts_desde", "ts_hasta"):
    if col not in ct:
        ct[col] = None
byma = pd.read_csv(BASE / "sp500/cedears_byma_2026-09-16.csv").set_index("cedear")
k = ct.index[(ct.ticker == VENDE) & ct.hasta.isna()][0]
pv, ts = cot(VENDE); pc, _ = cot(COMPRA)
hoy = datetime.fromtimestamp(ts, timezone.utc).astimezone().date().isoformat()
rv = int(str(ct.ratio[k]).split(":")[0]); rc_txt = byma.ratio[COMPRA]; rc = int(str(rc_txt).split(":")[0])
plata = ct.cedears[k] * pv / rv
n = math.floor(plata / (pc / rc))
ct.loc[k, ["hasta", "precio_venta", "ts_hasta"]] = [hoy, round(pv, 2), ts]
nueva = {**ct.loc[k].to_dict(), "ticker": COMPRA, "nombre": byma.empresa_byma[COMPRA].title() if COMPRA != "WDC" else "Western Digital",
         "monto_usd": round(plata, 2), "precio_entrada": round(pc, 2), "cedears": n, "ratio": rc_txt, "precio_cedear": round(pc / rc, 2),
         "stop": None, "desde": hoy, "hasta": None, "precio_venta": None, "ts_desde": ts, "ts_hasta": None,
         "peso": round(plata / ct.capital.iloc[0], 4)}
ct = pd.concat([ct, pd.DataFrame([nueva])], ignore_index=True)
ct.to_csv(AQUI / "cartera_tercios.csv", index=False)
print(f"vende {ct.cedears[k]} {VENDE} a {pv:.2f} = USD {plata:.2f}; compra {n} CEDEARs de {COMPRA} a {pc:.2f} (ratio {rc_txt}), sobran USD {plata - n * pc / rc:.2f}")
