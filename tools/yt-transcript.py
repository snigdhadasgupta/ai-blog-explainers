#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "youtube-transcript-api>=1.2",
#     "yt-dlp>=2025.1.1",
# ]
# ///
"""Fetch a YouTube video's transcript and write it out as a Markdown document.

Run it wherever youtube.com is reachable, then hand the generated file to
whoever is writing the explainer.

    uv run tools/yt-transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"

Or with a plain interpreter, after `pip install youtube-transcript-api yt-dlp`:

    python3 tools/yt-transcript.py "https://youtu.be/VIDEO_ID" -o notes.md

Transcripts are fetched two ways: the captions API first, and yt-dlp as a
fallback for the cases it refuses (datacenter IPs are frequently blocked).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

# Every URL shape YouTube hands out, plus a bare ID.
_ID_PATTERNS = [
    r"(?:youtube\.com|youtube-nocookie\.com)/watch\?(?:.*&)?v=([\w-]{11})",
    r"youtu\.be/([\w-]{11})",
    r"(?:youtube\.com|youtube-nocookie\.com)/(?:embed|shorts|live|v)/([\w-]{11})",
    r"^([\w-]{11})$",
]


def extract_video_id(url):
    """Pull the 11-character video ID out of any YouTube URL form."""
    for pattern in _ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise SystemExit(f"Could not find a YouTube video ID in: {url!r}")


def timestamp(seconds):
    """Format seconds as m:ss, or h:mm:ss once the video passes an hour."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fetch_metadata(video_id):
    """Best-effort title/channel/date via yt-dlp. Returns {} if unavailable."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return {}

    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
    except Exception as exc:  # network, geo-block, private video, ...
        print(f"  ! metadata unavailable ({type(exc).__name__})", file=sys.stderr)
        return {}

    upload_date = info.get("upload_date") or ""
    if len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

    return {
        "title": info.get("title"),
        "channel": info.get("uploader") or info.get("channel"),
        "upload_date": upload_date,
        "duration": timestamp(info["duration"]) if info.get("duration") else None,
        "description": info.get("description") or "",
    }


def fetch_via_api(video_id, languages):
    """Primary path: the captions API. Prefers human captions over auto-generated."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    listing = api.list(video_id)

    try:
        transcript = listing.find_manually_created_transcript(languages)
        kind = "manual"
    except Exception:
        transcript = listing.find_generated_transcript(languages)
        kind = "auto-generated"

    snippets = [
        {"start": s.start, "duration": s.duration, "text": s.text}
        for s in transcript.fetch()
    ]
    return snippets, kind, transcript.language_code


def fetch_via_ytdlp(video_id, languages):
    """Fallback path: let yt-dlp download the caption track and parse json3."""
    lang = languages[0]
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--skip-download",
            "--write-subs", "--write-auto-subs",
            "--sub-langs", f"{lang}.*,{lang}",
            "--sub-format", "json3",
            "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        files = [f for f in os.listdir(tmpdir) if f.endswith(".json3")]
        if not files:
            raise RuntimeError(
                "yt-dlp produced no caption file. "
                f"stderr: {result.stderr.strip()[:400] or '(none)'}"
            )

        # A manually written track wins over the auto-generated one.
        files.sort(key=lambda f: ".orig." in f or "-orig" in f, reverse=True)
        with open(os.path.join(tmpdir, files[0]), encoding="utf-8") as handle:
            data = json.load(handle)

    snippets = []
    for event in data.get("events", []):
        text = "".join(seg.get("utf8", "") for seg in event.get("segs", []) or [])
        text = text.strip()
        if not text:
            continue
        snippets.append({
            "start": event.get("tStartMs", 0) / 1000.0,
            "duration": event.get("dDurationMs", 0) / 1000.0,
            "text": text,
        })

    kind = "auto-generated" if "auto" in files[0] or "orig" not in files[0] else "manual"
    return snippets, kind, lang


