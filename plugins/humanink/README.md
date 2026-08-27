# HumanInk Community

`v2.0.0-club`

**The editorial suite for Escritores Aumentados members.**

Part of **HumanInk** — turn your Claude subscription into a full editorial team. The collaborators you choose, never a forced pipeline. Inference runs on *your* Claude, so there are no token bills from us.

> humanink.io · Human ink. AI team. Your authorship, proven.

---

## What's inside

This package installs the following collaborators (call any of them, in any order — nothing is mandatory):

- **`/humanink:help`** — Command Cheat-Sheet: Visual reference of every command in this plugin, grouped by phase — what each does and its key flags.
- **`/humanink:dashboard`** — Project Dashboard: Live cockpit of your project — Human Authorship Score, active collaborators, metrics.
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
- **`/humanink:auditor`** — Authorship Auditor (17): Certifies your human authorship with AWAP: records every writing event, computes your Human Authorship Score, signs a QR-verifiable PDF certificate.
- **`/humanink:kdp-audit`** — Amazon KDP Auditor: Full audit of your book's Amazon listing from its ASIN: title, BSR, categories, cover, reviews, KDP policies, pricing, 3+ competitors — scored /100 with an improvement plan (Word + JSON history).
- **`/humanink:projects`** — Project Portfolio: One live HTML dashboard for all your projects: per-project cards, milestones and an SVG Gantt with a today line — updated by talking, no forms.
- **`/humanink:agenda`** — Agenda: Turns conversation into Google Calendar events, Gmail drafts and task lists (with your Google connectors authorized in Claude; degrades to a markdown agenda without them). Never sends email — drafts only.

It also bundles the **AWAP engine** (the Authorship Audit Protocol) so the auditor can sign a publicly verifiable certificate of human authorship.

---

## License

**Commercial — HumanInk Single License (Model B).** One-time purchase, lifetime use. No subscription, no recurring fee for the plugin itself.

**You may:**
- Install and use it on the machines you personally control.
- Use it to write, edit and publish an **unlimited number of your own books**, personal or commercial.
- Keep using this version forever, and receive minor updates of the version you bought.

**You may not:**
- Redistribute, resell, sublicense, publish or share the plugin files (in whole or in part).
- Repackage the collaborators, prompts or the iParser/AWAP code into another product.
- Remove or alter authorship, license or attribution notices.

The license is personal to the purchaser. One purchase = one author/seat. Lost or shared files that appear in the wild may have their license key revoked.

© Rais Busom / HumanInk. All rights reserved. See https://humanink.io for the full terms.

---

## Requirements

To use HumanInk you need **Anthropic Claude Cowork**, which requires:

1. The **Anthropic Claude Desktop App** — download: https://claude.ai/download
2. A **Claude subscription, Pro plan minimum** (Pro or Max) — get it: https://claude.ai/upgrade · plans: https://www.anthropic.com/pricing

HumanInk runs *inside* your own Claude — it never uses an API key, your manuscript text never leaves your machine, and there are no token bills from us. (Claude Code in the terminal also works to install and run the plugin.)

For certificates: AWAP runs as a **hosted HumanInk service** (nothing to install or configure; needs an internet connection). It receives only document **hashes and metadata** — score inputs, titles, dates — **never your manuscript text**.

---

## Installation (1 minute)

1. In the Claude desktop app: **Settings → Plugins → Add → Upload plugin**, and choose **`humanink-community-full-v2.0.0-club.plugin`**.
2. Open a **new** chat and type `/humanink:help`. If the command list appears, you're done.

The collaborators appear as `/humanink:…` commands.

> **If the plugin shows under Settings → Plugins but the chat says the skill is unknown** — this only happens on machines that also have Claude Code installed — upload the same file from your browser instead: **claude.ai → Settings → Plugins → Add → Upload plugin**. Then open a new chat.

### One more click — only if you will use the Authorship Auditor

Cowork does **not** connect a plugin's connectors automatically. Once, after installing:

**Plugins → HumanInk → Connectors → `awap` → Connect**

Without it, the Auditor and the certificate cannot record your authorship. Everything else works regardless.

---

## First run (3 steps)

**1. Open your book's folder.** Work in the folder where your book files are (or will be). No pre-existing structure is required.

**2. Point the dashboard at it:**

```
/humanink:awos ~/Documents/my-novel
```

If the folder isn't set up yet, it will guide you to initialize it.

**3. Start with the collaborator you need.** A few examples for this package:

```
/humanink:help
/humanink:dashboard ~/my-novel
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

### Proving your authorship (the certificate)

Use the **Authorship Auditor** to record your process and sign a certificate:

```
/humanink:auditor ~/Documents/my-novel --init         # start auditing from day one
/humanink:auditor ~/Documents/my-novel --status       # status & Human Authorship Score
/humanink:auditor ~/Documents/my-novel --certificate  # sign the PDF certificate (QR-verifiable)
```

It's **process evidence**, not a result scan — aligned with what the U.S. Copyright Office asks for to register AI-assisted work.

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
