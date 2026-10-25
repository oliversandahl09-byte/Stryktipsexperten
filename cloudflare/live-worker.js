// Liveresultat för Stryktipset, som Cloudflare Worker.
//
// Svenska Spels API tillåter inte anrop direkt från en annan webbplats (CORS),
// så webbsidan frågar den här i stället: /?omgang=4976 hämtar omgången från
// Svenska Spel och svarar i samma format som live.json (se stryktips/live.py).
// Svaren sparas en halv minut så att Svenska Spel inte får ett anrop per besökare.

const SOURCE = "https://api.spela.svenskaspel.se/draw/1/stryktipset/draws/";
const CACHE_SECONDS = 30;
const ENDED = new Set(["Ended", "EndedAfterExtratime", "EndedAfterPenalties", "Fulltime"]);
const HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": `public, max-age=${CACHE_SECONDS}`,
};

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
  const s = score(match);
  if (s && lage !== "ej startad") {
    out.mal = s;
    out.utfall = s[0] > s[1] ? "1" : s[0] < s[1] ? "2" : "X";
  }
  return out;
}

export function build(draw) {
  const matcher = {};
  for (const ev of draw.drawEvents || []) matcher[String(ev.eventNumber)] = matchState(ev);
  return { omgang: draw.drawNumber, hamtad: new Date().toISOString().slice(0, 19) + "+00:00", matcher };
}

const reply = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: HEADERS });

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") return new Response(null, { headers: HEADERS });
    const nr = new URL(request.url).searchParams.get("omgang") || "";
    if (!/^\d{1,6}$/.test(nr)) return reply({ fel: "ange ?omgang=<nummer>" }, 400);

    const cache = caches.default;
    const key = new Request(`https://live.cache/${nr}`);
    const cached = await cache.match(key);
    if (cached) return cached;

    const upstream = await fetch(SOURCE + nr, { headers: { "User-Agent": "stryktipsexperten-live" } });
    if (!upstream.ok) return reply({ fel: `Svenska Spel svarade ${upstream.status}` }, 502);
    const data = await upstream.json();
    const response = reply(build(data.draw || data));
    ctx.waitUntil(cache.put(key, response.clone()));
    return response;
  },
};
