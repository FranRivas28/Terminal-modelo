// Función de Vercel: precios cada 15 minutos (Yahoo) de la cartera 1/3 desde el día de la compra,
// para que el gráfico del Resumen se vea al día sin volver a armar la página. No necesita clave.
// Si Yahoo no responde, la página usa los precios que ya trae adentro.
export default async function handler(req, res) {
  const tickers = String(req.query.t || "").split(",").filter(t => /^[A-Z.\-]{1,10}$/.test(t)).slice(0, 20);
  const desde = /^\d{4}-\d{2}-\d{2}$/.test(String(req.query.desde || "")) ? String(req.query.desde) : null;
  const intervalo = ["15m", "30m", "1h"].includes(req.query.i) ? req.query.i : "15m";
  if (!tickers.length || !desde) return res.status(400).json({ error: "Faltan t o desde" });
  const p1 = Math.floor(Date.parse(desde + "T00:00:00Z") / 1000), p2 = Math.floor(Date.now() / 1000);
  const series = {};
  await Promise.all(tickers.map(async t => {
    try {
      const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(t.replace(".", "-"))}?period1=${p1}&period2=${p2}&interval=${intervalo}`,
        { headers: { "User-Agent": "Mozilla/5.0" } });
      if (!r.ok) return;
      const j = (await r.json()).chart.result[0], c = j.indicators.quote[0].close, m = {};
      j.timestamp.forEach((s, i) => { if (c[i] != null) m[s] = Math.round(c[i] * 1000) / 1000; });
      if (Object.keys(m).length) series[t] = m;
    } catch (e) { /* un activo que falla no frena al resto */ }
  }));
  const ts = [...new Set(Object.values(series).flatMap(m => Object.keys(m).map(Number)))].sort((a, b) => a - b);
  const cierres = {}; Object.entries(series).forEach(([t, m]) => { cierres[t] = ts.map(s => m[s] ?? null); });
  // Vercel guarda la respuesta 2 minutos: no se le pide a Yahoo en cada visita.
  res.setHeader("Cache-Control", "s-maxage=120, stale-while-revalidate=300");
  res.status(200).json({ intervalo, desde, ts, cierres });
}
