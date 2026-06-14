import subprocess, json

channel_info = json.dumps({
    "is_multi_key": False,
    "multi_key_size": 0,
    "multi_key_status_list": {},
    "multi_key_polling_index": 0,
    "multi_key_mode": ""
})
print("Fixed channel_info:", channel_info)

# Use parameterized approach - write SQL file then pipe
sql = "UPDATE channels SET channel_info = '%s';" % channel_info.replace("'", "''")
print("SQL:", sql)

result = subprocess.run(
    ["docker", "exec", "-i", "new-api-mysql", "mysql", "-uroot", "-pnewapi123456", "new-api"],
    input=sql, capture_output=True, text=True
)
if result.returncode != 0:
    print("Error:", result.stderr[:300])
else:
    print("Updated!")

# Verify
result2 = subprocess.run(
    ["docker", "exec", "-i", "new-api-mysql", "mysql", "-uroot", "-pnewapi123456", "new-api", "-e", "SELECT channel_info FROM channels LIMIT 1"],
    capture_output=True, text=True
)
print("Verify:", result2.stdout[:200])

subprocess.run(["docker", "restart", "new-api"], capture_output=True)
print("Restarted, waiting...")
import time; time.sleep(6)
