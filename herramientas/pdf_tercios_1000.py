"""PDF de la cartera 1/3 (SPY, QQQ, regla B) armada con USD 1.000 en CEDEARs (pedido de Francisco, 11/11/2026).
Cambio pedido: MU se reemplaza por UNH (la siguiente de la regla B con CEDEAR) porque cada CEDEAR de MU es muy caro.
Uso: python pdf_tercios_1000.py   -> cartera_tercios_1000usd.html (+ PDF con rotacion/t26_pdf.js)
"""
import json, math
from pathlib import Path
import pandas as pd

AQUI = Path(__file__).parent; BASE = AQUI.parent
CAPITAL = 1000
px = json.loads((BASE / "dashboard/precios.json").read_text())
i0 = px["fechas"].index("2026-11-09")
b = pd.read_csv(AQUI / "seleccion_b_cedears.csv").set_index("ticker")
rk = pd.read_csv(AQUI / "seleccion_b_2026-11-09.csv").set_index("t")
byma = pd.read_csv(BASE / "sp500/cedears_byma_2026-09-16.csv").set_index("cedear")
ratio = lambda t: int(str(byma.ratio[t]).split(":")[0])
B = ["SNDK", "CVS", "HPQ", "DELL", "UNH"]  # sin MU
monto = {t: (b.monto_diario_musd[t] if t in b.index else rk.monto[t]) for t in B}
precio = {t: (b.precio[t] if t in b.index else round(rk.precio[t], 2)) for t in B}
stop = {t: (b.stop[t] if t in b.index else round(rk.stop[t], 2)) for t in B}
empresa = {"SNDK": "Sandisk", "CVS": "CVS Health", "HPQ": "HP Inc.", "DELL": "Dell Technologies", "UNH": "UnitedHealth Group",
           "SPY": "S&P 500 (ETF)", "QQQ": "Nasdaq-100 (ETF)"}
