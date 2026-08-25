#!/usr/bin/env python3
"""awos-log.py — HumanInk collaborator usage logger
Usage:
  python3 ~/.awos/awos-log.py log --collaborator ID --name NAME --project PROJECT
      --mode MODE --tokens-in N --tokens-out N --docs-up N --docs-prod N
      --questions N --answers N
  python3 ~/.awos/awos-log.py show
  python3 ~/.awos/awos-log.py clear
"""
import sys, json, os
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

LOG_DIR  = Path.home() / '.awos' / 'logs'
LOG_FILE = LOG_DIR / 'awos-usage.jsonl'

COLLAB_NAMES = {
    'awos-autor':      ('Author Onboarding (01)',          '•'),
    'awos-analista':   ('Market Analyst (02)',             '•'),
    'awos-coach':      ('Literary Coach (03)',             '•'),
    'awos-estilo':     ('Style Editor (04)',               '•'),
    'awos-escritor':   ('Ghostwriter (05)',                '•'),
    'awos-editor':     ('Developmental Editor (06)',       '•'),
    'awos-lector':     ('Professional Reader (07)',        '•'),
    'awos-beta':       ('Beta Reader (08)',                '•'),
    'awos-corrector':  ('Copyeditor & Proofreader (09)',   '•'),
    'awos-maquetador': ('Interior Typesetter (10)',        '•'),
    'awos-asesor':     ('Literary Agent (11)',             '•'),
    'awos-copywriter': ('Copywriter (12)',                 '•'),
    'awos-portadista': ('Cover Designer (13)',             '•'),
    'awos-community':  ('Community Manager (14)',           '•'),
    'awos-marketero':  ('Ads Manager (15)',                '•'),
    'awos-humanizador': ('Humanizer (16)',                 '•'),
    'awos-auditor':     ('Authorship Auditor (17)',        '•'),
}

def cmd_log():
    args = sys.argv[2:]
    entry = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'collaborator': '', 'name': '', 'project': '',
        'mode': '--default',
        'tokens_in': 0, 'tokens_out': 0,
        'docs_uploaded': 0, 'docs_produced': 0,
        'questions': 1, 'answers': 1,
    }
    i = 0
    while i < len(args):
        a = args[i]
        v = args[i+1] if i+1 < len(args) else ''
        MAP = {
            '--collaborator': 'collaborator', '--name': 'name',
            '--project': 'project', '--mode': 'mode',
            '--tokens-in': 'tokens_in', '--tokens-out': 'tokens_out',
            '--docs-up': 'docs_uploaded', '--docs-prod': 'docs_produced',
            '--questions': 'questions', '--answers': 'answers',
        }
        if a in MAP:
            k = MAP[a]
            entry[k] = int(v) if entry[k].__class__ == int else v
            i += 2
        else:
            i += 1

    # Canonical name always wins for known slugs (normalizes any stale/Spanish
    # display name a collaborator might still pass), else keep what was given.
    if entry['collaborator'] in COLLAB_NAMES:
        entry['name'] = COLLAB_NAMES[entry['collaborator']][0]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    icon = COLLAB_NAMES.get(entry['collaborator'], ('', '📌'))[1]
    print(f"{icon} HumanInk Log · {entry['name']} · {entry['mode']}")
    print(f"   Project: {entry['project']} | in:{entry['tokens_in']:,} out:{entry['tokens_out']:,} | docs: ↑{entry['docs_uploaded']} ↓{entry['docs_produced']}")

def cmd_show():
    if not LOG_FILE.exists():
        print("No records yet. Use the collaborators to generate activity."); return

    logs = []
    for line in LOG_FILE.read_text(encoding='utf-8').strip().split('\n'):
        if line.strip():
            try: logs.append(json.loads(line))
            except: pass

    stats = defaultdict(lambda: {
        'name': '', 'icon': '📌', 'invocations': 0,
        'tokens_in': 0, 'tokens_out': 0,
        'docs_uploaded': 0, 'docs_produced': 0,
        'questions': 0, 'answers': 0,
        'projects': set(), 'modes': defaultdict(int),
    })

    for e in logs:
        cid = e.get('collaborator', 'unknown')
        s = stats[cid]
        s['name'] = e.get('name') or COLLAB_NAMES.get(cid, (cid,))[0]
        s['icon'] = COLLAB_NAMES.get(cid, ('', '📌'))[1]
        s['invocations'] += 1
        s['tokens_in']   += e.get('tokens_in', 0)
        s['tokens_out']  += e.get('tokens_out', 0)
        s['docs_uploaded']  += e.get('docs_uploaded', 0)
        s['docs_produced']  += e.get('docs_produced', 0)
        s['questions'] += e.get('questions', 0)
        s['answers']   += e.get('answers', 0)
        s['projects'].add(e.get('project', '—'))
        s['modes'][e.get('mode', '')] += 1

    total_in  = sum(s['tokens_in']  for s in stats.values())
    total_out = sum(s['tokens_out'] for s in stats.values())
    total_inv = sum(s['invocations'] for s in stats.values())
    total_dp  = sum(s['docs_produced'] for s in stats.values())
    total_du  = sum(s['docs_uploaded'] for s in stats.values())

    print(f"\n{'═'*62}")
    print(f"  HUMANINK USAGE DASHBOARD — {len(logs)} total records")
    print(f"{'─'*62}")
    print(f"  Total invocations    : {total_inv:>8,}")
    print(f"  Tokens input         : {total_in:>8,}")
    print(f"  Tokens output        : {total_out:>8,}")
    print(f"  Tokens TOTAL         : {total_in+total_out:>8,}")
    print(f"  Docs uploaded        : {total_du:>8,}")
    print(f"  Docs produced        : {total_dp:>8,}")
    print(f"{'═'*62}")
    print(f"  {'Collaborator':<35} {'Inv':>4} {'TokIn':>8} {'TokOut':>8} {'↑Doc':>5} {'↓Doc':>5}")
    print(f"{'─'*62}")
    for cid, s in sorted(stats.items(), key=lambda x: x[1]['invocations'], reverse=True):
        print(f"  {s['icon']} {s['name']:<33} {s['invocations']:>4} {s['tokens_in']:>8,} {s['tokens_out']:>8,} {s['docs_uploaded']:>5} {s['docs_produced']:>5}")
    print(f"{'═'*62}\n")

def cmd_clear():
    r = input("Delete the entire HumanInk log? (type 'yes'): ")
    if r.strip().lower() in ['sí', 'si', 's', 'yes', 'y']:
        LOG_FILE.unlink(missing_ok=True)
        print("✓ Log deleted.")
    else:
        print("Cancelled.")

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    {'log': cmd_log, 'show': cmd_show, 'clear': cmd_clear}.get(cmd, cmd_show)()
