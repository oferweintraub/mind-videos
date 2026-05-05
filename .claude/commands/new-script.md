---
description: Draft a new episode script.md (Hebrew dialogue across multiple characters)
argument-hint: <slug> [topic] | <slug> --from <path/to/draft.{txt,md,docx,pdf}>
---

The user wants to draft a new episode script.

User input: **$ARGUMENTS**

## Step 1 — Pick a slug + topic OR ingest a draft

Detect which mode the user is in by scanning `$ARGUMENTS`:

**Draft-import mode** — if the args contain `--from <path>`, OR a path that ends in `.txt`, `.md`, `.docx`, or `.pdf`, OR the user said something like "convert this file" / "use this draft":

1. Run:
   ```bash
   source venv/bin/activate && python scripts/extract_text.py "<path>"
   ```
   This prints the plain text of the draft to stdout. Capture it.
2. Show the user the extracted text (or the first 30-40 lines if it's long) and ask them to confirm it looks right.
3. **Skip step 2 below** (you already have content). Go to step 3 with the extracted text as the source.

If the user pastes raw text directly into `$ARGUMENTS` (no path), treat that as the draft and skip extraction — go straight to step 3.

**Topic mode** — anything else:

If `$ARGUMENTS` already gives a slug, use it. Otherwise propose one (lowercase, underscores, ≤ 30 chars) and confirm with the user.

If `$ARGUMENTS` includes a topic/theme, use it. If not, ask: "What is this episode about? Give me a sentence in Hebrew or English."

## Step 2 — Survey the available characters

Run:

```bash
ls characters/
```

(Skip directories starting with `_` — those are candidate images, not real characters.)

For each character, read its manifest:

```bash
cat characters/<slug>/manifest.json
```

Summarize the cast to the user (slug, display name, style, one-line description). Ask: **"Who should appear in this episode, and in what order?"**

If the user wants a character that doesn't exist yet, suggest running `/new-character` first.

## Step 3 — Draft the dialogue

If you came from **topic mode**, write 3-5 fresh Hebrew segments. Match each character's voice/personality from their manifest description. The Channel 14 + Eden format is a strong default if the user hasn't specified another:

- 2-4 over-the-top adoring statements from the anchor(s)
- A final quiet question from a child or skeptic that punctures the narrative

If you came from **draft-import mode**, you have an existing text. Your job is to:
1. Split the text into segments (paragraphs, dialogue beats, or natural pauses).
2. **Map each segment to a character slug** from `characters/`. Look for explicit speaker labels in the source (e.g. "Anchor: ...", "אנקור: ...", "[Eden]: ..."), and fuzzy-match them to slugs. If the source has no speaker labels, propose an assignment based on tone/content and the personalities in the character manifests.
3. If any segment is too long for one breath (~25s of audio at 15 chars/sec ≈ 375 chars), suggest splitting it.
4. If the source is in English or another non-Hebrew language and the user wants Hebrew output, translate it — but tell the user you translated and ask them to verify.

In **both** modes: show the full draft to the user **before saving** and ask for revisions. Speaker mappings especially deserve a visible pass — list them as e.g.:

```
#1 → @anchor_female: "אני מאוהבת..."
#2 → @anchor_male:   "לגמרי..."
#3 → @eden:          "אבל אמא..."
```

Ask: "Do these speaker assignments look right? Any to swap or split?"

## Step 4 — Save

Once the draft is approved, write `episodes/<slug>/script.md` with this exact format:

```markdown
---
title: <Short title in English or Hebrew>
description: <One-line summary>
---

## <character_slug>  (optional annotation)
<Hebrew text — keep on one line per paragraph; multi-line is OK>

## <character_slug>
<Hebrew text>

...
```

**Format rules**:
- Each `## ` heading is a new segment. The first word after `##` MUST be an exact character slug from `characters/`. Anything else after the slug is free-text annotation (ignored by the pipeline).
- Hebrew text goes between headings. Multiple lines are OK; they get joined with newlines.
- The same character may appear multiple times — each `##` is its own segment.

## Step 5 — Validate

Run a parser check to confirm the script is valid:

```bash
source venv/bin/activate && python -c "
from src.script_format import parse_file, validate_against_characters
from src.character import slugs
s = parse_file('episodes/<slug>/script.md')
errors = validate_against_characters(s, slugs())
print(f'segments={len(s.segments)}, characters={s.characters}')
print('errors:', errors or 'none')
"
```

If errors are reported, fix the script and re-validate before exiting.

## Step 6 — Tell the user what's next

> Script saved to `episodes/<slug>/script.md`. Render it with:
>
> ```
> /make-video <slug>
> ```
>
> Estimated cost: ~$0.10 per second of audio (Hebrew TTS averages ~15 chars/sec, lip-sync is $0.08/s).
