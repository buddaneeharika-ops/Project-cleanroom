import json
import redis

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
with open('static/data/glance_cache.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

r.set('cache:country_glance_data:data', json.dumps(data))
print("Successfully synced country_glance_data to Redis!")
print("National Avg in Redis:", data.get('national_avg'))

with open('static/data/state_glance_cache.json', 'r', encoding='utf-8') as f:
    sg_data = json.load(f)

for state_abb, s_data in sg_data.items():
    r.set(f'state_glance:{state_abb}', json.dumps(s_data))

print(f"Successfully synced {len(sg_data)} state_glance:* keys to Redis!")
