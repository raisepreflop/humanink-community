---
name: setup
description: Guided first run — find or create the brain, capture the first pen name, seed the structure, write brain.md and config.yaml.
version: "1.0.0"
---

# Guided setup (first run)

Goal: get the writer to a working brain in a few questions, with zero jargon.

## Steps

1. **Locate.** Ask where the brain should live. Recommend a **synced folder**
   (iCloud/Drive/Dropbox) so the inbox doubles as phone capture. Default offer:
   `~/HumanInk-Brain/`. Confirm before creating anything.

2. **First author (pen name).** Ask the name they publish under (their real name
   is fine — that's just one author folder). If they only use one name, the
   author level adds no friction; don't over-explain it.

3. **First book (optional).** If they have a current project, capture its name to
   seed `authors/{author}/books/{book}/`. If not, skip — they can add it later in
   one sentence.

4. **Seed the structure.** Run `scripts/brain-tree.sh <root> <author> [book]`.
   It creates the whole-writer folders, the author folders, and the book folder,
   each with `raw/ wiki/ outputs/ log.md` and an empty `wiki/index.md`.

5. **Write `brain.md`** (how it works + the writer's personal rules) and
   **`config.yaml`** (location, default author, pen-name list, preferences,
   backup target). See `references/preferences.md` for the keys.

6. **Tell them the one move that matters:** *drop anything into `inbox/`, then ask
   me to process it.* Everything else flows from there.

## brain.md template (write this at the root)

```markdown
# This is your HumanInk Brain
- The filesystem is the database; the librarian (HumanInk) organizes and retrieves.
- Drop anything into inbox/. Ask: "process my inbox".
- raw/ is yours to dump in. wiki/ is AI-built — don't hand-edit it.
- Ask your brain anything: "what do I have on…", "where did I write…",
  "does anything contradict…", "what have I never used…".
- Your canon never mixes between books or pen names.
- Answers come only from your files, with the source quoted.

## My rules (edit freely)
- (e.g. "Always ask before deleting." "Keep British spelling." …)
```

## config.yaml template

```yaml
brain_version: "1.0.0"
location: "~/HumanInk-Brain"
default_author: "{author}"
authors: ["{author}"]
preferences:
  ask_before_delete: true
  default_model: ""
backup_targets: []          # see durability.md
awap:
  log_events: true          # see awap-evidence.md
```

After setup, route the writer to `ingest.md` with their first dump.
