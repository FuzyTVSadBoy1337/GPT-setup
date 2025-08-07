# === FILE: tool_rejoin.py ===
#!/usr/bin/env python3
import os
import time
import json
import subprocess
import xml.etree.ElementTree as ET

# Advanced monitoring via psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# --- CONFIG ---
ACCOUNT_FILE     = '/sdcard/Download/accounts.json'
WORKSPACE_REPORT = '/sdcard/RonixExploit/workspace/Report Rejoin'
CHECK_INTERVAL   = 3     # seconds between checks
HEART_STALE      = 30    # seconds stale heartbeat threshold
TELEPORT_TIMEOUT = 60    # seconds teleport timeout
CPU_IDLE_TIMEOUT = 10    # seconds to consider idle
CPU_THRESHOLD    = 5.0   # percent CPU threshold
RAM_THRESHOLD    = 50.0  # MB RAM threshold
PREFIX_DEFAULT   = 'com.roblox'

# --- UTIL FUNCTIONS ---

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')


def save_accounts(data):
    os.makedirs(os.path.dirname(ACCOUNT_FILE), exist_ok=True)
    with open(ACCOUNT_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"[✓] Saved {len(data)} accounts to {ACCOUNT_FILE}")


def load_accounts():
    if not os.path.exists(ACCOUNT_FILE):
        return {}
    with open(ACCOUNT_FILE) as f:
        return json.load(f)


def list_packages(prefix):
    out = subprocess.getoutput('pm list packages').splitlines()
    return [l.split(':')[1] for l in out if l.startswith('package:' + prefix)]


def read_username(pkg):
    prefs = f'/data/data/{pkg}/shared_prefs/prefs.xml'
    if not os.path.exists(prefs):
        return None
    try:
        tree = ET.parse(prefs)
        for e in tree.getroot().findall('string'):
            if e.attrib.get('name','').lower() == 'username':
                return e.text
    except:
        pass
    return None

# --- MENU FUNCTIONS ---

def start_auto_rejoin():
    clear_screen()
    print("Starting Auto Rejoin...
")
    auto_rejoin()


def select_package_run():
    clear_screen()
    print("Select Package to Run (3rd-party, prefix com.roblox first):
")
    # list third-party packages
    out = subprocess.getoutput('pm list packages -3').splitlines()
    pkgs = [l.split(':')[1] for l in out]
    # prioritize prefix
    prefix = PREFIX_DEFAULT
    roblox = [p for p in pkgs if p.startswith(prefix)]
    others = [p for p in pkgs if not p.startswith(prefix)]
    all_pkgs = roblox + others
    for i,p in enumerate(all_pkgs,1): print(f"{i}. {p}")
    choice = input("Enter number: ").strip()
    try:
        idx = int(choice)-1
        pkg = all_pkgs[idx]
    except:
        print("Invalid selection.")
        time.sleep(1)
        return
    user = read_username(pkg)
    if not user:
        print(f"No prefs.xml or username for {pkg}.")
        time.sleep(1)
        return
    gid = input(f"Enter Game ID for '{user}' (package {pkg}): ").strip()
    accs = load_accounts()
    accs[user] = {'pkg': pkg, 'gid': gid}
    save_accounts(accs)
    input("Saved. Press Enter to continue...")


def list_accounts():
    clear_screen()
    print("Configured Accounts:
")
    accs = load_accounts()
    if not accs:
        print("None configured.")
    else:
        for user,info in accs.items():
            print(f"- {user}: package={info['pkg']}, gameID={info['gid']}")
    input("
Press Enter to return to menu...")


def auto_select_package_run():
    # auto select all packages with com.roblox prefix
    prefix = PREFIX_DEFAULT
    pkgs = list_packages(prefix)
    accounts = load_accounts()
    for pkg in pkgs:
        user = read_username(pkg)
        if not user:
            continue
        gid = input(f"Enter Game ID for '{user}' (package {pkg}): ").strip()
        accounts[user] = {'pkg': pkg, 'gid': gid}
    save_accounts(accounts)
    input("Press Enter to return to menu...")("Add another? (y/n): ").strip().lower()
        if cont != 'y': break


def set_android_id():
    clear_screen()
    aid = input("Enter desired Android ID: ").strip()
    if not aid:
        print("No ID entered, cancel.")
    else:
        subprocess.call(f"su -c 'settings put secure android_id {aid}'", shell=True)
        print(f"Android ID set to: {aid}")
    input("Press Enter to return to menu...")("Press Enter to return to menu...")

# --- MAIN MENU ---
if __name__ == '__main__':
    while True:
        clear_screen()
        print("+---------------- Roblox Rejoin Tool ---------------+")
        print(f"| 1) Start Auto Rejoin")
        print(f"| 2) Select Package Run")
        print(f"| 3) List Accounts")
        print(f"| 4) Auto Select Package Run")
        print(f"| 5) Set Android ID")
        print("| 0) Exit")
        print("+----------------------------------------------------+")
        choice = input("Enter choice: ").strip()
        if choice == '1':
            start_auto_rejoin()
        elif choice == '2':
            select_package_run()
        elif choice == '3':
            list_accounts()
        elif choice == '4':
            auto_select_package_run()
        elif choice == '5':
            set_android_id()
        elif choice == '0':
            auto_set_android_id()
        elif choice == '0':
            break
        else:
            print("Invalid choice.")
            time.sleep(1)
            