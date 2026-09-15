import sys
import io
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import json
from env_loader import load_lab_env
from tools import TOOL_FUNCTIONS as T

# Load env variables if available
load_lab_env(Path.cwd())

results = {}

# 1. clarify
try:
    r = T['clarify']('Mã asset là gì?', 'text')
    results['clarify'] = {'status': 'PASS' if r.get('awaiting_user') is True else 'FAIL', 'output': r}
except Exception as e:
    results['clarify'] = {'status': 'ERROR', 'error': str(e)}

# 2. check_service_status
try:
    r = T['check_service_status']('vpn', 'production')
    results['check_service_status'] = {'status': 'PASS' if r.get('service') == 'vpn' else 'FAIL', 'output': r}
except Exception as e:
    results['check_service_status'] = {'status': 'ERROR', 'error': str(e)}

# 3. inspect_device
try:
    r = T['inspect_device']('LT-318', 'vpn')
    results['inspect_device'] = {'status': 'PASS' if r.get('asset_id') == 'LT-318' else 'FAIL', 'output': {'asset_id': r.get('asset_id'), 'check': r.get('check')}}
except Exception as e:
    results['inspect_device'] = {'status': 'ERROR', 'error': str(e)}

# 4. lookup_user
try:
    r = T['lookup_user']('EMP-1007')
    emp = r.get('employee') or {}
    results['lookup_user'] = {'status': 'PASS' if emp.get('employee_id') == 'EMP-1007' else 'FAIL', 'output': {'employee_id': emp.get('employee_id'), 'name': emp.get('display_name')}}
except Exception as e:
    results['lookup_user'] = {'status': 'ERROR', 'error': str(e)}

# 5. search_kb
try:
    r = T['search_kb']('VPN macOS certificate', 'vpn', 2)
    results['search_kb'] = {'status': 'PASS' if 'results' in r and 'trust_boundary' in r else 'FAIL', 'output': {'count': len(r.get('results') or []), 'boundary': r.get('trust_boundary')}}
except Exception as e:
    results['search_kb'] = {'status': 'ERROR', 'error': str(e)}

# 6. policy
try:
    r = T['policy']('dữ liệu nào được gửi ra external tool', 'external_tools', 2)
    results['policy'] = {'status': 'PASS' if 'results' in r and 'trust_boundary' in r else 'FAIL', 'output': {'count': len(r.get('results') or []), 'boundary': r.get('trust_boundary')}}
except Exception as e:
    results['policy'] = {'status': 'ERROR', 'error': str(e)}

# 7. format_incident_report
try:
    r = T['format_incident_report']([{'label': 'VPN', 'detail': 'degraded'}], 'brief', 'VPN incident')
    results['format_incident_report'] = {'status': 'PASS' if r.get('finding_count') == 1 else 'FAIL', 'output': {'finding_count': r.get('finding_count')}}
except Exception as e:
    results['format_incident_report'] = {'status': 'ERROR', 'error': str(e)}

# 8. create_ticket (dry-run with confirmed=False)
try:
    r = T['create_ticket']('VPN dry run', 'low', 'LT-204', False)
    results['create_ticket'] = {'status': 'PASS' if r.get('status') == 'needs_confirmation' else 'FAIL', 'output': {'status': r.get('status'), 'reason': r.get('reason')}}
except Exception as e:
    results['create_ticket'] = {'status': 'ERROR', 'error': str(e)}

# 9. search_device_info (Tavily search)
try:
    r = T['search_device_info']('Lenovo', 'ThinkPad T14 Gen 4', 'drivers', 2)
    if 'error' in r:
        results['search_device_info'] = {'status': 'OPTIONAL_NO_KEY' if 'API key' in str(r.get('error')) else 'FAIL', 'output': r.get('error')}
    else:
        results['search_device_info'] = {'status': 'PASS', 'output': {'items_found': len(r.get('items') or [])}}
except Exception as e:
    results['search_device_info'] = {'status': 'ERROR', 'error': str(e)}

print("\n" + "=" * 60)
print("             KẾT QUẢ KIỂM TRA TOÀN BỘ 9 TOOLS")
print("=" * 60)
for name, data in results.items():
    status = data['status']
    info = data.get('output', data.get('error'))
    print(f"[{status:^15}] {name:<25}: {info}")
print("=" * 60 + "\n")
