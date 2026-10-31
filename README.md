# Trettonrätt

Hämtar veckans Stryktips-kupong från Svenska Spel och föreslår ett system
(spikar, halv- och helgarderingar) inom din budget.

**Veckans förslag:** [forslag/SENASTE.md](forslag/SENASTE.md)

## Hur den tänker

1. **Sannolikhet.** Odds görs om till sannolikheter för 1, X och 2, med
   spelbolagets marginal borträknad. Först används Pinnacle via The Odds API,
   annars snittet av europeiska spelbolag där, sedan Svenska Spels egna odds,
   startodds, Tio tidningars tips och sist strecken. Källan syns i kolumnen
   "Källa" i förslaget.
2. **Spelvärde.** Sannolikheten delas med svenska folkets streck. Ett värde över
   1 betyder att tecknet är understreckat: det går in oftare än folk tror, och
   när det gör det delar färre på potten.
3. **System.** För varje match väljs vilka tecken som täcks. Ett val får poäng
   för träffchans och för spelvärde, vägt med `--risk` (0 = bara träffchans,
   1 = bara spelvärde). Den kombination som ger högst poäng och ryms i
   `--rader` väljs.
4. **Backtest.** Gamla omgångar spelas om med samma regler, och insats och
   utdelning räknas med de verkliga utdelningarna för 10–13 rätt.

## Webbsidan

`webb/index.html` visar veckans omgång: mest troliga raden, sannolikheter, streck
och värde per match. Du väljer system (max antal rader, eller exakt antal halv-
och helgarderingar) och spelstil, och förslaget räknas om direkt i webbläsaren
med samma metod som `kupong.py`. Tryck på ett tecken för att låsa egna val, så
fylls resten av systemet i runt dem. Lägger du till ett tecken växer systemet
i stället för att andra garderingar plockas bort: 64 rader och en halvgardering
till blir 128 rader, en halv som blir hel ger ×1,5.

Under **R-system** finns färdiga reducerade system med samma garderingar och
garantier som Svenska Spels R-system, till exempel R 4-0-9 (12): 4 helgarderingar,
0 halvgarderingar, 9 rader och minst 12 rätt om alla spikar och garderingar sitter.
Varje system visas med garderingar, antal rader och pris, garanti och raderna själva.
Raderna är framräknade i förväg (lokal sökning för små delsystem, ternära Golaykoden
för R 11-0-729 och sammansättning av delsystem för resten) och kontrollerade mot sin
garanti; de ligger i `R_KODER` i `webb/index.html`. **Reducera fritt** räknar fram
ett eget R-system i webbläsaren för valfria garderingar och garanti 12, 11 eller 10
rätt. Chanserna för 10–13 rätt räknas på de reducerade raderna, och filen till
Svenska Spel innehåller bara de raderna.

