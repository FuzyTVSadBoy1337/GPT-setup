#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-Tool Termux — Full tool
- accounts.json keyed by UserID
- configs.json for all settings (webhook, device name, icon, intervals)
- installs Lua autoexec that writes workspace/status_<UID>.log
- monitors logs and rejoin on SEVERE (30s first-delay, cooldown)
- periodic System Status webhook with screenshot + embed matching sample
"""

import os, sys, time, json, random, threading, queue, subprocess, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# Optional libs
try:
    import requests
except Exception:
    requests = None
try:
    import psutil
except Exception:
    psutil = None

# --- Paths & defaults ---
WORKDIR = "/sdcard/Download/GPT-Tool"   # local workspace for screenshots etc
CONFIG_FILE = os.path.join(WORKDIR, "configs.json")
ACCOUNTS_FILE = os.path.join(WORKDIR, "accounts.json")

# Default executor workspace (where autoexec / workspace mapping lives)
DEFAULT_EXEC_WS = "/sdcard/RonixExploit"

AUTOEXEC_DIRS = [
    os.path.join(DEFAULT_EXEC_WS, "autoexec"),
    os.path.join(DEFAULT_EXEC_WS, "Autoexec"),
    os.path.join(DEFAULT_EXEC_WS, "autoexec/"),
]

REPORT_DIRNAME = "Rejoin Report"   # folder inside executor workspace
LUA_FILENAME = "rejoin_autoexec.lua"

# default config
DEFAULT_CONFIG = {
    "package_prefix": "com.roblox",
    "exec_workspace": DEFAULT_EXEC_WS,
    "webhook_url": "",
    "device_name": "GPT-Tool Device",
    # default ChatGPT-ish icon (changeable)
    "icon_url": "https://i.imgur.com/kOeJ8zr.png",
    "report_interval_min": 10,      # minutes
    "first_rejoin_delay": 30,       # seconds (first rejoin per UID)
    "heartbeat_stale": 45,          # seconds
    "send_screenshot": True,
    "screenshot_path": os.path.join(WORKDIR, "screenshot.png")
}

# Rejoin behavior constants (fallbacks; values read from config at runtime too)
DEFAULT_HEARTBEAT_INTERVAL = 20   # lua heartbeat period
DEFAULT_REJOIN_COOLDOWN = 20      # seconds between rejoins for same UID

# utility
def ensure_dir(p):
    if not p:
        return
    os.makedirs(p, exist_ok=True)

def sh(cmd):
    return subprocess.call(cmd, shell=True)

def shout(cmd):
    try:
        return subprocess.getoutput(cmd)
    except Exception:
        return ""

def load_json(path, default=None):
    try:
        if not os.path.exists(path):
            return default if default is not None else {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# config/accounts
def load_config():
    cfg = load_json(CONFIG_FILE, {})
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg or {})
    # normalize numeric fields
    try:
        merged["report_interval_min"] = int(merged.get("report_interval_min", DEFAULT_CONFIG["report_interval_min"]))
    except Exception:
        merged["report_interval_min"] = DEFAULT_CONFIG["report_interval_min"]
    try:
        merged["first_rejoin_delay"] = int(merged.get("first_rejoin_delay", DEFAULT_CONFIG["first_rejoin_delay"]))
    except Exception:
        merged["first_rejoin_delay"] = DEFAULT_CONFIG["first_rejoin_delay"]
    try:
        merged["heartbeat_stale"] = int(merged.get("heartbeat_stale", DEFAULT_CONFIG["heartbeat_stale"]))
    except Exception:
        merged["heartbeat_stale"] = DEFAULT_CONFIG["heartbeat_stale"]
    return merged

def save_config(cfg):
    save_json(CONFIG_FILE, cfg)
    print(f"[✓] Saved config to {CONFIG_FILE}")

def load_accounts():
    return load_json(ACCOUNTS_FILE, {})

def save_accounts(accounts):
    save_json(ACCOUNTS_FILE, accounts)
    print(f"[✓] Saved {len(accounts)} accounts to {ACCOUNTS_FILE}")

# --- Read username and userid from pkg prefs.xml ---
def read_user_from_prefs(pkg_name):
    prefs = f"/data/data/{pkg_name}/shared_prefs/prefs.xml"
    if not os.path.exists(prefs):
        return None, None
    try:
        tree = ET.parse(prefs)
        root = tree.getroot()
        uname = None
        uid = None
        # common keys: username, UserId or userid
        for e in root.findall("string"):
            n = e.attrib.get("name", "").lower()
            if n == "username":
                uname = (e.text or "").strip()
            if n in ("userid", "user_id", "userId".lower()):
                uid = (e.text or "").strip()
        for e in root.findall("int"):
            n = e.attrib.get("name", "").lower()
            if n in ("userid", "user_id"):
                uid = str(e.attrib.get("value", ""))
        return uname, uid
    except Exception:
        return None, None

# --- Lua autoexec content (writes to workspace/status_<UID>.log) ---
LUA_SCRIPT = r'''-- rejoin_autoexec.lua (auto-generated)
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local CoreGui = game:GetService("CoreGui")
local RunService = game:GetService("RunService")
local TeleportService = game:GetService("TeleportService")

local player = Players.LocalPlayer
local username = (player and player.Name) or ("unknown_" .. tostring(math.random(1000,9999)))
local userid = (player and player.UserId) or 0
local logfile = "workspace/status_" .. tostring(userid) .. ".log"

local function jencode(t)
  local ok, s = pcall(function() return HttpService:JSONEncode(t) end)
  return ok and s or nil
end

local function write_status(event, code, severity, details)
  local rec = {
    t = os.time(),
    user = username,
    uid = userid,
    event = event,
    code = code or "",
    severity = severity or "INFO",
    details = details or {}
  }
  local line = jencode(rec)
  if line then
    pcall(function()
      appendfile(logfile, line .. "\n")
    end)
  end
end

-- heartbeat: RUNNING every 20s
task.spawn(function()
  while task.wait(20) do
    local fps = 0
    pcall(function() fps = math.floor(workspace:GetRealPhysicsFPS() or 0) end)
    write_status("RUNNING", "OK", "INFO", {fps = fps})
  end
end)

-- Teleport events
pcall(function()
  TeleportService.TeleportInitFailed:Connect(function(placeId, reason)
    write_status("ERROR", tostring(reason), "MINOR", {during = "teleport"})
  end)
  TeleportService.TeleportStart:Connect(function()
    write_status("TELEPORT_BEGIN", "", "INFO", {})
  end)
  TeleportService.TeleportStateChanged:Connect(function(state)
    write_status("TELEPORT_END", tostring(state), "INFO", {})
  end)
end)

-- CoreGui error prompts (kick/disconnect or minor)
pcall(function()
  CoreGui.ChildAdded:Connect(function(child)
    local txt = ""
    pcall(function()
      if child and child.FindFirstChild then
        local e = child:FindFirstChild("ErrorMessage") or child:FindFirstChild("Message")
        if e and e.Text then txt = e.Text end
      end
    end)
    if txt ~= "" then
      local lower = string.lower(tostring(txt))
      if string.find(lower, "kick") or string.find(lower, "lost connection") or string.find(lower, "disconnected") then
        write_status("ERROR", "KICK_OR_DISCONNECT", "SEVERE", {msg = txt})
      else
        write_status("ERROR", "GUI_ERROR", "MINOR", {msg = txt})
      end
    end
  end)
end)

-- Player removed => likely kick
pcall(function()
  player.AncestryChanged:Connect(function(_, parent)
    if parent == nil then
      write_status("KICK", "PLAYER_REMOVED", "SEVERE", {})
    end
  end)
end)

-- BindToClose -> Crash / Shutdown
pcall(function()
  game:BindToClose(function()
    write_status("CRASH", "BIND_CLOSE", "SEVERE", {})
  end)
end)

-- Heartbeat stale detection (if main thread stops)
local last = tick()
RunService.Heartbeat:Connect(function() last = tick() end)
task.spawn(function()
  while task.wait(60) do
    if tick() - last > 120 then
      write_status("ERROR", "HEARTBEAT_STALE", "SEVERE", {})
    end
  end
end)

-- initial record
write_status("RUNNING", "INIT_OK", "INFO", {})
'''

def install_lua(autoexec_dirs=None):
    if autoexec_dirs is None:
        autoexec_dirs = AUTOEXEC_DIRS
    written = []
    for d in autoexec_dirs:
        try:
            ensure_dir(d)
            target = os.path.join(d, LUA_FILENAME)
            with open(target, "w", encoding="utf-8") as f:
                f.write(LUA_SCRIPT)
            written.append(target)
        except Exception as e:
            print("[!] Failed write lua to", d, ":", e)
    # ensure report dir exists in executor workspace
    cfg = load_config()
    exec_ws = cfg.get("exec_workspace", DEFAULT_EXEC_WS)
    ensure_dir(os.path.join(exec_ws, REPORT_DIRNAME))
    return written

# --- Helper: count roblox processes (best-effort) ---
def count_roblox_processes_and_list(pkg_prefix=None):
    accounts = load_accounts()
    running = []
    stopped = []
    for uid, info in accounts.items():
        pkg = info.get("pkg")
        if not pkg:
            stopped.append(f"{uid} ({info.get('username','')}) - no pkg")
            continue

        # dùng ps -ef để chắc chắn có tên process
        psout = shout(f"ps -ef | grep {pkg} | grep -v grep")
        if psout.strip():
            running.append(f"{uid} ({info.get('username','')}) - {pkg}")
        else:
            stopped.append(f"{uid} ({info.get('username','')}) - {pkg}")
    return running, stopped

# --- Screenshot helper ---
def capture_screenshot(cfg):
    path = cfg.get("screenshot_path", DEFAULT_CONFIG["screenshot_path"])
    ensure_dir(os.path.dirname(path))
    # try adb first (requires adb host), else try local screencap (on device)
    try:
        code = sh(f"adb exec-out screencap -p > '{path}'")
        if code == 0 and os.path.exists(path):
            return path
    except Exception:
        pass
    # fallback: local screencap
    try:
        code = sh(f"screencap -p '{path}'")
        if code == 0 and os.path.exists(path):
            return path
    except Exception:
        pass
    return None

# --- Webhook sender (full embed + optional screenshot) ---
def send_status_webhook(cfg=None):
    if requests is None:
        print("[!] requests module missing; webhook disabled (pip install requests).")
        return False
    cfg = cfg or load_config()
    url = cfg.get("webhook_url", "").strip()
    if not url:
        # not configured
        return False
    device = cfg.get("device_name", "GPT-Tool Device")
    icon = cfg.get("icon_url", DEFAULT_CONFIG["icon_url"])
    # sys info
    uptime = str(datetime.now() - start_time).split('.')[0]
    cpu = 0.0
    mem_total_g = mem_used_g = mem_percent = 0.0
    tool_mem_mb = 0.0
    if psutil:
        cpu = psutil.cpu_percent(interval=0.5)
        vm = psutil.virtual_memory()
        mem_total_g = round(vm.total / (1024**3), 2)
        mem_used_g = round(vm.used / (1024**3), 2)
        mem_percent = vm.percent
        proc = psutil.Process(os.getpid())
        tool_mem_mb = round(proc.memory_info().rss / (1024**2), 2)
    # roblox processes
    running, stopped = count_roblox_processes_and_list(cfg.get("package_prefix"))
    roblox_count = len(running)
status_text = f"🟢 {roblox_count} Roblox instance(s) running" if roblox_count > 0 else "🔴 All stopped"
    # accounts details
    accounts = load_accounts()
    if accounts:
        acc_lines = []
        for uid, info in accounts.items():
            acc_lines.append(f"{uid} ({info.get('username','')}) — {info.get('pkg','')} — game {info.get('gid','')}")
        acc_text = "\n".join(acc_lines)
    else:
        acc_text = "None"
    # build embed
    fields = []
    fields.append({"name":"📱 Device","value":device,"inline":False})
    fields.append({"name":"💾 Total Memory","value":f"{mem_total_g} GB","inline":True})
    fields.append({"name":"⏱️ Uptime","value":uptime,"inline":True})
    fields.append({"name":"⚡ CPU Usage","value":f"{cpu} %","inline":True})
    fields.append({"name":"🧠 Memory Usage","value":f\"{mem_used_g} GB ({mem_percent}%)\",\"inline\":True})
    fields.append({"name":"🛠️ Tool Memory Usage","value":f\"{tool_mem_mb} MB\",\"inline\":True})
    fields.append({"name":"🎮 Total Roblox Processes","value":f\"Running: {roblox_count}\",\"inline\":False})
    fields.append({"name":"🔍 Roblox Details","value":acc_text[:1024] if acc_text else \"None\",\"inline\":False})
    fields.append({"name":"✅ Status","value":status_text,\"inline\":False})
    embed = {
        "title":"📊 System Status Monitor",
        "description":f"Real-time report for **{device}**",
        "color": 0x2ecc71 if roblox_count>0 else 0xe74c3c,
        "fields": fields,
        "footer": {"text": "Made with 💚 by GPT TOOL", "icon_url": icon},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    payload = {
        "username": "GPT TOOL",
        "avatar_url": icon,
        "embeds": [embed]
    }
    files = None
    # attach screenshot if enabled
    if cfg.get("send_screenshot", True):
        sc_path = capture_screenshot(cfg)
        if sc_path and os.path.exists(sc_path):
            try:
                files = {"file": (os.path.basename(sc_path), open(sc_path, "rb"), "image/png")}
                # embed image attachment
                embed["image"] = {"url": f"attachment://{os.path.basename(sc_path)}"}
            except Exception as e:
                print("[!] Failed attach screenshot:", e)
                files = None
    # send
    try:
        if files:
            res = requests.post(url, data={"payload_json": json.dumps(payload)}, files=files, timeout=15)
        else:
            res = requests.post(url, json=payload, timeout=15)
        print("[Webhook] HTTP", getattr(res, "status_code", None))
        return 200 <= getattr(res, "status_code", 0) < 300
    except Exception as e:
        print("[!] Webhook send error:", e)
        return False

# --- Monitor class: follow logs and decide rejoin ---
class RejoinMonitor:
    def __init__(self, cfg):
        self.cfg = cfg
        self.exec_ws = cfg.get("exec_workspace", DEFAULT_EXEC_WS)
        self.report_dir = os.path.join(self.exec_ws, REPORT_DIRNAME)
        ensure_dir(self.report_dir)
        self.accounts = load_accounts()
        self.q = queue.Queue()
        self.stop = threading.Event()
        self.last_action = {}    # uid -> timestamp of last rejoin
        self.first_rejoined = {} # uid -> bool
        self.last_seen = {}      # uid -> last 't' from log
        self.rejoin_cooldown = DEFAULT_REJOIN_COOLDOWN
        self.first_delay = cfg.get("first_rejoin_delay", DEFAULT_CONFIG["first_rejoin_delay"])
        self.heartbeat_stale = cfg.get("heartbeat_stale", DEFAULT_CONFIG["heartbeat_stale"])
        # start watchers & worker & periodic webhook thread
        self._start_watchers()
        self.worker_t = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_t.start()
        self.webhook_thread = threading.Thread(target=self._periodic_webhook_loop, daemon=True)
        self.webhook_thread.start()

    def _start_watchers(self):
        for uid in list(self.accounts.keys()):
            t = threading.Thread(target=self._follow_file, args=(uid,), daemon=True)
            t.start()

    def _follow_file(self, uid):
        path = os.path.join(self.report_dir, f"status_{uid}.log")
        pos = 0
        if os.path.exists(path):
            try:
                pos = os.path.getsize(path)
            except Exception:
                pos = 0
        while not self.stop.is_set():
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        fh.seek(pos)
                        for ln in fh:
                            ln = ln.strip()
                            if ln:
                                self.q.put((uid, ln))
                        pos = fh.tell()
            except Exception:
                pass
            time.sleep(1)

    def _parse_json_line(self, ln):
        try:
            return json.loads(ln)
        except Exception:
            return None

    def _is_severe(self, rec):
        if not rec:
            return False
        sev = (rec.get("severity","") or "").upper()
        event = (rec.get("event","") or "").upper()
        code = (rec.get("code","") or "").upper()
        if sev == "SEVERE":
            return True
        if event in ("KICK", "CRASH", "DISCONNECT"):
            return True
        if "HEARTBEAT_STALE" in code or "PLAYER_REMOVED" in code:
            return True
        if code.startswith("ERROR_268") or code.startswith("ERROR_277"):
            return True
        return False

    def _schedule_rejoin(self, uid):
        # check cooldown
        last = self.last_action.get(uid, 0)
        if time.time() - last < self.rejoin_cooldown:
            print(f"[i] Skip rejoin {uid}: cooldown")
            return
        # spawn a thread to perform rejoin (so worker can continue)
        threading.Thread(target=self._do_rejoin, args=(uid,), daemon=True).start()

    def _do_rejoin(self, uid):
        info = self.accounts.get(uid, {})
        pkg = info.get("pkg")
        gid = str(info.get("gid","")).strip()
        if not pkg:
            print(f"[!] No pkg for UID {uid}, skip rejoin")
            return
        # first rejoin delay (avoid collision)
        if not self.first_rejoined.get(uid, False):
            d = self.first_delay + random.randint(0,5)
            print(f"[i] First rejoin for {uid}: waiting {d}s before rejoin")
            time.sleep(d)
            self.first_rejoined[uid] = True
        else:
            jitter = random.randint(3,8)
            print(f"[i] Rejoin uid {uid}: jitter {jitter}s")
            time.sleep(jitter)
        # force stop
        print(f"[->] Force-stopping {pkg}")
        try:
            sh(f"su -c 'am force-stop {pkg}'")
        except Exception:
            pass
        time.sleep(0.6)
        launched = False
        # try deep link if gid numeric
        if gid and any(ch.isdigit() for ch in gid):
            deep = f"roblox://placeId={gid}"
            try:
                rc = sh(f"su -c \"am start -a android.intent.action.VIEW -d '{deep}'\"")
                if rc == 0:
                    launched = True
            except Exception:
                pass
        if not launched:
            print(f"[->] Launching package {pkg} via monkey")
            try:
                sh(f"su -c 'monkey -p {pkg} -c android.intent.category.LAUNCHER 1'")
            except Exception:
                pass
        self.last_action[uid] = time.time()

    def _worker_loop(self):
        while not self.stop.is_set():
            try:
                uid, ln = self.q.get(timeout=1)
            except Exception:
                # periodic stale check
                self._check_stale()
                continue
            rec = self._parse_json_line(ln)
            if not rec:
                continue
            # update last seen
            t = int(rec.get("t", time.time()))
            self.last_seen[uid] = t
            # if severe -> schedule rejoin
            if self._is_severe(rec):
                # only schedule rejoin, do not send webhook here (per your request)
                print(f"[!] SEVERE detected for {uid}: {rec.get('event')} / {rec.get('code')}")
                self._schedule_rejoin(uid)
            # else ignore minor/running
            # loop
        print("[i] Worker loop stopped")

    def _check_stale(self):
        # if no new RUNNING heartbeat within heartbeat_stale -> schedule rejoin
        try:
            for uid in list(self.accounts.keys()):
                last = self.last_seen.get(uid, 0)
                if last == 0:
                    continue
                if time.time() - last > self.heartbeat_stale:
                    # cooldown check
                    if time.time() - self.last_action.get(uid, 0) < self.rejoin_cooldown:
                        continue
                   