def clean(text):
    """Strip caption artifacts: newlines, [Music]/[Applause] tags, doubled spaces."""
    text = text.replace("\n", " ")
    text = re.sub(r"\[[^\]]{1,25}\]", " ", text)  # [Music], [Applause], [__]
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_paragraphs(snippets, gap_threshold=2.0, target_words=110):
    """Reflow caption fragments into readable paragraphs.

    Captions arrive as ~5-word fragments. Break on a long silence or a sentence
    ending once the paragraph is already substantial, so paragraphs land on
    natural boundaries instead of mid-thought.
    """
    paragraphs = []
    current, start_time, word_count, previous_end = [], None, 0, None

    for snippet in snippets:
        text = clean(snippet["text"])
        if not text:
            continue

        if start_time is None:
            start_time = snippet["start"]

        gap = snippet["start"] - previous_end if previous_end is not None else 0
        ends_sentence = current and current[-1].rstrip().endswith((".", "?", "!"))

        should_break = word_count >= target_words and (ends_sentence or gap >= gap_threshold)
        if should_break:
            paragraphs.append({"start": start_time, "text": " ".join(current)})
            current, word_count, start_time = [], 0, snippet["start"]

        current.append(text)
        word_count += len(text.split())
        previous_end = snippet["start"] + snippet["duration"]

    if current:
        paragraphs.append({"start": start_time, "text": " ".join(current)})
    return paragraphs


def render(video_id, meta, paragraphs, kind, language, show_timestamps):
    url = f"https://www.youtube.com/watch?v={video_id}"
    title = meta.get("title") or f"YouTube transcript — {video_id}"
    total_words = sum(len(p["text"].split()) for p in paragraphs)

    lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f"source_url: {url}",
        f"video_id: {video_id}",
    ]
    for key in ("channel", "upload_date", "duration"):
        if meta.get(key):
            lines.append(f"{key}: {meta[key]}")
    lines += [
        f"captions: {kind} ({language})",
        f"word_count: {total_words}",
        "---",
        "",
        f"# {title}",
        "",
    ]

    byline = []
    if meta.get("channel"):
        byline.append(f"**{meta['channel']}**")
    if meta.get("upload_date"):
        byline.append(meta["upload_date"])
    if meta.get("duration"):
        byline.append(meta["duration"])
    if byline:
        lines += [" · ".join(byline), ""]
    lines += [f"[Watch on YouTube]({url})", "", "---", "", "## Transcript", ""]

    for para in paragraphs:
        if show_timestamps:
            lines.append(f"**[{timestamp(para['start'])}]** {para['text']}")
        else:
            lines.append(para["text"])
        lines.append("")

    if meta.get("description"):
        description = meta["description"].strip()
        if description:
            lines += ["---", "", "## Video description", "", "```", description, "```", ""]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a YouTube transcript and write it as Markdown."
    )
    parser.add_argument("url", help="YouTube URL (watch, youtu.be, shorts, embed) or bare video ID")
    parser.add_argument("-o", "--out", help="Output file (default: transcripts/<video_id>.md)")
    parser.add_argument("-l", "--lang", default="en",
                        help="Comma-separated caption languages, best first (default: en)")
    parser.add_argument("--timestamps", action="store_true",
                        help="Prefix each paragraph with its start time")
    parser.add_argument("--no-meta", action="store_true",
                        help="Skip the yt-dlp metadata lookup (faster)")
    parser.add_argument("--stdout", action="store_true", help="Print instead of writing a file")
    args = parser.parse_args()

    video_id = extract_video_id(args.url.strip())
    languages = [lang.strip() for lang in args.lang.split(",") if lang.strip()]
    print(f"Video ID: {video_id}", file=sys.stderr)

    meta = {} if args.no_meta else fetch_metadata(video_id)

    try:
        snippets, kind, language = fetch_via_api(video_id, languages)
        print(f"  captions via API: {kind} ({language})", file=sys.stderr)
    except Exception as api_error:
        print(f"  ! captions API failed: {type(api_error).__name__}: {api_error}",
              file=sys.stderr)
        print("  trying yt-dlp fallback ...", file=sys.stderr)
        try:
            snippets, kind, language = fetch_via_ytdlp(video_id, languages)
            print(f"  captions via yt-dlp: {kind} ({language})", file=sys.stderr)
        except Exception as ytdlp_error:
            raise SystemExit(
                f"Could not retrieve a transcript for {video_id}.\n"
                f"  captions API: {api_error}\n"
                f"  yt-dlp:       {ytdlp_error}\n"
                "The video may have captions disabled, be private/age-restricted, "
                "or your IP may be blocked by YouTube."
            )

    if not snippets:
        raise SystemExit("The caption track came back empty.")

    paragraphs = build_paragraphs(snippets)
    document = render(video_id, meta, paragraphs, kind, language, args.timestamps)

    if args.stdout:
        print(document)
        return

    out_path = args.out or os.path.join("transcripts", f"{video_id}.md")
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(document)

    words = sum(len(p["text"].split()) for p in paragraphs)
    print(f"Wrote {out_path} ({len(paragraphs)} paragraphs, {words} words)", file=sys.stderr)


if __name__ == "__main__":
    main()
