---
name: preferences
description: The config.yaml keys and the writer's personal rules in brain.md — how behaviour is tuned without touching the skill.
version: "1.0.0"
---

# Preferences

The brain is tuned by two files the writer owns: `config.yaml` (machine settings)
and `brain.md` (personal rules in plain English). Read both every session.

## config.yaml keys

```yaml
brain_version: "1.0.0"
location: "~/HumanInk-Brain"
default_author: "jack-reeve"        # resolves unscoped actions
authors: ["jack-reeve", "real-name"]
preferences:
  ask_before_delete: true           # always confirm deletions
  default_model: ""                 # leave blank to use the session model
  spelling: ""                      # e.g. "en-GB" — honour in wiki prose
  resurfacing: true                 # allow quiet resurfacing during tasks
backup_targets: []                  # paths/services for backup-mirror.sh
awap:
  log_events: true                  # log authorship events if AWAP is installed
```

## brain.md — personal rules (plain English)

The writer writes rules in their own words; you honour them. Examples:

- "Always ask before deleting or overwriting."
- "Keep British spelling in the wiki."
- "Never resurface fragments while I'm drafting — only when I ask."
- "For Jack Reeve, default to thriller comps."

Personal rules win over defaults. If a rule conflicts with the grounding contract
(`honesty.md`) or the never-pool rule, those safety rules still hold — explain why
and offer an alternative.

## Changing preferences

The writer changes preferences in one sentence (*"stop resurfacing while I
draft"*); update `config.yaml` or `brain.md` accordingly and confirm. Never change
a preference without being asked.
