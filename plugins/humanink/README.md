# HumanInk Community

`v2.2.1-club`

**The editorial suite for Escritores Aumentados members.**

Part of **HumanInk** — turn your Claude subscription into a full editorial team. The collaborators you choose, never a forced pipeline. Inference runs on *your* Claude, so there are no token bills from us.

> humanink.io · Human ink. AI team. Your authorship, proven.

---

## What's inside

This package installs the following collaborators (call any of them, in any order — nothing is mandatory):

- **`/humanink:help`** — Command Cheat-Sheet: Visual reference of every command in this plugin, grouped by phase — what each does and its key flags.
- **`/humanink:diagnostico`** — Setup Check: Checks what your Cowork (or computer) has for HumanInk to work: Python modules for Word and tracked changes, typesetting tools, fonts, internet and write access. Touches no files, costs nothing.
- **`/humanink:log`** — Usage Logger: Records each collaborator run (tokens, documents in/out) and shows the dashboard.
- **`/humanink:author`** — Author Onboarding (01): Interview that builds your author profile — voice, goals, history, limits, habits.
- **`/humanink:analyst`** — Market Analyst (02): Full market intelligence for any genre: reader avatar, rankings, competition, keywords, categories.
- **`/humanink:coach`** — Literary Coach (03): Story bible, Scene/Sequel outline, literary & commercial consulting, and writer mindset. Makes you finish the book.
- **`/humanink:style`** — Style Editor (04): Analyzes your voice and references and writes the project's definitive style guide (macro + micro).
- **`/humanink:ghostwriter`** — Ghostwriter (05): Writes, rewrites or expands chapters following every project doc. Built-in anti-AI-slop pass. Tracked changes in Word.
- **`/humanink:editor`** — Developmental Editor (06): Full developmental report: dialogue, description, prose, plot, subplots, structure, scene construction.
- **`/humanink:reader`** — Professional Reader (07): The complete integrated reading report: development + style + structure + theme + characters + genre + reader reaction + Traditional Publication Probability + a genre-weighted Bestseller Prediction score + marketing + a 3-option revision plan, with the HumanInk collaborator rewrite workflow. Delivered as a Word document.
- **`/humanink:beta`** — Beta Reader (08): Simulates a real reader of your target audience (configurable demographics). First-person verdict.
- **`/humanink:copyeditor`** — Copyeditor & Proofreader (09): Three passes over your manuscript: line edit, copy edit, proofread.
- **`/humanink:typesetter`** — Interior Typesetter (10): Assembles all chapters and produces 4 publish-ready formats (HTML master, PDF, EPUB, A4 Word).
- **`/humanink:agent`** — Literary Agent (11): Query letter, full editorial briefing, and a tracking sheet of 10+ publishers with contacts.
- **`/humanink:copywriter`** — Copywriter (12): Back-cover blurb (3 versions), bio, taglines, and the full optimized Amazon/KDP listing.
- **`/humanink:cover`** — Cover Designer (13): 5 cover concepts with AI prompts, then the full KDP paperback wrap (front+spine+back) and ebook JPG.
- **`/humanink:community`** — Community Manager (14): Content strategy for 2 networks with funnels & KPIs, monthly calendar, banners/carousels/video scripts.
- **`/humanink:humanizer`** — Humanizer · iParser (16): Detects AI marks in your text (score 0–100, 100+ patterns) and rewrites the most artificial fragments in your voice.
- **`/humanink:kdp-audit`** — Amazon KDP Auditor: Full audit of your book's Amazon listing from its ASIN: title, BSR, categories, cover, reviews, KDP policies, pricing, 3+ competitors — scored /100 with an improvement plan (Word + JSON history).
- **`/humanink:projects`** — Project Portfolio: One live HTML dashboard for all your projects: per-project cards, milestones and an SVG Gantt with a today line — updated by talking, no forms.
- **`/humanink:agenda`** — Agenda: Turns conversation into Google Calendar events, Gmail drafts and task lists (with your Google connectors authorized in Claude; degrades to a markdown agenda without them). Never sends email — drafts only.
- **`/humanink:verificar`** — Version Checker: Checks a manuscript version is sound: the .docx opens, tracked changes are legal, headings survived — and that rejecting every change gives back the previous version word for word.
- **`/humanink:comparar`** — Version Comparer: Compares two versions (or the whole series) of your manuscript: words added and cut, chapter by chapter.

