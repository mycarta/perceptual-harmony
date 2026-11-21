"""Bundle the package source for the web page: writes docs/perceptual_harmony.json.

    python docs/build_bundle.py

The page loads this file into Pyodide, so it runs the same code as the library. Re-run after
changing anything in src/perceptual_harmony; the test suite checks that the bundle is current.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src' / 'perceptual_harmony'
OUT = ROOT / 'docs' / 'perceptual_harmony.json'


def bundle() -> str:
    files = {p.name: p.read_text(encoding='utf-8') for p in sorted(SRC.glob('*.py'))}
    return json.dumps(files, indent=0, sort_keys=True, ensure_ascii=False) + '\n'


if __name__ == '__main__':
    OUT.write_text(bundle(), encoding='utf-8')
    print('wrote', OUT)
