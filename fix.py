
import json
with open('static/data/pc_ac_cache.json', 'r') as f:
    d = json.load(f)

with open('static/data/ac_pc_mapping.json', 'r') as f:
    ac_pc = json.load(f)

pc_id_to_ac_count = {}
for ac_key, ac_info in ac_pc['acs'].items():
    pc_id = str(ac_info['pc_id'])
    pc_id_to_ac_count[pc_id] = pc_id_to_ac_count.get(pc_id, 0) + 1

state_pc_to_id = {}
for pc_id, pc_info in ac_pc['pcs'].items():
    key = pc_info['state_abb'] + '|' + str(pc_info['pc_no'])
    state_pc_to_id[key] = str(pc_id)

for metric in ['retro', 'form20']:
    pc_data = d['map_pc_data_' + metric]
    for pc in pc_data:
        key = pc['state_abb'] + '|' + str(pc['pc_no'])
        pc_id = state_pc_to_id.get(key)
        count = pc_id_to_ac_count.get(pc_id, 1)
        if count > 0:
            pc['covered'] = int(round(pc['covered'] / count))
            pc['total'] = int(round(pc['total'] / count))
            if pc['total'] > 0:
                pc['pct'] = round((pc['covered'] / pc['total']) * 100, 2)
            else:
                pc['pct'] = 0

with open('static/data/pc_ac_cache.json', 'w') as f:
    json.dump(d, f, separators=(',', ':'))

print('Cache fixed. Checking Punjab PC 1:')
for pc in d['map_pc_data_retro']:
    if pc['state_abb'] == 'PB' and pc['pc_no'] == 1:
        print(pc)
        break

