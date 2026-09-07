import json, redis
r = redis.Redis(host='localhost', port=6379, db=0)
with open('static/data/state_glance_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
for k, v in d.items():
    r.set(f'state_glance:{k}', json.dumps(v))
print('Synced all states to Redis!')
