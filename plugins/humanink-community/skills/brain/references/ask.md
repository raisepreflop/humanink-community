---
name: ask
description: Answer the writer's questions from the wiki, correctly scoped, with the evidence quoted and the source named. Save substantial answers to outputs/.
version: "1.0.0"
---

# Ask my brain

Answer questions from the wiki — *"what do I have on the detective?"*, *"what did
I establish about Mara in book 2?"*, *"which character notes have I never used?"*
Good answers are saved to the relevant `outputs/` and feed back in.

## The flow

1. **Scope first.** Determine the pen name / book / series, or whole-writer. If
   ambiguous, ask. (Never-pool — `honesty.md`.)
2. **Search, don't guess.** For "where did I write X", run the literal search
   first (`search.md`), then synthesize. For "what do I know about X", read the
   relevant wiki article(s) — actually read them.
3. **Answer under the grounding contract** (`honesty.md`):
   - Plain-English answer.
   - For canon facts: **quote the supporting line(s)** + name the article (+ which
     book, for a series).
   - If it's not in the brain: say so, name what you checked, suggest the literal search.
4. **Re-check** the answer against its quoted evidence; cut anything unsupported.
5. **Offer to save** a substantial answer/briefing to `outputs/` so it compounds.

## Question shapes and how to handle them

| Shape | Handling |
|---|---|
| *"What do I have on X?"* | Gather across the scope's wiki; cite articles. |
| *"What did I establish about X in book N?"* | Scope to that series; quote evidence with provenance. |
| *"Where did I write about X?"* | Literal search first (`search.md`), then synthesize. |
| *"What have I never used?"* | Route to `resurfacing.md`. |
| *"Does anything contradict X?"* | Route to `continuity-audit.md`. |
| *"Is <real-world fact> true?"* | Route to `fact-check.md` — different evidence rules. |

## Never

- Never blend one brand's character or canon into another's answer.
- Never present training-data inference as the writer's canon.
- Never give an unsourced canon claim.

Log a substantial answer as an authorship event (`awap-evidence.md`).
