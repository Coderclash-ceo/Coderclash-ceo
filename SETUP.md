# Setup

1. Extract this ZIP and copy EVERYTHING (including hidden `.github`) into your
   cloned `Coderclash-ceo` folder. Replace the old README.md and assets.
2. Preview: open README.md in VS Code, press Ctrl+Shift+V.
3. Edit `config/profile.json` (rows, radar values), then:
       pip install pillow
       python scripts/generate-assets.py
4. Photo dot-map (like the reference): save a clear photo as `assets/portrait.jpg`,
   run step 3 again. Without a photo you get a dot-matrix "KM" monogram.
5. Live stats: python scripts/generate-stats.py
   (set GITHUB_TOKEN env var to also get contributions + streaks)
6. Add NutriLink links: search "TODO" in README.md.
7. Push:
       git add .
       git commit -m "Rebuild GitHub profile"
       git push origin main

Repo must be public and named exactly `Coderclash-ceo`.
The workflow refreshes the stats cards daily (Settings > Actions must be enabled).
