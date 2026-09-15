import json
import sys
from pathlib import Path

run_file = Path("runs/v0_B_base_gemini_20260915T193858431805.json")
if len(sys.argv) > 1:
    run_file = Path(sys.argv[1])

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

data = json.loads(run_file.read_text(encoding="utf-8"))
failed = [c for c in data["results"] if not c["result"]["passed"]]

print(f"=== SUMMARY: {data['summary']['passed_cases']}/{data['summary']['total_cases']} PASSED (Accuracy: {data['summary']['case_accuracy']*100:.1f}%) ===")
print(f"Total Failed Cases: {len(failed)}\n")

for c in failed:
    res = c["result"]
    print(f"ID: {c['id']}")
    print(f"  Skill/Test: {c.get('metadata', {}).get('what_it_tests', '')}")
    print(f"  Failure type: {res.get('failure_type')} (mismatch: {res.get('observed_mismatch')})")
    print(f"  Input: {c['input']}")
    print(f"  Expected: {c['expect']}")
    print(f"  Actual:   {res.get('actual_tool_calls')}")
    print(f"  Reason:   {res.get('failures')}")
    print("-" * 60)
