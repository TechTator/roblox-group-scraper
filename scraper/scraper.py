from structures import ProxyPool, Proxy, Counter
import threading
import json
import time
import os
import sys
import requests

with open("config.json") as fp:
    _config = json.load(fp)
    THREAD_COUNT = _config["threadCount"]
    DISPLAY_ERRORS = _config.get("displayErrors", True)
    MIN_MEMBER_COUNT = _config.get("minMemberCount")
    IS_LOOPED = _config.get("isLooped", False)
    WEBHOOK_URL = _config.get("webhookUrl")
    RANGE = _config["range"] if len(sys.argv) == 1 else {"min": int(sys.argv[1]), "max": int(sys.argv[2])}

with open("proxies.txt") as fp:
    proxies = ProxyPool(fp.read().splitlines())

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

        file_exists = os.path.exists("groups.txt")
        with open("groups.txt", "a") as fp:
            if not file_exists:
                fp.write("group id,group name,member count\n")
            fp.write(f"{group_info['id']},{group_info['name']},{group_info['memberCount']}\n")
        
        if WEBHOOK_URL:
            requests.post(
                WEBHOOK_URL,
                json=dict(
                    embeds=[make_embed(group_info)]
                )
            )
        cache[group_info["id"]] = True

def thread_func():
    while True:
        group_id = get_group_id()
        proxy = proxies.get_proxy()

        try:
            group_info = get_group_info(group_id, proxy)
            if not group_info:
                continue
            report(group_info)
            counter.increment()
        except Exception as ex:
            if DISPLAY_ERRORS:
                print(f"Error processing group {group_id}: {ex}")
            proxy.blacklist()
            continue
        finally:
            processed += 1
            if processed % 1000 == 0:
                print(f"Processed {processed} of {total_count} in {loop_num} loops")

if __name__ == "__main__":
    threads = [
        threading.Thread(target=thread_func)
        for i in range(THREAD_COUNT)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()
