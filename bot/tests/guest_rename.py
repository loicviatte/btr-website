"""Guest name fix (Loïc 03.11: « Hannah Trever », not « Trevor »): the replacements, and a dry run on a copy of a real
episode's files (argument: data/episodes/<id>, read only).  python tests/guest_rename.py [/opt/btr-bot/data/episodes/O_ZdYlKrdwU]"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import rename  # noqa: E402

R = rename.subs("Hannah Trevor", "Hannah Trever")
CASES = {"with Hannah Trevor | x": "with Hannah Trever | x", "#HannahTrevor #dpa": "#HannahTrever #dpa",
         "1103_HANNAH-TREVOR_QUOTE_01.jpg": "1103_HANNAH-TREVER_QUOTE_01.jpg", "HANNAH TREVOR ON RISKS": "HANNAH TREVER ON RISKS",
         "Ms Trevor said": "Ms Trever said", "@hannahtrevor": "@hannahtrevor", "Trevorson": "Trevorson",
         "hannah trevor": "hannah trever"}
for a, b in CASES.items():
    got = rename.fix(a, R)
    assert got == b, (a, got, b)
assert rename.fix_obj({"f": "/x/Hannah Trevor.jpg", "u": "https://a/Trevor", "t": ["Trevor"]}, R) == \
    {"f": "/x/Hannah Trevor.jpg", "u": "https://a/Trevor", "t": ["Trever"]}
print("replacements ok")

if len(sys.argv) > 1:
    src = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as d:
        for f in list(src.glob("*.json")) + list(src.glob("*.srt")):
            shutil.copy(f, d)
        for p in sorted(Path(d).iterdir()):
            before = p.read_text(errors="replace")
            changed = rename.fix_json(p, R) if p.suffix == ".json" else rename.fix_file(p, R)
            after = p.read_text(errors="replace")
            print(f"{p.name}: {'fixed' if changed else '-'} · Trevor {len(re.findall('(?i)trevor', before))}"
                  f" → {len(re.findall('(?i)trevor', after))} · Trever {len(re.findall('(?i)trever', after))}")
