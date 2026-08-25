# HumanInk — User Manual

**Write however you want. Prove it properly.**

HumanInk is your augmented writing team inside Claude: **18 editorial collaborators** you call
whenever you want, an **AI-text humanizer** tuned for fiction, and a **verifiable certificate of
human authorship** (AWAP). It runs on *your* Claude — there are no token bills from us, and your
manuscript never leaves your computer.

> Core principle: **you choose.** HumanInk monitors and recommends — it never forces a pipeline.
> Call the collaborator you want, when you want, in any order.

---

## 1. What you need

- **Claude Desktop App** (Mac or Windows) — HumanInk runs inside its **Cowork** mode.
- A **Claude Pro plan (minimum)** — Cowork requires at least Pro.
- Your **HumanInk Writers' Room `.plugin`** file — the suite with all 18 collaborators.

---

## 2. Get Claude (one time)

1. Download the desktop app: **https://claude.ai/download** and sign in.
2. Make sure you're on **Pro (or higher)**: **https://claude.ai/upgrade**.
3. Open the app and enter **Cowork**.

---

## 3. Install the plugin (one time)

1. In Cowork, **drag your `humanink-<tier>-vX.plugin` file into the window** → **Accept**.
2. You may see a notice that the plugin includes a local **MCP server** (named `awap`). That's
   normal — it's the local engine that powers your authorship certificate. Accept it.
3. **Fully quit and reopen the app** (Cmd+Q on Mac) so everything loads cleanly.

To update later: drag the newer `.plugin` (higher version number), then **Cmd+Q and reopen**.

---

## 4. Set up your book

Create one folder per book and open it in Cowork. You only need to start with two files in your
own words:

```
my-novel/
├── premise.md        ← your idea (you write this)
└── synopsis.md       ← your summary (you write this)
```

From there, **let the collaborators build and organize the rest for you** — story bible, outline,
style guide, reports. You don't have to create or name those files yourself; each collaborator
knows where to put its work inside your book folder.

### How your manuscript is stored — the build system (recommended)

Keep **the whole manuscript in one file, numbered upward**. Every session — every intervention on
the text — produces the next build:

```
my-novel/
├── My-Novel-b01.docx     ← the whole manuscript, build 1
├── My-Novel-b02.docx     ← after the next session
└── My-Novel-b03.docx     ← …and so on
```

This is the system this suite was proven on, across several published novels, and it exists for one
reason: **surgical rewriting**. When the entire text sits in a single file, the collaborator reads
the whole novel before touching a line, finds every placeholder in one pass, and checks coherence
against the real book instead of against reassembled fragments. Nothing drifts, because nothing was
split apart.

It also gives you a free safety net: each build is a complete snapshot, so you can always go back
to how the novel read three sessions ago, and compare two builds side by side.

You don't have to rename anything by hand — the collaborators detect your numbering and write the
next build themselves. If you already keep **one file per chapter** (`capitulos/cap-01-v1.docx`),
that works too and is detected automatically; you simply lose the whole-manuscript view that makes
surgical rewrites safe.

> ⚠️ If a collaborator tells you it could not find your manuscript, **stop and fix the path or the
> naming before writing anything**. It will say so out loud rather than write blind — but a chapter
> written without the novel in front of it is a coherence problem you'll pay for later.

---

## 5. How to call a collaborator

Type a slash command in Cowork:

```
/humanink:<name>  [path-to-your-book]  [options]
```

Examples:

```
/humanink:coach ~/my-novel --bible
/humanink:ghostwriter 1 ~/my-novel
/humanink:editor ~/my-novel/chapters/ch-01.docx
/humanink:dashboard ~/my-novel
```

If you leave out the path, the current project folder is used. Each collaborator tells you what it
produced and suggests a sensible next step — but the next move is always yours.

---

## 6. Your 18 collaborators

> **HumanInk Writers' Room** includes all 18 collaborators + the iParser humanizer + the AWAP
> authorship auditor (with a free **draft** certificate). The official, publicly-verifiable
> certificate is a separate product — **HumanInk Certificate**.

### Foundation
| # | Command | What it does |
|---|---------|--------------|
| 01 | `/humanink:author` | Author Onboarding — interview that builds your author profile (voice, goals, habits, limits). |
| 02 | `/humanink:analyst` | Market Analyst — genre intelligence: reader avatar, rankings, competition, keywords, categories. |

### Development
| # | Command | What it does |
|---|---------|--------------|
| 03 | `/humanink:coach` | Literary Coach — story bible, scene/sequel outline, consulting, and the mindset to **finish the book**. |
| 04 | `/humanink:style` | Style Editor — analyzes your voice and writes your project's definitive style guide. |
| 05 | `/humanink:ghostwriter` | Ghostwriter — writes/rewrites/expands chapters in your voice, with an anti-AI-slop pass and tracked changes. |
| 06 | `/humanink:editor` | Developmental Editor — full report: dialogue, prose, plot, subplots, structure, scene construction. |
| 07 | `/humanink:reader` | Professional Reader — the complete **integrated reading report**: scores, structure (beats), theme, characters, genre, Traditional Publication Probability + marketing + a 3-option revision plan with the collaborator rewrite workflow. Word doc. |
| 08 | `/humanink:beta` | Beta Reader — simulates a real reader of your target audience; first-person verdict. |

### Finishing
| # | Command | What it does |
|---|---------|--------------|
| 09 | `/humanink:copyeditor` | Copyeditor & Proofreader — three passes: line edit, copy edit, proofread. |
| 10 | `/humanink:typesetter` | Interior Typesetter — assembles chapters into publish-ready HTML, PDF, EPUB and A4 Word. |
| 16 | `/humanink:humanizer` | Humanizer (iParser) — scores AI patterns (0–100) and rewrites the most artificial fragments **in your voice**. |

