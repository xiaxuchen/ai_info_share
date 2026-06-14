import sqlite3
import subprocess
import json

MYSQL_BASE = ['docker', 'exec', '-i', 'new-api-mysql', 'mysql', '-uroot', '-pnewapi123456', 'new-api']

def mysql_exec(sql):
    result = subprocess.run(MYSQL_BASE, input=sql, capture_output=True, text=True)
    if result.returncode != 0 and 'Duplicate entry' not in result.stderr:
        for line in result.stderr.strip().split('\n'):
            if 'Warning' not in line:
                print(f"  MySQL: {line[:200]}")
    return result.returncode == 0

def esc(s):
    """Escape string for MySQL (backslash-escape single quotes)"""
    if s is None:
        return ''
    return str(s).replace('\\', '\\\\').replace("'", "\\'")

src = sqlite3.connect('J:/zss/stock/data/one-api/one-api.db')
sc = src.cursor()

# === Channels ===
print("Migrating channels...")
sc.execute("SELECT id, type, key, status, name, weight, created_time, test_time, response_time, base_url, other, balance, balance_updated_time, models, `group`, used_quota, model_mapping, priority FROM channels")
for r in sc.fetchall():
    cid = r[0]; ct = r[1]; key = r[2]; st = r[3]; nm = r[4]; wt = r[5] or 0
    ctime = r[6] or 0; ttime = r[7] or 0; rtime = r[8] or 0
    burl = r[9] or ''; other = r[10] or ''; bal = r[11] or 0
    btime = r[12] or 0; models = r[13] or ''; grp = r[14] or 'default'
    uq = r[15] or 0; mm = r[16] or ''; pri = r[17] or 0

    ci = esc(json.dumps({
        'is_multi_key': False, 'multi_key_size': 0,
        'multi_key_status_list': {}, 'multi_key_polling_index': 0,
        'multi_key_mode': 0
    }))

    sql = f"""INSERT INTO channels (id, `type`, `key`, status, name, weight, created_time, test_time, response_time, base_url, other, balance, balance_updated_time, models, `group`, used_quota, model_mapping, priority, channel_info, status_code_mapping, settings) VALUES ({cid}, {ct}, '{esc(key)}', {st}, '{esc(nm)}', {wt}, {ctime}, {ttime}, {rtime}, '{esc(burl)}', '{esc(other)}', {bal}, {btime}, '{esc(models)}', '{esc(grp)}', {uq}, '{esc(mm)}', {pri}, '{ci}', '', '{{}}')"""
    mysql_exec(sql)
    print(f"  OK channel {cid}: {nm}")

# === Tokens ===
print("Migrating tokens...")
sc.execute("SELECT id, user_id, key, status, name, created_time, accessed_time, expired_time, remain_quota, unlimited_quota, used_quota, models, subnet FROM tokens")
for r in sc.fetchall():
    tid = r[0]; uid = r[1]; key = r[2]; st = r[3]; nm = r[4] or 'token'
    ctime = r[5] or 0; atime = r[6] or 0; etime = r[7] if r[7] is not None else -1
    rq = r[8] or 0; uq = r[9]; uquota = r[10] or 0; models = r[11] or ''
    subnet = r[12] or ''
    unlimited = 1 if uq in (True, 1, '1', 'true') else 0

    sql = f"""INSERT INTO tokens (id, user_id, `key`, status, name, created_time, accessed_time, expired_time, remain_quota, unlimited_quota, used_quota, model_limits, allow_ips) VALUES ({tid}, {uid}, '{esc(key)}', {st}, '{esc(nm)}', {ctime}, {atime}, {etime}, {rq}, {unlimited}, {uquota}, '{esc(models)}', '{esc(subnet)}')"""
    mysql_exec(sql)
    print(f"  OK token {tid}: {nm}")

# === Update root password ===
sc.execute("SELECT password FROM users WHERE id = 1")
pwd = sc.fetchone()[0]
mysql_exec(f"UPDATE users SET password = '{esc(pwd)}' WHERE id = 1")
print(f"\nRoot password synced")

src.close()
print("Migration complete!")