raiz = {t: math.sqrt(monto[t]) for t in B}; sr = sum(raiz.values())
obj = {"SPY": CAPITAL / 3, "QQQ": CAPITAL / 3, **{t: CAPITAL / 3 * raiz[t] / sr for t in B}}
precio.update({"SPY": px["cierres"]["SPY"][i0], "QQQ": px["cierres"]["QQQ"][i0]})
pc = {t: precio[t] / ratio(t) for t in obj}  # precio aprox. de 1 CEDEAR en USD
cant = {t: int(obj[t] // pc[t]) for t in obj}
caja = CAPITAL - sum(cant[t] * pc[t] for t in obj)
while True:  # completa unidades donde más falta, sin pasarse del capital
    falta = sorted(((obj[t] - cant[t] * pc[t]) / obj[t], t) for t in obj if pc[t] <= caja)
    if not falta or falta[-1][0] <= 0: break
    t = falta[-1][1]; cant[t] += 1; caja -= pc[t]
filas = [{"t": t, "e": empresa[t], "parte": "SPY" if t == "SPY" else "QQQ" if t == "QQQ" else "Regla B", "ratio": byma.ratio[t],
          "pc": pc[t], "n": cant[t], "usd": cant[t] * pc[t], "obj": obj[t], "px": precio[t], "stop": stop.get(t)} for t in obj]
inv = sum(f["usd"] for f in filas)
pd.DataFrame(filas).to_csv(AQUI / "cartera_tercios_1000usd.csv", index=False)
COL = {"SPY": "#8c8578", "QQQ": "#9b6fd6", "SNDK": "#2f86c9", "CVS": "#5cb8ff", "HPQ": "#1f5f94", "DELL": "#7cc4f5", "UNH": "#0f3f66"}
n_ = lambda x, d=0: f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
# dona
a = -math.pi / 2; arcs = ""; R0, r0, cx = 95, 58, 100
for f in filas:
    da = f["usd"] / inv * 2 * math.pi; a1 = a + da; big = 1 if da > math.pi else 0
    P = lambda r, t: f"{cx + r * math.cos(t):.2f} {cx + r * math.sin(t):.2f}"
    arcs += f'<path d="M{P(R0, a)} A{R0} {R0} 0 {big} 1 {P(R0, a1)} L{P(r0, a1)} A{r0} {r0} 0 {big} 0 {P(r0, a)}Z" fill="{COL[f["t"]]}" stroke="#fff" stroke-width="2"/>'
    a = a1
parte = lambda k: sum(f["usd"] for f in filas if f["parte"] == k) / inv * 100
ley = "".join(f'<li><i style="background:{COL[f["t"]]}"></i><b>{f["t"]}</b> {n_(f["usd"] / inv * 100, 1)}%</li>' for f in filas)
tabla = "".join(f'<tr><td><span class="pt {"b" if f["parte"] == "Regla B" else ""}">{f["parte"]}</span></td><td><b>{f["t"]}</b><div class="s">{f["e"]}</div></td><td class="r">{f["ratio"]}</td>'
                f'<td class="r">{n_(f["pc"], 2)}</td><td class="r"><b>{f["n"]}</b></td><td class="r">{n_(f["usd"], 2)}</td><td class="r">{n_(f["usd"] / inv * 100, 1)}%</td>'
                f'<td class="r">{n_(f["stop"], 2) + " <span class=s>(" + n_((f["stop"] / f["px"] - 1) * 100, 0) + "%)</span>" if f["stop"] else "—"}</td></tr>' for f in filas)
html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Cartera 1/3 · USD 1.000</title><style>
@page {{ size: A4; margin: 14mm 13mm; }}
body {{ font: 10.5pt/1.45 "Helvetica Neue", Arial, sans-serif; color: #1d1b18; margin: 0; }}
h1 {{ font-size: 20pt; margin: 0 0 2px; }} h2 {{ font-size: 12.5pt; margin: 18px 0 6px; border-bottom: 2px solid #1d1b18; padding-bottom: 3px; }}
.sub {{ color: #6b665e; font-size: 9.5pt; }} .s {{ color: #6b665e; font-size: 8.5pt; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 12px 0; }}
.k {{ border: 1px solid #ddd8cf; padding: 8px 10px; }} .k .l {{ font-size: 8pt; color: #6b665e; text-transform: uppercase; letter-spacing: .05em; }} .k .v {{ font-size: 15pt; font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }} th {{ text-align: left; font-size: 8pt; color: #6b665e; text-transform: uppercase; border-bottom: 1px solid #1d1b18; padding: 4px 5px; }}
td {{ padding: 5px; border-bottom: 1px solid #ebe7df; vertical-align: top; }} .r {{ text-align: right; }} tfoot td {{ font-weight: 700; border-top: 1px solid #1d1b18; }}
.pt {{ font-size: 8pt; border: 1px solid #8c8578; padding: 0 4px; }} .pt.b {{ border-color: #2f86c9; color: #2f86c9; }}
.dona {{ display: flex; gap: 22px; align-items: center; }} .dona svg {{ width: 170px; }}
.dona ul {{ list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(2, auto); gap: 4px 22px; }} .dona li i {{ display: inline-block; width: 10px; height: 10px; margin-right: 6px; }}
ul.p li {{ margin: 3px 0; }} .nota {{ background: #f5f2ec; padding: 8px 10px; font-size: 9.5pt; margin-top: 8px; }}
footer {{ margin-top: 18px; font-size: 8pt; color: #6b665e; border-top: 1px solid #ddd8cf; padding-top: 6px; }}
</style></head><body>
<h1>Cartera 1/3 · USD 1.000</h1>
<div class="sub">Un tercio SPY, un tercio QQQ, un tercio regla B · todo en CEDEARs · precios del 09/11/2026 · próxima revisión 09/02/2027</div>
<div class="kpis"><div class="k"><div class="l">Capital</div><div class="v">USD {n_(CAPITAL)}</div></div>
<div class="k"><div class="l">Invertido</div><div class="v">USD {n_(inv, 0)}</div><div class="s">quedan USD {n_(CAPITAL - inv, 0)} sin invertir</div></div>
<div class="k"><div class="l">Reparto</div><div class="v" style="font-size:12pt">{n_(parte("SPY"), 0)} / {n_(parte("QQQ"), 0)} / {n_(parte("Regla B"), 0)}</div><div class="s">SPY / QQQ / regla B (%)</div></div>
<div class="k"><div class="l">CEDEARs</div><div class="v">{sum(cant.values())}</div><div class="s">en 7 especies</div></div></div>
<h2>Qué comprar</h2>
<table><thead><tr><th>Parte</th><th>CEDEAR</th><th class="r">Ratio</th><th class="r">1 CEDEAR (USD)</th><th class="r">Cantidad</th><th class="r">Monto USD</th><th class="r">% cartera</th><th class="r">Stop (acción, USD)</th></tr></thead>
<tbody>{tabla}</tbody><tfoot><tr><td colspan="4">Total</td><td class="r">{sum(cant.values())}</td><td class="r">{n_(inv, 2)}</td><td class="r">100%</td><td></td></tr></tfoot></table>
<div class="s" style="margin-top:4px">Precio de 1 CEDEAR = precio de la acción en dólares ÷ ratio (aproximado: en BYMA cotiza en dólares MEP y puede diferir un poco). El stop es el precio de la acción original en EE.UU.</div>
<h2>Cómo queda repartida</h2>
<div class="dona"><svg viewBox="0 0 200 200">{arcs}<text x="100" y="96" text-anchor="middle" font-size="13" fill="#6b665e">USD</text><text x="100" y="116" text-anchor="middle" font-size="17" font-weight="700">{n_(inv, 0)}</text></svg><ul>{ley}</ul></div>
<h2>Por qué estas</h2>
<ul class="p">
<li><b>SPY y QQQ</b> son la base: el mercado de EE.UU. entero y las 100 grandes del Nasdaq (muy cargado de tecnología).</li>
<li><b>Regla B</b>: entre las acciones del S&amp;P 500 que más subieron en 12 meses, las más baratas y rentables según la Magic Formula. Peso dentro de la parte B: más a las más operadas.</li>
<li><b>Cambio pedido: MU afuera, entra UNH.</b> Cada CEDEAR de MU cuesta unos USD 147 (ratio 5:1): con USD 333 para la parte B no se puede repartir bien. UNH es la siguiente de la regla B que tiene CEDEAR (cada uno ~USD 12).</li>
</ul>
<div class="nota">En la prueba 2011-2026 (13 arranques, rebalanceo cada 3 meses), esta mezcla hizo de cada 100 → 1.127 (SPY 756, QQQ 1.363), con la mejor relación ganancia/riesgo de todas (Sharpe 0,87; SPY 0,75) y peor caída −32%. En el peor arranque terminó en 882, arriba de SPY. Gana menos que QQQ solo si siguen mandando las tecnológicas grandes.</div>
<h2>Qué hacer después</h2>
<ul class="p">
<li><b>Stops (solo parte B):</b> si una acción cierra debajo de su stop, se vende ese CEDEAR y la plata entra en la siguiente de la regla B con CEDEAR (se ve en la terminal). SPY y QQQ no tienen stop.</li>
<li><b>Cada 3 meses (09/02/2027):</b> se vuelve a dejar cada parte en un tercio y la parte B se cambia por la selección nueva.</li>
<li><b>Costos:</b> comprar cuesta ~0,7% (comisión + derechos + IVA), unos USD 7; vender, lo mismo.</li>
</ul>
<h2>Riesgos</h2>
<ul class="p">
<li>La parte B es una regla en prueba: perdió contra SPY en 2023-2026. Se sigue en papel al menos 2 trimestres.</li>
<li>Con USD 1.000, comisiones mínimas del broker pueden pesar más que el 0,7% estimado. Conviene revisar el mínimo por operación.</li>
<li>Los CEDEARs se mueven también con el dólar MEP/CCL; el resultado en dólares depende de la acción original.</li>
</ul>
<footer>Herramienta de investigación para seguimiento en papel. No es asesoramiento ni recomendación de compra. Precios de Yahoo Finance; ratios de BYMA (lista del 16/09/2026).</footer>
</body></html>"""
(AQUI / "cartera_tercios_1000usd.html").write_text(html)
print(pd.DataFrame(filas)[["t", "n", "pc", "usd", "obj", "stop"]].round(2).to_string(index=False), "\ninvertido", round(inv, 2))
