"""Junta los números del backtest, las predicciones y la regla "evitar" en dashboard/datos.json,
que es lo único que lee la página del dashboard (index.html)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
SEG = BASE / "seguimiento"

ops = pd.read_csv(SEG / "backtest_panel.csv", parse_dates=["fecha"])
ev = pd.read_csv(SEG / "backtest_evaluaciones.csv", parse_dates=["semana"])
pred = pd.read_csv(SEG / "predicciones.csv")
regla = pd.read_csv(SEG / "regla_seguimiento.csv")
resumen = pd.read_csv(SEG / "backtest_resumen.csv")

# Semana a semana: el modelo reparte en partes iguales entre las que pasan; sin candidatas queda en efectivo.
semanas = sorted(ev["semana"].unique())
mod = ops.groupby("fecha")["ret_real"].mean().reindex(semanas).fillna(0.0)
lista = ev.groupby("semana")["ret_real"].mean().reindex(semanas)
n_ops = ops.groupby("fecha").size().reindex(semanas).fillna(0).astype(int)
curva = (1 + mod).cumprod()
curva_lista = (1 + lista).cumprod()
dd = curva / curva.cummax() - 1

r = ops["ret_real"]
gan, per = r[r > 0], r[r <= 0]
por_ticker = ops.groupby("ticker")["ret_real"].agg(["sum", "count"]).query("count >= 2").sort_values("sum")
top5 = r.sort_values(ascending=False).head(5).sum() / r.sum()
sem_con = mod[n_ops > 0]

def fila(nombre):
    return resumen.loc[resumen["indicador"] == nombre].iloc[0]

ventaja = fila("Ventaja vs. la lista (misma semana)")
filtros = []
for _, f in resumen[resumen["indicador"].str.startswith("Filtro ")].iterrows():
    a, b = [float(x.strip().rstrip("%")) for x in f["valor"].split("vs")]
    filtros.append({"filtro": f["indicador"].split()[1].rstrip(":").capitalize().replace("Tecnico", "Técnico"), "pasan": a, "no_pasan": b})

datos = {
    "actualizado": str(pd.Timestamp.today().date()),
    "desde": str(semanas[0].date()), "hasta": str(semanas[-1].date()),
    "kpi": {
        "total": float(curva.iloc[-1] - 1), "total_lista": float(curva_lista.iloc[-1] - 1),
        "ventaja_sem": ventaja["valor"], "ventaja_margen": ventaja["margen_95"],
        "operaciones": int(len(r)), "ganadas": int(len(gan)), "perdidas": int(len(per)),
        "win": float(len(gan) / len(r)), "prom_gan": float(gan.mean()), "prom_per": float(per.mean()),
        "profit_factor": float(gan.sum() / -per.sum()), "esperanza": float(r.mean()),
        "max_dd": float(dd.min()), "semanas": len(semanas), "semanas_con": int((n_ops > 0).sum()),
        "stops": float(ops["toco_stop"].mean()),
    },
    "semanal": [{"f": str(s.date()), "m": round(float(mod[s]), 5), "l": round(float(lista[s]), 5),
                 "c": round(float(curva[s] - 1), 5), "cl": round(float(curva_lista[s] - 1), 5),
                 "dd": round(float(dd[s]), 5), "n": int(n_ops[s])} for s in semanas],
    "operaciones": [{"f": str(o.fecha.date()), "t": o.ticker, "s": round(o.score, 2), "r": round(o.ret_real, 4),
                     "stop": bool(o.toco_stop)} for o in ops.sort_values("fecha", ascending=False).itertuples()],
    "predicciones": pred.astype(object).where(pred.notna(), None).to_dict(orient="records"),
    "regla": regla.fillna("").to_dict(orient="records"),
    "filtros": filtros,
    "insights": {
        "mejor": [por_ticker.index[-1], float(por_ticker["sum"].iloc[-1]), int(por_ticker["count"].iloc[-1])],
        "peor": [por_ticker.index[0], float(por_ticker["sum"].iloc[0]), int(por_ticker["count"].iloc[0])],
        "mejor_sem": [str(sem_con.idxmax().date()), float(sem_con.max())],
        "peor_sem": [str(sem_con.idxmin().date()), float(sem_con.min())],
        "top5": float(top5), "rel_gp": float(per.min() / -gan.mean()),
        "rho": float(fila("Relación puntaje → retorno (correlación de rangos)")["valor"]),
    },
}

# ---------- Small caps: regla "evitar" de esta semana y señales probadas ----------
EST, SP = BASE / "estudio", BASE / "sp500"
al = pd.read_csv(SEG / "alertas.csv")
al = al[al["fecha"] == al["fecha"].max()]
motivos = {"Mucha cobertura": int((al["alerta_cobertura"] == "sí").sum()), "Salto de noticias": int((al["alerta_salto"] == "sí").sum()),
           "Ventas de directivos": int((al["alerta_ventas"] == "sí").sum())}
def razones(f):
    return ", ".join(n for n, c in [("cobertura", "alerta_cobertura"), ("salto", "alerta_salto"), ("ventas", "alerta_ventas")] if f[c] == "sí")
rs = pd.read_csv(EST / "regla_semanal.csv").dropna(subset=["diferencia_4s"])
sen = pd.read_csv(EST / "senales.csv")
datos["small"] = {
    "fecha": al["fecha"].max(), "evaluadas": int(len(al)), "evitar": int((al["evitar"] == "sí").sum()), "motivos": motivos,
    "lista_evitar": [{"t": f["ticker"], "m": razones(f)} for _, f in al[al["evitar"] == "sí"].iterrows()],
    "regla_hist": [{"f": f.fecha, "d": round(f.diferencia_4s, 5)} for f in rs.itertuples()],
    "senales": [{"s": f.senal, "tipo": f.tipo, "d": f.diferencia_1s, "lo": f.margen_bajo, "hi": f.margen_alto} for f in sen.itertuples()],
}

# ---------- S&P 500: elección de la semana, embudo y filtros ----------
sel = pd.read_csv(SP / "seleccion_sp500.csv")
evs = pd.read_csv(SP / "evaluacion_sp500.csv")
orden = ["sentimiento", "tecnico", "momentum", "ganancias", "graham", "pasa todo"]
top = sel[sel["top10"] == "sí"].sort_values("puntaje", ascending=False)
datos["sp"] = {
    "fecha": sel["fecha"].max(), "evaluadas": int(len(evs)), "pasan": int((evs["cae_en"] == "pasa todo").sum()),
    "embudo": [{"etapa": e, "n": int((evs["cae_en"] == e).sum())} for e in orden],
    "top": [{"t": f.ticker, "e": f.empresa, "sec": f.sector, "p": f.puntaje, "px": round(f.precio, 2), "piso": f.piso, "techo": f.techo,
             "rango": f.rango_mes_pct, "bal": f.balance if isinstance(f.balance, str) else "", "evitar": f.evitar,
             "motivos": f.motivos if isinstance(f.motivos, str) else "",
             "cedear": f.cedear_ratio if isinstance(f.cedear_ratio, str) else ""} for f in top.itertuples()],
    "con_cedear": int(sel["cedear_ratio"].notna().sum()),
    "filtros": pd.read_csv(SP / "terminal_filtros.csv").to_dict(orient="records"),
}

# ---------- Balances de las próximas dos semanas ----------
def proximos(nombre, prob):
    b = pd.read_csv(SEG / nombre)
    b = b[pd.to_datetime(b["fecha"]) <= pd.Timestamp(b["fecha"].min()) + pd.Timedelta(days=13)]
    return {"filas": b.fillna("").sort_values(["fecha", "prob_superar"], ascending=[True, False]).to_dict(orient="records"),
            "prob": pd.read_csv(SP / "balances" / prob).to_dict(orient="records")}
datos["balances"] = {"sp": proximos("proximos_balances.csv", "probabilidad_superar.csv"),
                     "small": proximos("proximos_balances_small.csv", "probabilidad_superar_small.csv"),
                     "aviso": pd.read_csv(SP / "aviso_balance_sp500.csv").to_dict(orient="records")}

def limpiar(x):  # NaN no es JSON válido: pasa a null
    if isinstance(x, dict): return {k: limpiar(v) for k, v in x.items()}
    if isinstance(x, list): return [limpiar(v) for v in x]
    if isinstance(x, float) and np.isnan(x): return None
    return x
datos = limpiar(datos)
precios = Path(__file__).parent / "precios.json"  # de bajar_precios.py
if precios.exists():
    datos["precios"] = json.loads(precios.read_text())
(Path(__file__).parent / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, default=str))
print(json.dumps(datos["kpi"], indent=1), datos["insights"])

# La página lleva los datos adentro, así funciona sola (Vercel o vista previa) sin pedir nada a ningún servidor.
plantilla = (Path(__file__).parent / "plantilla.html").read_text()
json_seguro = json.dumps(datos, ensure_ascii=False, default=str).replace("</", "<\\/")
pagina = plantilla.replace("/*DATOS*/", json_seguro)
(Path(__file__).parent / "vista_previa.html").write_text(pagina)  # para la vista previa en claude.ai
cabeza, cuerpo = pagina.split("</style>", 1)  # para Vercel: documento completo
(Path(__file__).parent / "index.html").write_text(
    '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    + cabeza + "body { margin: 0; }\n[hidden] { display: none !important; }\n</style>\n</head>\n<body>\n" + cuerpo + "\n</body>\n</html>\n")
