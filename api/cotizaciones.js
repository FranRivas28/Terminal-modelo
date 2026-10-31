// Función de Vercel: precios en vivo desde Finnhub. La clave va en la variable FINNHUB_API_KEY del proyecto.
export default async function handler(req, res) {
  const key = process.env.FINNHUB_API_KEY;
  if (!key) return res.status(500).json({ error: "Falta FINNHUB_API_KEY" });
  const tickers = String(req.query.t || "").split(",").filter(t => /^[A-Z.\-]{1,10}$/.test(t)).slice(0, 30);
  const out = {};
  await Promise.all(tickers.map(async t => {
    try {
      const r = await fetch(`https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(t)}&token=${key}`);
      if (!r.ok) return;
      const q = await r.json();
      if (q.c) out[t] = { p: q.c, pc: q.pc, t: q.t };
    } catch (e) { /* una acción que falla no frena al resto */ }
  }));
  // Vercel guarda la respuesta 30 s: muchos visitantes no gastan el límite de 60 consultas por minuto de Finnhub.
  res.setHeader("Cache-Control", "s-maxage=30, stale-while-revalidate=60");
  res.status(200).json(out);
}
