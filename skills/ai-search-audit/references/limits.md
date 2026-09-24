# What citable cannot check

Read this before explaining a result. Mention only the limits that apply to the site being audited.

1. **No JavaScript rendering.** Sites that build their pages in the browser and serve thin HTML will look empty or near empty. If page word counts are tiny or titles are missing on a site the user says has content, this is the likely cause. Many AI crawlers also do not run JavaScript, so this finding matters in its own right.
2. **Read-only.** citable audits. It never changes the site.
3. **Public pages only.** Anything behind a login is not crawled.
4. **One site per run.** Run it twice to compare two sites.
5. **Generic-anchor detection is English only.** Spanish anchors such as "haga clic" or "leer más" are not flagged yet.
6. **No soft-404 detection.** A page that returns HTTP 200 with an error message is treated as a success.
7. **Broken-link probing stops at 50 targets.** Large sites are sampled, not exhausted.
8. **The orphan-page check is limited by the crawl.** It compares the sitemap with the links found on the pages crawled. With a small page budget on a large site it overstates orphans. Re-run with more pages before treating a high orphan count as real.
9. **It does not measure citations.** It checks whether a site can be read and understood by AI crawlers. Whether ChatGPT, Claude or Perplexity actually cite the site is a separate measurement.
