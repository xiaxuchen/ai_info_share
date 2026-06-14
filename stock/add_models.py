import subprocess

models_sql = """
INSERT IGNORE INTO models (model_name, description, vendor_id, status, sync_official) VALUES
("deepseek-v4-flash", "DeepSeek V4 Flash", 1, 1, 0),
("deepseek-v4-pro", "DeepSeek V4 Pro", 1, 1, 0),
("Qwen/Qwen3-32B", "Qwen3 32B", 2, 1, 0),
("deepseek-ai/DeepSeek-V3.2", "DeepSeek V3.2", 2, 1, 0)
"""

result = subprocess.run(
    ["docker", "exec", "-i", "new-api-mysql", "mysql", "-uroot", "-pnewapi123456", "new-api"],
    input=models_sql, capture_output=True, text=True
)
print("Models insert:", "OK" if result.returncode == 0 else result.stderr[:200])

result2 = subprocess.run(
    ["docker", "exec", "new-api-mysql", "mysql", "-uroot", "-pnewapi123456", "new-api", "-e", "SELECT model_name FROM models"],
    capture_output=True, text=True
)
print(result2.stdout)