---

## License

**HumanInk Community — membership edition.** Included with your Escritores Aumentados membership, for as long as you are a member. No purchase, no licence key.

**You may:**
- Install and use it on the machines you personally control.
- Use it to write, edit and publish an **unlimited number of your own books**, personal or commercial.
- Keep using this version forever, and receive minor updates of the version you bought.

**You may not:**
- Redistribute, resell, sublicense, publish or share the plugin files (in whole or in part).
- Repackage the collaborators, prompts or the iParser/AWAP code into another product.
- Remove or alter authorship, license or attribution notices.

The edition is personal to the member. If you leave the community, please uninstall it.

© Rais Busom / HumanInk. All rights reserved. See https://humanink.io for the full terms.

---

## Requirements

To use HumanInk you need **Anthropic Claude Cowork**, which requires:

1. The **Anthropic Claude Desktop App** — download: https://claude.ai/download
2. A **Claude subscription, Pro plan minimum** (Pro or Max) — get it: https://claude.ai/upgrade · plans: https://www.anthropic.com/pricing

HumanInk runs *inside* your own Claude — it never uses an API key, your manuscript text never leaves your machine, and there are no token bills from us. (Claude Code in the terminal also works to install and run the plugin.)

---

## Installation (1 minute)

1. In the Claude desktop app: **Customize → Plugins → Add ▾ → Add marketplace**, paste `raisepreflop/humanink-community` and confirm. (If it says the marketplace is already added, press **Sync**.)
2. **Browse** → search *humanink* → **Install**.
3. Open a **new** chat and type `/humanink:help`. If the command list appears, you're done.

**No licence key and nothing to activate.** The first time, a collaborator will ask for your email once — it only tells us who uses HumanInk in the community; it never opens or closes anything.

Updates arrive on their own, within about an hour of a release. **Never install this edition from a `.plugin` file**: a copy installed from a file cannot update itself, and two copies with the same name disable each other. If you have one, remove it under **Yours** and install from the catalogue instead.

---

## First run (3 steps)

**1. Open your book's folder.** Work in the folder where your book files are (or will be). No pre-existing structure is required.

**2. Tell the front desk what you want to do today:**

```
/humanink:recepcion quiero un informe de lectura de ~/Documents/mi-novela
```

It tells you which collaborator does that and what they need from you.

**3. Start with the collaborator you need.** A few examples for this package:

```
/humanink:help
/humanink:diagnostico
/humanink:log
/humanink:author ~/my-novel
```

---

## How to use it — the collaborators *you* choose

HumanInk's principle is **monitor and recommend, never force**. There is no locked pipeline: you call the collaborator you want, when you want it. A silent monitor may surface a brief, ignorable suggestion in the voice of the relevant collaborator — you can always keep writing.

Every collaborator is invoked the same way:

```
/humanink:<collaborator> <project path> [--option]
```

Pass the project path and, where it applies, a mode flag. Run a collaborator with no flags to see its options.

---

## Guides & documentation

Full docs online (language switcher EN/ES at the top):

- **Creative Suite — interactive flowchart:** https://humanink.io/docs/en
- **Collaborator reference guide:** https://humanink.io/docs/en/guide.html
- **From blank page to book — the process:** https://humanink.io/docs/en/process.html

---

## Support

Questions, license help or upgrades between bundles:

- Email: **info@humanink.io**
- Web: **https://humanink.io** · the Escritores Aumentados community
- YouTube: **https://www.youtube.com/@Humanink-hub** (tutorials & walkthroughs)

*HumanInk — Write however you want. Prove it properly.*
