#!/bin/sh
# Samlar webbsidan och dess data i _site/ för GitHub Pages.
set -e
mkdir -p _site
cp webb/index.html _site/
cp forslag/senaste.json _site/
for f in inbordes tabeller; do
  if [ -f "forslag/$f.json" ]; then cp "forslag/$f.json" _site/; fi
done
# Liveresultat skrivs bara medan matcherna spelas.
python -m stryktips live --ut _site/live.json || echo "Kunde inte hämta liveresultat"
