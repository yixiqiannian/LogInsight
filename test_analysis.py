import urllib.request
import json

result = urllib.request.urlopen("http://localhost:8000/api/logs?level=error&page_size=1").read().decode()
data = json.loads(result)
log_id = data["items"][0]["id"]
print(f"测试日志 ID: {log_id}")
print(f"日志内容: {data['items'][0]['message'][:80]}...")
print()

print("=== 触发分析 (force=true) ===")
req = urllib.request.Request(
    f"http://localhost:8000/api/analysis/log/{log_id}?force=true",
    data=b"",
    method="POST"
)
resp = urllib.request.urlopen(req).read().decode()
result_data = json.loads(resp)
print(f"返回结构 keys: {list(result_data.keys())}")
print(f"analysis status: {result_data['analysis']['status']}")
print(f"analysis model_used: {result_data['analysis'].get('model_used', 'N/A')}")
print(f"summary: {(result_data['analysis'].get('summary') or '')[:100]}")
print()
print("=== 2秒后再 GET 一次 ===")
import time
time.sleep(2)
resp2 = urllib.request.urlopen(f"http://localhost:8000/api/analysis/log/{log_id}").read().decode()
get_data = json.loads(resp2)
print(f"GET status: {get_data['status']}")
print(f"GET model_used: {get_data.get('model_used', 'N/A')}")
print(f"GET summary: {(get_data.get('summary') or '')[:100]}")
