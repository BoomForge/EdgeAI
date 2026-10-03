# EdgeAI newsroom image contract

- Homepage cards and hero modules must prefer the article's embedded `edge-article-hero` image before Blogger `media$thumbnail` metadata.
- Source-page placeholder, template, icon, avatar, badge and favicon URLs are not valid editorial imagery.
- Visual repair passes must replace an existing hero block when the stored image is stale, malformed or generic.
- If a source provides no usable image, use the EdgeAI fallback only as a final safety net; continue looking for a real article image first.
- Excerpts must omit hero captions and Evidence Trust card text.
- Ticker separators must be CSS borders/spacing only; do not use bullet glyphs or HTML entities that Blogger may serialise visibly.