### Publishing
| # | Command | What it does |
|---|---------|--------------|
| 11 | `/humanink:agent` | Literary Agent — query letter, editorial briefing, and a tracking sheet of 10+ publishers. |
| 12 | `/humanink:copywriter` | Copywriter — back-cover blurb, bio, taglines, and the full optimized Amazon/KDP listing. |
| 13 | `/humanink:cover` | Cover Designer — 5 cover concepts + AI prompts, then the full KDP wrap and ebook cover. |

### Marketing
| # | Command | What it does |
|---|---------|--------------|
| 14 | `/humanink:community` | Community Manager — content strategy, calendar, banners/carousels/video scripts. |
| 15 | `/humanink:ads` | Ads Manager — Amazon & Meta Ads: strategy, campaigns, keywords, creatives, daily optimization. |

### Trust & Memory
| # | Command | What it does |
|---|---------|--------------|
| 17 | `/humanink:auditor` | Authorship Auditor — your AWAP control panel: status, score, and the authorship certificate. |
| 18 | `/humanink:brain` | Continuity Editor (HumanInk Brain) — your **second brain** (see §8). |

Two control commands:
- `/humanink:dashboard` — live cockpit of your project (Human Authorship Score, active collaborators, metrics).
- `/humanink:log` — system log of every collaborator run (tokens in/out, documents).

---

## 7. A recommended flow (optional)

You can jump in anywhere, but a natural order is:

1. **`/humanink:author`** → your profile · **`/humanink:analyst`** → the market.
2. **`/humanink:coach --bible`** → story bible + outline · **`/humanink:style`** → your style guide.
3. **`/humanink:ghostwriter 1`** → draft a chapter (repeat per chapter).
4. **`/humanink:editor` · `/humanink:reader` · `/humanink:beta`** → feedback; revise.
5. **`/humanink:copyeditor`** → polish · **`/humanink:humanizer --analyze`** → check your voice.
6. **`/humanink:typesetter --all`** → publish-ready files.
7. **`/humanink:cover` · `/humanink:copywriter` · `/humanink:agent`** → package & submit.
8. **`/humanink:community` · `/humanink:ads`** → launch.

Tip: **revising AI-drafted text raises your Human Authorship Score** — the more of your own
revision, the stronger your authorship record.

---

## 8. How your work persists (memory)

HumanInk remembers across sessions in three ways:

1. **Your project folder is the memory.** Everything the collaborators produce (bible, outline,
   style guide, chapters, reports) lives as files in your book folder. Reopen the folder anytime
   and pick up where you left off.
2. **The authorship ledger (`.awap/`).** As you write, HumanInk silently logs each event — what
   you wrote, what the AI generated, what you revised, and when — into a hidden `.awap/` folder.
   This feeds your **Human Authorship Score (HAS, 0–100)**. See it anytime with
   **`/humanink:dashboard`**; see the raw activity with **`/humanink:log`**.
3. **HumanInk Brain (#18) — your second brain.** A folder of notes you own. Say things like
   *"add this to my brain"*, *"what do I have on X"*, *"which notes have I never used"*. It answers
   **only** from your own files (quoting the evidence) and never mixes one book or pen name into
   another.

> ⚠️ **Important — Cowork does not keep your chat between sessions.** Your **files** and your
> `.awap/` authorship ledger persist, but the **conversation itself is temporary**: when you close
> a Cowork session, that chat is gone. If a conversation matters (decisions you made, ideas, a
> thread you want to keep), **ask HumanInk to save it**: say *"save this chat to a memory file"* and
> it will write the conversation to a markdown file in your book folder so you (and your next
> session) can read it. For knowledge you'll reuse across the book, put it in your **Brain (#18)**.

---

## 9. Prove your authorship — the certificate

HumanInk produces a **Certificate of Human Authorship** via the AWAP protocol. There are two kinds:

- **Draft (free, unlimited).** A local self-audit so you can track your score while you write:
  ```
  /humanink:auditor ~/my-novel --certificate
  ```
  The draft is **not** an official certificate — its QR will say *"not registered"* until you
  register it. Use it to see how your authorship is shaping up.

- **Official (the certificate you present).** Frozen to your final manuscript, registered with
  HumanInk, anchored for tamper-proof timestamping, and **publicly verifiable** at
  `verify.humanink.io` — the certificate for a copyright office, a publisher or an agent:
  ```
  /humanink:auditor ~/my-novel --official
  ```
  Registering requires a HumanInk Certificate credit (one per title) — see
  **https://humanink.io/#pricing**.

Other AWAP commands: `--status` (current score), `--report` (full breakdown), `--score` (just the number).

---

## 10. Good to know

- **It's your Claude.** All writing and analysis run on your own Claude subscription — no extra
  token bills from us. Your manuscript stays on your computer.
- **Nothing is forced.** Skip any collaborator. There's no locked pipeline.
- **The Humanizer protects your voice** — it's tuned for fiction and your defense against
  false-positive "AI" accusations; it is *not* a detector-bypass trick.
- **EPUB for Amazon KDP** (Interior Typesetter `--epub`) needs **pandoc** installed — a one-time
  `brew install pandoc epubcheck` (macOS). Everything else is built in.
- **Updating** = drag the newer `.plugin`, then **Cmd+Q and reopen**.

---

## Support

- Email: **info@humanink.io**
- Web: **https://humanink.io** · YouTube: **https://www.youtube.com/@Humanink-hub**

*HumanInk — Human ink. AI team. Your authorship, proven.*
