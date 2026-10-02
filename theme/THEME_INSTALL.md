# EdgeAI Blogger Theme Installation

`EDGEAI_THEME.xml` is the production Blogger theme for EdgeAI.

## What it provides

- futuristic dark newsroom visual system
- sticky masthead and category navigation
- full-site search field
- animated latest-headline ticker
- three-story featured/hero area
- automatic fallback to newest posts when no `Featured` posts exist yet
- latest-intelligence news stream
- Trending Now / Popular Posts sidebar
- Browse The Radar / label navigation
- visible CONFIRMED / DEVELOPING / EARLY SIGNAL / RUMOUR status styling
- responsive tablet/mobile layouts
- article typography and source-link styling
- privacy/feed footer links

## One manual Blogger step is required

The Blogger v3 API used by EdgeAI can create and update posts, but the automation does not have a supported API endpoint for replacing the Blogger theme. Install this file once in Blogger:

1. Open the EdgeAI Blogger dashboard.
2. Go to **Theme**.
3. Use the theme menu to **Back up** the current theme first.
4. Choose **Restore / Upload** (wording can vary) and upload `EDGEAI_THEME.xml`.
5. Open the site and check desktop and mobile.

Do not paste repository secrets or API credentials into the theme. The theme is entirely public-facing.

## Canonical EdgeAI labels

The theme has first-class navigation/styling for these labels:

### Coverage
- `Breaking`
- `Models`
- `Tools`
- `Research`
- `Agents`
- `Open Source`
- `Creative AI`
- `Infrastructure`
- `Featured`

### Verification state
- `CONFIRMED`
- `DEVELOPING`
- `EARLY SIGNAL`
- `RUMOUR`

The hero requests `Featured` first and falls back to the three newest posts automatically.

## Homepage behaviour

The ticker requests the latest ten public Blogger posts through the site's own Blogger JSON feed. The hero requests the latest three `Featured` posts, with a fallback to ordinary recent posts. No additional paid service, JavaScript library, analytics product or API key is required.

## Design direction

EdgeAI deliberately uses a dark, restrained future-tech newsroom aesthetic rather than a neon gaming UI. Cyan identifies live/active intelligence, violet is secondary emphasis, green confirms, amber indicates developing coverage, and magenta/red is reserved for uncertain or urgent states.

## Rollback

If Blogger rejects the theme or the live rendering differs from preview, restore the backup made in step 3. The EdgeAI publishing/radar automation is independent of the visual theme, so a theme rollback does not affect ingestion or posting.
