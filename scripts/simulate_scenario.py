import sys
import os
import requests
import json
import time

API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')

def run_simulation():
    print(f"[*] Starting Cargo Tracking System Simulation against {API_BASE_URL}...")
    
    # 1. Health check
    try:
        res = requests.get(f"{API_BASE_URL}/", headers={"Accept": "application/json"})
        print(f"[+] API Status: {res.status_code}")
    except Exception as e:
        print(f"[-] Could not connect to API at {API_BASE_URL}: {e}")
        print("[-] Please ensure Flask API is running (e.g. python run.py or docker compose up -d)")
        return False

    # 2. Create 20 Cargos
    print("\n--- STEP 1: Creating 20 Cargos ---")
    created_ids = []
    for i in range(1, 21):
        tracking_num = f"KRG-{1000 + i}"
        payload = {
            "tracking_number": tracking_num,
            "sender": f"Musteri-{i}",
            "receiver": f"Alici-{i}"
        }
        res = requests.post(f"{API_BASE_URL}/cargo", json=payload)
        if res.status_code == 201:
            cargo = res.json()
            created_ids.append(cargo['id'])
            print(f"[+] Created Cargo ID {cargo['id']}: Tracking {tracking_num}")
        else:
            print(f"[-] Failed to create {tracking_num}: {res.text}")

    # 3. Update 10 Cargos to IN_TRANSIT (IDs 1 to 10)
    print("\n--- STEP 2: Updating 10 Cargos to IN_TRANSIT ---")
    for cid in created_ids[:10]:
        res = requests.put(f"{API_BASE_URL}/cargo/{cid}/status", json={"status": "IN_TRANSIT"})
        if res.status_code == 200:
            print(f"[+] Cargo ID {cid} -> IN_TRANSIT")
        else:
            print(f"[-] Failed status update for ID {cid}: {res.text}")

    # 4. Update 5 Cargos to DELIVERED (IDs 1 to 5)
    print("\n--- STEP 3: Updating 5 Cargos to DELIVERED ---")
    for cid in created_ids[:5]:
        res = requests.put(f"{API_BASE_URL}/cargo/{cid}/status", json={"status": "DELIVERED"})
        if res.status_code == 200:
            print(f"[+] Cargo ID {cid} -> DELIVERED (Notification sent)")
        else:
            print(f"[-] Failed delivery for ID {cid}: {res.text}")

    # 5. Update 2 Cargos to CANCELLED (IDs 19 and 20)
    print("\n--- STEP 4: Updating 2 Cargos to CANCELLED ---")
    for cid in created_ids[18:20]:
        res = requests.put(f"{API_BASE_URL}/cargo/{cid}/status", json={"status": "CANCELLED"})
        if res.status_code == 200:
            print(f"[+] Cargo ID {cid} -> CANCELLED")
        else:
            print(f"[-] Failed cancellation for ID {cid}: {res.text}")

    # 6. Check Metrics
    print("\n--- STEP 5: Checking Prometheus Metrics ---")
    try:
        metrics_res = requests.get(f"{API_BASE_URL}/metrics")
        lines = metrics_res.text.splitlines()
        print("[+] Relevant Metrics Snapshot:")
        for line in lines:
            if any(k in line for k in ["cargo_created_total", "cargo_delivered_total", "cargo_cancelled_total", "cargo_status_changed_total"]) and not line.startswith('#'):
                print(f"    {line}")
    except Exception as e:
        print(f"[-] Error reading metrics: {e}")

    print("\n[SUCCESS] Simulation completed successfully!")
    return True

if __name__ == '__main__':
    run_simulation()
