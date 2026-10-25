// Liveresultat för Stryktipset, som Cloudflare Worker.
//
// Svenska Spels API tillåter inte anrop direkt från en annan webbplats (CORS),
// så webbsidan frågar den här i stället: /?omgang=4976 hämtar omgången från
// Svenska Spel och svarar i samma format som live.json (se stryktips/live.py).
// Lägg till &spel=europatipset för Europatipset.
// När alla matcher är slut hämtas också utdelningen för 10–13 rätt.
// Svaren sparas en halv minut så att Svenska Spel inte får ett anrop per besökare.

const SOURCE = "https://api.spela.svenskaspel.se/draw/1/";
const GAMES = ["stryktipset", "europatipset"];
const CACHE_SECONDS = 30;
const ENDED = new Set(["Ended", "EndedAfterExtratime", "EndedAfterPenalties", "Fulltime"]);
const HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": `public, max-age=${CACHE_SECONDS}`,
};

const num = v => (v === undefined || v === null || v === "" ? NaN : parseFloat(String(v).replace(/\s/g, "").replace(",", ".")));

function score(match) {
  const results = match.result || [];
  for (const kind of ["Current", "Fulltime"]) {
    for (const r of results) {
      const home = parseInt(r.home, 10), away = parseInt(r.away, 10);
      if (r.sportEventResultType === kind && !isNaN(home) && !isNaN(away)) return [home, away];
    }
  }
  return null;
}

export function matchState(event) {
  const match = event.match || {};
  const status = match.sportEventStatus || "NotStarted";
  let lage = "pågår";
  if (status === "NotStarted") lage = "ej startad";
  else if (ENDED.has(status)) lage = "slut";
  else if (status === "Postponed" || status === "Cancelled" || event.cancelled) lage = "inställd";
  else if (status === "Interrupted") lage = "avbruten";
  const out = { lage, status: match.status || "", start: match.matchStart };
  const f = event.svenskaFolket;
  if (f && [f.one, f.x, f.two].every(v => !isNaN(num(v)))) out.streck = { 1: num(f.one) / 100, X: num(f.x) / 100, 2: num(f.two) / 100 };
  const s = score(match);
  if (s && lage !== "ej startad") {
    out.mal = s;
    out.utfall = s[0] > s[1] ? "1" : s[0] < s[1] ? "2" : "X";
  }
  return out;
}

export function payouts(result) {
  const out = {};
  for (const item of (result && result.distribution) || []) {
    const m = String(item.name || item.description || "").match(/\d+/);
    const kr = num(item.amount);
    if (m && !isNaN(kr)) out[m[0]] = { kr, vinnare: item.winners };
  }
  return Object.values(out).some(v => v.kr || v.vinnare) ? out : null;
}

export const allEnded = draw =>
  (draw.drawEvents || []).length > 0 && draw.drawEvents.every(ev => ["slut", "inställd"].includes(matchState(ev).lage));

export function build(draw, result) {
  const matcher = {};
  for (const ev of draw.drawEvents || []) matcher[String(ev.eventNumber)] = matchState(ev);
  const out = { omgang: draw.drawNumber, hamtad: new Date().toISOString().slice(0, 19) + "+00:00", matcher };
  const sale = num(draw.currentNetSale), price = num(draw.rowPrice);
  if (sale) { out.omsattning = sale; out.radpris = price || 1; }
  const utdelning = payouts(result);
  if (utdelning) out.utdelning = utdelning;
  return out;
}

const reply = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: HEADERS });

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") return new Response(null, { headers: HEADERS });
    const params = new URL(request.url).searchParams;
    const nr = params.get("omgang") || "";
    const spel = params.get("spel") || "stryktipset";
    if (!/^\d{1,6}$/.test(nr)) return reply({ fel: "ange ?omgang=<nummer>" }, 400);
    if (!GAMES.includes(spel)) return reply({ fel: `okänt spel, välj ${GAMES.join(" eller ")}` }, 400);

    const cache = caches.default;
    const key = new Request(`https://live.cache/${spel}/${nr}`);
    const cached = await cache.match(key);
    if (cached) return cached;

    const upstream = await fetch(`${SOURCE}${spel}/draws/${nr}`, { headers: { "User-Agent": "stryktipsexperten-live" } });
    if (!upstream.ok) return reply({ fel: `Svenska Spel svarade ${upstream.status}` }, 502);
    const data = await upstream.json();
    const draw = data.draw || data;
    let result = null;
    if (allEnded(draw)) {
      // Resultatet publiceras en stund efter sista matchen, så ett fel här är väntat.
      try {
        const r = await fetch(`${SOURCE}${spel}/draws/${nr}/result`, { headers: { "User-Agent": "stryktipsexperten-live" } });
        if (r.ok) { const j = await r.json(); result = j.result || j; }
      } catch (e) {}
    }
    const response = reply(build(draw, result));
    ctx.waitUntil(cache.put(key, response.clone()));
    return response;
  },
};
