#!/usr/bin/env python3
"""96中文 - 每周热门游戏排行榜文案生成器"""

import hashlib
import json
import requests
import sys
from datetime import datetime, timedelta

API_BASE = "https://api.5676.one"
SITE_URL = "https://96i8.com"
PLAT_ID = "60006"
CHANNEL_ID = "60006002"
GAME_DOMAIN = "96i8.com"
USERNAME = "111111"
PASSWORD = "111111"
DEVICE = "894ff616-9b3a-454c-a77b-9345eca42db0"

HEADERS = {
    "Referer": f"{SITE_URL}/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

COMMON_PARAMS = {
    "plat_id": PLAT_ID,
    "lang": "zh_CN",
    "device_type": "3",
    "app_type": "4",
    "device": DEVICE,
    "channel_id": CHANNEL_ID,
    "game_domain": GAME_DOMAIN,
    "app_plat_type": "3",
}

KNOWN_LIVE_GAMES = {10740, 10743}


def bf(d):
    return {k: (None, str(v)) for k, v in d.items()}


def login():
    pw = hashlib.md5(PASSWORD.encode()).hexdigest()
    payload = {**COMMON_PARAMS, "username": USERNAME, "password": pw}
    resp = requests.post(f"{API_BASE}/api/user/login", files=bf(payload), headers=HEADERS, timeout=15)
    data = resp.json()
    if data.get("status") != 0:
        print(f"LOGIN_FAILED: {data}", file=sys.stderr)
        sys.exit(1)
    return str(data["data"]["user_id"]), data["data"]["token"]


def fetch_rank(user_id, token):
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    params = {
        **COMMON_PARAMS,
        "ranking_type": "1",
        "time_start": start_date,
        "time_end": end_date,
        "coin_name_unique": "USDT",
        "user_id": user_id,
        "token": token,
    }
    resp = requests.post(f"{API_BASE}/api/v2/plat/{PLAT_ID}/rank/game", files=bf(params), headers=HEADERS, timeout=15)
    data = resp.json()
    if data.get("status") != 0:
        print(f"RANK_FAILED: {data}", file=sys.stderr)
        sys.exit(1)
    rank_data = data.get("data", [])[:10]
    if not rank_data:
        print("RANK_EMPTY", file=sys.stderr)
        sys.exit(1)
    return rank_data


def fetch_game_names(user_id, token, product_ids):
    params = {
        **COMMON_PARAMS,
        "modules": json.dumps(["game_list"]),
        "vendor_product_ids": json.dumps(product_ids),
        "coin_name_unique": "USDT",
        "user_id": user_id,
        "token": token,
        "page_index": "1",
        "page_count": str(len(product_ids)),
    }
    resp = requests.post(f"{API_BASE}/api/v2/plat/{PLAT_ID}/game/list", files=bf(params), headers=HEADERS, timeout=15)
    gl = resp.json().get("data", {}).get("game_list", {})
    games = {}
    for g in gl.get("list", []) if isinstance(gl, dict) else []:
        bi = g["base_info"]
        games[bi["vendor_product_id"]] = bi.get("vendor_product_name", "")
    return games


def get_game_url(pid):
    if pid in KNOWN_LIVE_GAMES:
        return f"{SITE_URL}/zh-CN/game_play2/{pid}"
    return f"{SITE_URL}/zh-CN/slot/{pid}"


def generate_post(rank_data, games):
    today = datetime.now().strftime("%-m月%-d日")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for item in rank_data:
        pid = item["vendor_product_id"]
        rank = item["rank"]
        name = games.get(pid, str(pid))
        url = get_game_url(pid)
        prefix = medals.get(rank, f"{rank}、")
        lines.append(f'{prefix} {name} <a href="{url}">游玩</a>')

    return f"""🔥 今日最受欢迎游戏榜单新鲜出炉 （{today}）
看看其他玩家都在玩什么👇👇👇

{chr(10).join(lines)}
👉 <a href="{SITE_URL}/game_rank">前往查看 玩家热门游戏排行榜</a>

📅 每日签到领取¥8️⃣！周领¥6️⃣0️⃣！
👉👉👉 <a href="{SITE_URL}/zh-CN/activity_sign">前往签到 免費玩游戏</a>"""


def main():
    user_id, token = login()
    rank_data = fetch_rank(user_id, token)
    product_ids = [item["vendor_product_id"] for item in rank_data]
    games = fetch_game_names(user_id, token, product_ids)
    post = generate_post(rank_data, games)
    print(post)


if __name__ == "__main__":
    main()