Sidan visar också **inbördes möten** mellan lagen (senaste tio säsongerna, från
[football-data.co.uk](https://www.football-data.co.uk), ingen nyckel behövs).
Ett reglage styr hur mycket de ska väga in i sannolikheterna, från inget alls
till hälften. Hämtas med `python -m stryktips inbordes`.

Till höger visas **aktuella tabeller** för Premier League, Championship och League One,
räknade ur säsongens resultat hos football-data.co.uk. Lag som finns på
kupongen är markerade med matchnumret. Hämtas med `python -m stryktips tabell`.

**Liveresultat:** medan matcherna spelas hämtar `.github/workflows/live.yml`
ställningarna från Svenska Spel var tionde minut och publicerar om sidan.
Sidan visar ställningen per match, markerar om ditt system täcker den och
räknar hur många rätt du har just nu. Svenska Spels API går inte att anropa
direkt från webbsidan (CORS), därav omvägen via GitHub Actions.

Under liveresultaten visas **utdelningen**. Medan omgången pågår är det en
förväntad utdelning per rad för 10–13 rätt om ställningarna står sig (matcher
som inte har startat räknas med det mest troliga tecknet). Den räknas ur
omsättningen och svenska folkets streck: Svenska Spel delar ut 65 % av
omsättningen (40 % till 13 rätt, 15 % till 12, 12 % till 11 och 25 % till 10),
och antalet vinnare uppskattas som om varje spelad rad följde strecken. Det är
en grov prognos, ofta inom en faktor två för 13 rätt. När alla matcher är slut
och Svenska Spel har räknat klart visas den faktiska utdelningen och antalet
vinnare i stället. Båda delarna visar också vad ditt system skulle ge.

För ställningar varje minut finns en liten Cloudflare Worker i
`cloudflare/live-worker.js` som hämtar omgången från Svenska Spel åt sidan.
Lägg upp den i Cloudflare (Workers & Pages → Create → Worker, klistra in koden,
Deploy) och skriv dess adress i `LIVE_PROXY` i `webb/index.html`. Svarar den
inte används live.json som vanligt.

**Inloggning och sparade tips:** utan inloggning sparas dina val bara i
webbläsaren. Med ett gratis Supabase-projekt kan besökare logga in med en
länk till sin e-post, och då sparas tipset per omgång i databasen så att det
syns på alla enheter, tillsammans med de senaste omgångarnas tips.

1. Skapa ett projekt på [supabase.com](https://supabase.com).
2. Kör `supabase/tips.sql` under **SQL Editor**. Den skapar tabellen `tips`
   och ser till att varje användare bara kan läsa och ändra sina egna tips.
3. Under **Authentication → URL Configuration**: sätt Site URL till sidans
   adress och lägg till både den och `…/?spel=europatipset` som Redirect URLs.
4. Skriv projektets URL och anon-nyckel (**Project Settings → API**) i
   `SUPABASE_URL` och `SUPABASE_KEY` i `webb/index.html`. Anon-nyckeln är
   gjord för att ligga publikt; skyddet sitter i databasens regler.

Är de tomma visas ingen inloggning och sidan fungerar som förut.

Sidan publiceras med GitHub Pages av `.github/workflows/webb.yml`, varje gång
veckans förslag har skrivits. Slå på det under **Settings → Pages → Source:
GitHub Actions**. Lokalt: `python -m http.server` i repots rot och öppna
<http://localhost:8000/webb/>.

## Automatiskt varje vecka

GitHub Actions (`.github/workflows/veckovis.yml`) kör torsdag, fredag och
lördag förmiddag, sparar kupong, streck och odds under `data/raw/` och skriver
ett nytt förslag. På måndagar sparas helgens resultat. Svenska Spel visar inte
streck och odds för gamla omgångar särskilt länge, så den sparade datan blir
mer värd för varje vecka.

Du kan också köra den för hand under **Actions → Veckans stryktips → Run
workflow** och välja antal rader och risknivå.

För att bygga upp historik: **Actions → Hämta historik och backtesta**, välj
ett intervall av omgångsnummer (data finns ungefär från omgång 4267, januari
2013; startodds från ungefär 2021).

## Skarpare odds med The Odds API

1. Skaffa en gratis nyckel på <https://the-odds-api.com> (500 anrop i månaden).
2. Spara den i repot under **Settings → Secrets and variables → Actions → New
   repository secret** med namnet `ODDS_API_KEY`.

Varje hämtning kostar ett anrop per liga på kupongen, oftast 2–3, så
gratisnivån räcker gott. Utan nyckel används Svenska Spels odds som tidigare.
Oddsen sparas i `data/raw/marknad_<omgång>.json`, så med tiden kan backtestet
även köras på dem.

## Köra lokalt

Kräver Python 3.10 eller senare, inga andra paket.

```
python -m stryktips hamta                    # öppna omgångar + nya resultat
python -m stryktips forslag --rader 96       # förslag för nästa omgång
python -m stryktips historik 4850 4980       # hämta gamla omgångar
python -m stryktips backtest --rader 64 --svep
python -m unittest discover -s tests         # tester
```

## Bra att veta

- Svenska Spels API är inofficiellt och odokumenterat. Det kan ändras utan
  förvarning, och då behöver `stryktips/svenskaspel.py` justeras.
- Ligor som inte finns i `LEAGUES` i `stryktips/oddsapi.py` (och matcher vars
  lagnamn inte går att para ihop) får Svenska Spels odds.
- Ingen modell vinner säkert på tips. Spela för pengar du har råd att förlora.
