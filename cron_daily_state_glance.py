import os
import subprocess
import time
import json
import redis

def sync_json_to_redis():
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Syncing JSON Caches to Redis...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=2)
        r.ping()
    except Exception as e:
        print(f"[WARN] Redis is not running or accessible. Dashboards will safely fallback to JSON. ({e})")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Sync State Glance Cache
    state_file = os.path.join(base_dir, 'static', 'data', 'state_glance_cache.json')
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for state_abb, state_data in data.items():
                    r.set(f"state_glance:{state_abb}", json.dumps(state_data))
            print(f"[OK] Synced {len(data)} states to Redis (state_glance:*)")
        except Exception as e:
            print(f"[ERROR] Failed to sync state glance to Redis: {e}")

    # Sync Country Glance Cache
    country_file = os.path.join(base_dir, 'static', 'data', 'glance_cache.json')
    if os.path.exists(country_file):
        try:
            with open(country_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                r.set('cache:country_glance_data:data', json.dumps(data))
            print(f"[OK] Synced Country Glance to Redis")
        except Exception as e:
            print(f"[ERROR] Failed to sync country glance to Redis: {e}")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Redis Sync Complete!")

def run_nightly_aggregation():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Nightly State Glance Aggregation...")
    
    scripts = [
        # 1. Base Data (LGD, Joshua, Ejal, etc.)
        ("scratch_build_state_data.py", "Building Base Data"),
        
        # 2. Form 20 Heavy Aggregation (~40 mins)
        ("scratch_patch_form20.py", "Aggregating Form 20 Data"),
        
        # 3. True Booth Counts
        ("scratch_fix_booths.py", "Updating True Booth Counts"),
        
        # 4. True Zone Populations
        ("scratch_patch_true_zones.py", "Mapping True Zone Populations"),
        
        # 5. True Granular Coverage
        ("scratch_patch_granular_coverage.py", "Calculating True LGD Coverage"),
        
        # 6. By-Polls and Quality Remarks
        ("scratch_master_patch.py", "Finalizing By-Polls & Remarks"),

        # 7. Generate Country Glance Cache
        ("generate_glance_data.py", "Generating Country Glance Cache")
    ]
    
    for script, description in scripts:
        print(f"\n---> {description} ({script})")
        start_t = time.time()
        
        try:
            subprocess.run(
                ["python3" if os.name != 'nt' else "python", script], 
                cwd=os.path.dirname(os.path.abspath(__file__)),
                check=True
            )
            print(f"[OK] Completed in {round(time.time() - start_t, 2)}s")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Script {script} failed with exit code {e.returncode}")

    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Nightly Aggregation Scripts Finished!")
    
    # 7. Push newly built JSON files into Redis for fast in-memory access
    sync_json_to_redis()

if __name__ == "__main__":
    run_nightly_aggregation()
