# Stryktipsexperten

Hämtar veckans Stryktips-kupong från Svenska Spel och föreslår ett system
(spikar, halv- och helgarderingar) inom din budget.

**Veckans förslag:** [forslag/SENASTE.md](forslag/SENASTE.md)

## Hur den tänker

1. **Sannolikhet.** Svenska Spels odds görs om till sannolikheter för 1, X och 2,
   med spelbolagets marginal borträknad. Saknas odds används startodds, sedan
   Tio tidningars tips och sist strecken.
2. **Spelvärde.** Sannolikheten delas med svenska folkets streck. Ett värde över
   1 betyder att tecknet är understreckat: det går in oftare än folk tror, och
   när det gör det delar färre på potten.
3. **System.** För varje match väljs vilka tecken som täcks. Ett val får poäng
   för träffchans och för spelvärde, vägt med `--risk` (0 = bara träffchans,
   1 = bara spelvärde). Den kombination som ger högst poäng och ryms i
   `--rader` väljs.
4. **Backtest.** Gamla omgångar spelas om med samma regler, och insats och
   utdelning räknas med de verkliga utdelningarna för 10–13 rätt.

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
- Svenska Spels egna odds har högre marginal än skarpa spelbolag. Nästa steg är
  att lägga till fler oddskällor (till exempel The Odds API) för bättre
  sannolikheter.
- Ingen modell vinner säkert på tips. Spela för pengar du har råd att förlora.
