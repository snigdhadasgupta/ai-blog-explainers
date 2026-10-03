# AI Blog Explainers

**A daily, automatically-updated static site that turns the AI announcements that matter into one-page visual explainers — plus ready-to-share social cards.**

🔗 Live: https://snigdhadasgupta.github.io/ai-blog-explainers/
📰 RSS: https://snigdhadasgupta.github.io/ai-blog-explainers/feed.xml

## What it is

Every day, the site scans the official blogs below for new posts relevant to **knowledge workers, product managers, and client-facing engineers** — practical enterprise, product, agentic-AI, and AI-governance content (it skips soft "AI for good", human-interest, and general infra-security posts).

For each new post it automatically:

1. **Builds a visual explainer** — a self-contained HTML page in the house style with a TL;DR and at least one infographic.
2. **Generates a shareable card** — a 1200×630 social image with a punchy hook and a short summary, in the source's accent color.
3. **Registers it** on the homepage, the RSS feed, and the *Most Sharable* gallery.
4. **Publishes** to GitHub Pages.

## Sources

Badges use the blog/brand name, not the parent company:

| Badge | Blog |
|---|---|
| Claude | https://claude.com/blog |
| OpenAI | https://openai.com/news/ |
| Microsoft 365 | https://www.microsoft.com/en-us/microsoft-365/blog/ |
| Google Workspace | https://workspace.google.com/blog/ |
| Microsoft Security | https://www.microsoft.com/en-us/security/blog/ (AI/agent posts only) |

## Structure

- `index.html` — landing page: latest explainers with source/topic filters, and a **Most Sharable** section.
- `share.html` — the full **Most Sharable** gallery: quote cards with Image / Link / Copy / X / LinkedIn actions.
- `explainers/<slug>.html` — one self-contained explainer per post. Each sets its `og:image` to its own share card, so link previews show the card.
- `share-cards/<slug>.png` — the social card for each post.
- `share-posts.js` — the `window.__POSTS__` data (slug, source, category, date, hook, body) that both Most Sharable views read.
- `feed.xml` — RSS feed. `favicon.svg` / `logo-mark.svg` — the prism logo.

## Sharing on LinkedIn / X

Because each explainer's `og:image` is its card, sharing an explainer **link** shows the card as the preview (and clicking it opens the explainer). For a full in-feed image post, use the **Image** button to download the PNG and attach it. LinkedIn caches previews per URL — to refresh an already-shared link, run it through the [LinkedIn Post Inspector](https://www.linkedin.com/post-inspector/) or add a throwaway `?v=1` query.

## How it's built

Pure static — **no build step**. A daily scheduled task (`daily-cluad-blog`) runs the whole pipeline: fetch → explainer → card → register → publish. The card generator and fonts live **outside** the deployed site (in `../_cardgen/`, not part of this repo).

### Add a post manually

1. Add `explainers/<slug>.html` and point its `og:image`/`twitter:image` to `share-cards/<slug>.png`.
2. Add an object to the `POSTS` array near the bottom of `index.html`.
3. Add an `<item>` to `feed.xml`.
4. For a card: add `{hook, body}` for the slug to `_cardgen/share-content.json`, run the generator to `share-cards/<slug>.png`, and add an entry to `share-posts.js`.

### Build an explainer from a YouTube video

Source material for an explainer doesn't have to be a blog post. `tools/yt-transcript.py` turns a video URL into a Markdown transcript you can hand to the explainer step:

```bash
uv run tools/yt-transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
# -> transcripts/VIDEO_ID.md
```

`uv` reads the script's inline dependency block, so there's nothing to install. With a plain interpreter, `pip install youtube-transcript-api yt-dlp` first.

| Flag | Effect |
|---|---|
| `-o PATH` | Output file (default `transcripts/<video_id>.md`) |
| `-l en,en-GB` | Caption languages, best first |
| `--timestamps` | Prefix each paragraph with its start time |
| `--no-meta` | Skip the yt-dlp title/channel/date lookup |
| `--stdout` | Print instead of writing a file |

It accepts any YouTube URL form (`watch`, `youtu.be`, `shorts`, `embed`, `live`) or a bare video ID, prefers human-written captions over auto-generated ones, and reflows the caption fragments into readable paragraphs. Captions are fetched via the captions API, falling back to yt-dlp when that's refused.

**This needs direct network access to youtube.com.** It won't run from a Claude Code web session whose egress policy blocks YouTube — run it locally and commit the transcript.

Published automatically via GitHub Pages (**main / root**).
