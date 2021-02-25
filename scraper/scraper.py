from structures import ProxyPool, Proxy, Counter
import threading
import json
import time
import ctypes
import os

with open("config.json") as fp:
    _config = json.load(fp)
    THREAD_COUNT = _config["threadCount"]
    DISPLAY_ERRORS = _config.get("displayErrors", True)
    MIN_MEMBER_COUNT = _config.get("minimumMemberCount")
    ID_ITER = iter(range(
        _config["range"]["min"],
        _config["range"]["max"] + 1
    ))
    TOTAL_COUNT = _config["range"]["max"] - _config["range"]["min"]

with open("proxies.txt") as fp:
    proxies = ProxyPool(fp.read().splitlines())

counter = Counter()
processed = 0

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

class StatThread(threading.Thread):
    def run(self):
        while True:
            time.sleep(0.1)
            try:
                ctypes.windll.kernel32.SetConsoleTitleW("  |  ".join([
                    "Progress: %d/%d" % (processed, TOTAL_COUNT),
                    "CPM: %d" % counter.get_cpm()
                ]))
            except:
                pass

class Thread(threading.Thread):
    def run(self):
        global processed

        while True:
            try:
                group_id = next(ID_ITER)
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