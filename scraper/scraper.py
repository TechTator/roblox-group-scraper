from structures import ProxyPool, Proxy, Counter
import threading
import json
import time
import os
import sys
if os.name == "nt":
    import ctypes
try:
    import requests
except:
    requests = None

with open("config.json") as fp:
    _config = json.load(fp)
    THREAD_COUNT = _config["threadCount"]
    DISPLAY_ERRORS = _config.get("displayErrors", True)
    MIN_MEMBER_COUNT = _config.get("minMemberCount")
    IS_LOOPED = _config.get("isLooped", False)
    WEBHOOK_URL = _config.get("webhookUrl")
    RANGE = _config["range"] if len(sys.argv) == 1 else {"min": int(sys.argv[1]), "max": int(sys.argv[2])}
    del _config

with open("proxies.txt") as fp:
    proxies = ProxyPool(fp.read().splitlines())

if IS_LOOPED and not requests:
    print("ERROR: isLooped is enabled, but the module 'requests' is not installed.")
    input()

counter = Counter()
processed = 0
loop_num = 0
total_count = RANGE["max"] - RANGE["min"]
id_iter = None
id_iter_lock = threading.Lock()
cache = {}

def get_group_id():
    global id_iter

    with id_iter_lock:
        if not id_iter:
            id_iter = iter(range(
                RANGE["min"],
                RANGE["max"] + 1
            ))
        
        try:
            return next(id_iter)
        except StopIteration:
            if IS_LOOPED:
                global processed
                global loop_num
                id_iter = None
                processed = 0
                loop_num += 1
            else:
                raise

    return get_group_id()

def get_group_info(group_id, proxy: Proxy):
    conn = proxy.get_connection("groups.roblox.com")
    conn.putrequest("GET", f"/v1/groups/{group_id}")
    conn.endheaders()
    resp = conn.getresponse()
    data = resp.read()
    data = json.loads(data)

    if "errors" in data:
        for err in data["errors"]:
            if not err["code"] in [1]:
                raise Exception(err)
        return
    
    return data

def make_embed(group_info):
    icon_url = requests.get("https://thumbnails.roblox.com/v1/groups/icons?groupIds=%d&size=150x150&format=Png&isCircular=false" % group_info["id"]).json()["data"][0]["imageUrl"]
    return dict(
        title="New group discovered!",
        url="https://www.roblox.com/groups/%d/--" % group_info["id"],
        thumbnail={"url": icon_url},
        fields=[
            {"name": "Id", "value": "%d" % group_info["id"]},
            {"name": "Name", "value": group_info["name"]},
            {"name": "Member count", "value": "%d" % group_info["memberCount"]}
        ]
    )

report_lock = threading.Lock()
def report(group_info):
    if group_info.get("owner"):
        return

    if not group_info.get("publicEntryAllowed"):
        return

    if group_info.get("isLocked"):
        return

    if MIN_MEMBER_COUNT and MIN_MEMBER_COUNT > 0 and group_info["memberCount"] < MIN_MEMBER_COUNT:
        return

    if group_info["id"] in cache:
        return
    
    with report_lock:
        print(f"[FOUND] Id: {group_info['id']} - Members: {group_info.get('memberCount')} - Name: {group_info['name']}")

        file_exists = os.path.exists("found.csv")
        with open("found.csv", "a", encoding="UTF-8", errors="ignore") as fp:
            if not file_exists:
                fp.write("Id,Member Count,Url,Name\n")
            fp.write(",".join([
                str(group_info["id"]),
                str(group_info.get("memberCount", 0)),
                f"https://www.roblox.com/groups/{group_info['id']}/--",
                '"' + group_info["name"] + '"'
            ]) + "\n")
        
        cache[group_info["id"]] = True

    if WEBHOOK_URL:
        embed = make_embed(group_info)
        requests.post(
            url=WEBHOOK_URL,
            json={"embeds": [embed]}
        )

class StatThread(threading.Thread):
    def run(self):
        while True:
            time.sleep(0.1)
            try:
                status = "  |  ".join([
                    "Progress: %d/%d %s" % (processed, total_count, f"({loop_num})" if IS_LOOPED else ""),
                    "CPM: %d" % counter.get_cpm()
                ])
                if os.name == "nt":
                    ctypes.windll.kernel32.SetConsoleTitleW(status)
                else:
                    print(status)
            except:
                pass

class Thread(threading.Thread):
    def run(self):
        global processed

        while True:
            try:
                group_id = get_group_id()
            except StopIteration:
                break

            while True:
                try:
                    with next(proxies) as proxy:
                        group_info = get_group_info(group_id, proxy)
                        if group_info:
                            report(group_info)

                        processed += 1
                        counter.add()
                        break
                except Exception as err:
                    if DISPLAY_ERRORS:
                        print(f"Error while processing {group_id}: {err} ({type(err)})")

def main():
    StatThread().start()
    threads = [Thread() for _ in range(THREAD_COUNT)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()