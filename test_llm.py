import urllib.request
import json
import sqlite3

db = sqlite3.connect(r"G:\AiLog\backend\loginsight.db")
row = db.execute("SELECT api_base, api_key, model_name FROM llm_configs WHERE is_default = 1 LIMIT 1").fetchone()
db.close()

if not row:
    print("❌ 数据库里没有找到默认模型配置！")
    exit(1)

api_base, api_key, model_name = row
print(f"API Base: {api_base}")
print(f"Model: {model_name}")
print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
print()

url = api_base.rstrip("/") + "/chat/completions"
print(f"请求URL: {url}")
print()

payload = {
    "model": model_name,
    "messages": [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好，请用一句话介绍自己"},
    ],
    "temperature": 0.3,
    "max_tokens": 200,
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print("✅ 请求成功！")
        print(f"回复: {data['choices'][0]['message']['content']}")
except urllib.error.HTTPError as e:
    print(f"❌ HTTP {e.code} 错误")
    body = e.read().decode()
    print(f"响应体: {body}")
except Exception as e:
    print(f"❌ 其他错误: {e}")
