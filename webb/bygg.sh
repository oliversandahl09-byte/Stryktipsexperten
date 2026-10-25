#!/bin/sh
# Samlar webbsidan och dess data i _site/ för GitHub Pages.
# Stryktipset ligger i roten, Europatipset i _site/europatipset/.
set -e
mkdir -p _site/europatipset
cp webb/index.html _site/
cp forslag/senaste.json _site/
for f in inbordes tabeller; do
  if [ -f "forslag/$f.json" ]; then cp "forslag/$f.json" _site/; fi
done
for f in senaste inbordes tabeller; do
  if [ -f "forslag/europatipset/$f.json" ]; then cp "forslag/europatipset/$f.json" _site/europatipset/; fi
done
# Liveresultat skrivs bara medan matcherna spelas.
python -m stryktips live --ut _site/live.json || echo "Kunde inte hämta liveresultat"
SPEL=europatipset python -m stryktips live --ut _site/europatipset/live.json || echo "Kunde inte hämta liveresultat för Europatipset"
