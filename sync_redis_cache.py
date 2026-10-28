import json
import redis

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
with open('static/data/glance_cache.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

r.set('cache:country_glance_data:data', json.dumps(data))
print("Successfully synced country_glance_data to Redis!")
print("National Avg in Redis:", data.get('national_avg'))
