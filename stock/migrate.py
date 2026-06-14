import sqlite3

src = sqlite3.connect('J:/zss/stock/data/one-api/one-api.db')
dst = sqlite3.connect('J:/zss/stock/new-api/data/one-api.db')
sc = src.cursor()
dc = dst.cursor()

# Clean
dc.execute('DELETE FROM tokens')
dc.execute('DELETE FROM channels')
dc.execute('DELETE FROM users')
dst.commit()

# === Users ===
sc.execute("""SELECT id, username, password, display_name, role, status,
    email, github_id, oidc_id, wechat_id, access_token, quota, used_quota,
    request_count, "group", aff_code, inviter_id FROM users""")
for r in sc.fetchall():
    vals = list(r)
    # Ensure non-null strings
    for i in [3,6,7,8,9,11,14,15]:  # string fields
        if vals[i] is None: vals[i] = ''
    new_vals = [
        vals[0],  # 0: id
        vals[1],  # 1: username
        vals[2],  # 2: password
        vals[3] or '',  # 3: display_name
        vals[4],  # 4: role
        vals[5],  # 5: status
        vals[6] or '',  # 6: email
        vals[7] or '',  # 7: github_id
        '',       # 8: discord_id
        vals[8] or '',  # 9: oidc_id
        vals[9] or '',  # 10: wechat_id
        '',       # 11: telegram_id
        vals[10] or '', # 12: access_token
        vals[11], # 13: quota
        vals[12], # 14: used_quota
        vals[13], # 15: request_count
        vals[14] or 'default', # 16: group
        vals[15] or '', # 17: aff_code
        0,        # 18: aff_count
        0,        # 19: aff_quota
        0,        # 20: aff_history
        vals[16] or 0, # 21: inviter_id
        None,     # 22: deleted_at
        '',       # 23: linux_do_id
        '',       # 24: setting
        '',       # 25: remark
        '',       # 26: stripe_customer
        None,     # 27: created_at
        0,        # 28: last_login_at
    ]
    assert len(new_vals) == 29, f"Expected 29, got {len(new_vals)}"
    dc.execute("INSERT INTO users VALUES(" + ",".join(["?"]*29) + ")", new_vals)
print('Users OK')

# === Channels ===
sc.execute("""SELECT id, type, key, status, name, weight, created_time,
    test_time, response_time, base_url, other, balance, balance_updated_time,
    models, "group", used_quota, model_mapping, priority, config, system_prompt
    FROM channels""")
for r in sc.fetchall():
    vals = list(r)
    # Map one-api fields to new-api fields (30 columns total)
    new_vals = [
        vals[0],   # 0: id
        vals[1],   # 1: type
        vals[2],   # 2: key
        '',        # 3: open_ai_organization
        '',        # 4: test_model
        vals[3],   # 5: status
        vals[4],   # 6: name
        vals[5],   # 7: weight
        vals[6],   # 8: created_time
        vals[7],   # 9: test_time
        vals[8],   # 10: response_time
        vals[9] or '',   # 11: base_url
        vals[10] or '',  # 12: other
        vals[11] or 0,   # 13: balance
        vals[12] or 0,   # 14: balance_updated_time
        vals[13] or '',  # 15: models
        vals[14] or 'default', # 16: group
        vals[15] or 0,   # 17: used_quota
        vals[16] or '',  # 18: model_mapping
        '',        # 19: status_code_mapping
        vals[17] or 0,   # 20: priority
        1,         # 21: auto_ban
        '',        # 22: other_info
        '',        # 23: tag
        '',        # 24: setting
        '',        # 25: param_override
        '',        # 26: header_override
        '',        # 27: remark
        None,      # 28: channel_info
        '',        # 29: settings
    ]
    assert len(new_vals) == 30, f"Expected 30, got {len(new_vals)}"
    dc.execute("INSERT INTO channels VALUES(" + ",".join(["?"]*30) + ")", new_vals)
print('Channels OK')

# === Tokens ===
sc.execute("""SELECT id, user_id, key, status, name, created_time,
    accessed_time, expired_time, remain_quota, unlimited_quota, used_quota,
    models, subnet FROM tokens""")
for r in sc.fetchall():
    vals = list(r)
    unlimited = vals[9]
    if isinstance(unlimited, str):
        unlimited = 1 if unlimited.lower() == 'true' else 0
    unlimited = int(unlimited or 0)

    new_vals = [
        vals[0],   # 0: id
        vals[1],   # 1: user_id
        vals[2],   # 2: key
        vals[3],   # 3: status
        vals[4],   # 4: name
        vals[5] or 0,  # 5: created_time
        vals[6] or 0,  # 6: accessed_time
        vals[7] or -1, # 7: expired_time
        vals[8] or 0,  # 8: remain_quota
        unlimited,  # 9: unlimited_quota
        0,         # 10: model_limits_enabled
        vals[11] or '', # 11: model_limits (was 'models' in one-api)
        vals[12] or '', # 12: allow_ips (was 'subnet' in one-api)
        vals[10] or 0,  # 13: used_quota
        '',        # 14: group
        0,         # 15: cross_group_retry
        None,      # 16: deleted_at
    ]
    assert len(new_vals) == 17, f"Expected 17, got {len(new_vals)}"
    dc.execute("INSERT INTO tokens VALUES(" + ",".join(["?"]*17) + ")", new_vals)
print('Tokens OK')

dst.commit()

for t in ['users', 'channels', 'tokens']:
    dc.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"{t}: {dc.fetchone()[0]}")

dc.close()
src.close()
print('Done!')
