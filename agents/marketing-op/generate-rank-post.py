#!/usr/bin/env python3
"""乐天娱乐 - 每周热门游戏排行榜文案生成器"""

import json
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

LOGIN_CREDENTIALS = {
    "username": "beiai01",
    "password": "111111",
}

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def auto_login(config):
    """自动登录获取新 Token"""
    api = config["api"]
    url = "https://api.pb76mv.vip/api/user/login"
    password_md5 = hashlib.md5(LOGIN_CREDENTIALS["password"].encode()).hexdigest()
    payload = {
        "username": LOGIN_CREDENTIALS["username"],
        "password": password_md5,
        "plat_id": api["params"]["plat_id"],
        "lang": api["params"]["lang"],
        "device_type": api["params"]["device_type"],
        "app_type": api["params"]["app_type"],
        "device": api["params"]["device"],
        "channel_id": api["params"]["channel_id"],
        "game_domain": "ltyl555.com",
        "app_plat_type": api["params"]["app_plat_type"],
    }
    files = {k: (None, str(v)) for k, v in payload.items()}
    resp = requests.post(url, files=files, headers=api["headers"], timeout=10)
    data = resp.json()
    if data.get("status") != 0:
        raise Exception(f"登录失败: {data.get('msg')}")
    token = data["data"]["token"]
    # 更新 config.json
    config["api"]["params"]["token"] = token
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"✅ 自动登录成功，Token 已更新", flush=True)
    return token

def build_form_data(params_dict):
    """Build multipart form data for the API"""
    files = {}
    for key, value in params_dict.items():
        files[key] = (None, str(value))
    return files

def fetch_rank(config, retry=True):
    """Fetch game ranking from API，Token 失效时自动重新登录"""
    api = config["api"]
    url = api["base_url"] + api["rank_endpoint"]
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    params = {
        "plat_id": api["params"]["plat_id"],
        "ranking_type": "1",  # 热门榜
        "time_start": start_date,
        "time_end": end_date,
        "coin_name_unique": api["params"]["coin_name_unique"],
        "user_id": api["params"]["user_id"],
        "token": api["params"]["token"],
        "lang": api["params"]["lang"],
        "device_type": api["params"]["device_type"],
        "app_type": api["params"]["app_type"],
        "device": api["params"]["device"],
        "channel_id": api["params"]["channel_id"],
        "game_domain": api["params"]["game_domain"],
        "app_plat_type": api["params"]["app_plat_type"],
    }
    
    resp = requests.post(url, files=build_form_data(params), headers=api["headers"])
    data = resp.json()

    # Token 过期时自动重新登录
    if data.get("status") in (10129, 1100301, 401) and retry:
        print("⚠️ Token 已过期，自动重新登录...", flush=True)
        auto_login(config)
        params["token"] = config["api"]["params"]["token"]
        resp = requests.post(url, files=build_form_data(params), headers=api["headers"])
        data = resp.json()

    if data.get("status") != 0:
        raise Exception(f"Rank API error: {data}")

    return data["data"][:10]

def fetch_game_details(config, product_ids):
    """Fetch game names for given product IDs"""
    api = config["api"]
    url = api["base_url"] + api["game_list_endpoint"]
    
    params = {
        "plat_id": api["params"]["plat_id"],
        "modules": json.dumps(["game_list"]),
        "vendor_product_ids": json.dumps(product_ids),
        "page_index": "1",
        "page_count": str(len(product_ids)),
        "coin_name_unique": api["params"]["coin_name_unique"],
        "user_id": api["params"]["user_id"],
        "token": api["params"]["token"],
        "lang": api["params"]["lang"],
        "device_type": api["params"]["device_type"],
        "app_type": api["params"]["app_type"],
        "device": api["params"]["device"],
        "channel_id": api["params"]["channel_id"],
        "game_domain": api["params"]["game_domain"],
        "app_plat_type": api["params"]["app_plat_type"],
    }
    
    resp = requests.post(url, files=build_form_data(params), headers=api["headers"])
    data = resp.json()
    
    games = {}
    for g in data.get("data", {}).get("game_list", {}).get("list", []):
        bi = g["base_info"]
        games[bi["vendor_product_id"]] = {
            "name": bi.get("vendor_product_name", ""),
            "vendor_type": bi.get("vendor_type", 0),
        }
    return games

def get_vendor_name(config, pid):
    """Get vendor name from config mapping"""
    for vendor, pids in config.get("vendor_map", {}).items():
        if pid in pids:
            return vendor
    return "??"

def get_game_url(config, pid):
    """Get the correct game URL"""
    if pid in config.get("known_live_games", []):
        return f"https://ltyl777.com/zh-CN/game_play2/{pid}"
    return f"https://ltyl777.com/zh-CN/slot/{pid}"

def generate_post(config, rank_data, games):
    """Generate the Telegram post"""
    today = datetime.now().strftime("%-m月%-d日")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    lines = []
    for item in rank_data:
        pid = item["vendor_product_id"]
        rank = item["rank"]
        name = games.get(pid, {}).get("name", str(pid))
        vendor = get_vendor_name(config, pid)
        url = get_game_url(config, pid)
        prefix = medals.get(rank, f"{rank}、")
        lines.append(f"{prefix} {vendor} {name} [游玩]({url})")
    
    post = f"""💸💸💸 乐天游戏返水 2.2%｜玩的越多，返得越多！

天天返水，局局有回馈！不论输赢都能拿返利！
玩得越多，累计越高，边玩边拿返水，轻松赚福利！

🔥 今日最受欢迎游戏榜单新鲜出炉 （{today}）
看看其他玩家都在玩什么👇👇👇

{chr(10).join(lines)}
👉 [前往查看 玩家热门游戏排行榜](https://ltyl777.com/game_rank)

📅 每日签到领取¥8️⃣！周领¥6️⃣0️⃣！
👉👉👉 [前往签到 免費玩游戏](https://ltyl777.com/zh-CN/activity_sign)"""
    
    return post

def main():
    config = load_config()

    # 0. 每次运行先自动刷新 Token（保持最新）
    try:
        auto_login(config)
    except Exception as e:
        print(f"⚠️ 自动登录失败，使用现有 Token: {e}", flush=True)

    # 1. Fetch rankings
    rank_data = fetch_rank(config)
    
    # 2. Fetch game details
    product_ids = [item["vendor_product_id"] for item in rank_data]
    games = fetch_game_details(config, product_ids)
    
    # 3. Update vendor map with any new games
    for pid, info in games.items():
        found = False
        for pids in config.get("vendor_map", {}).values():
            if pid in pids:
                found = True
                break
        if not found:
            vtype = info.get("vendor_type", 0)
            # Auto-detect based on vendor_type or just mark unknown
            print(f"⚠️ 新游戏未在 vendor_map 中: {pid} ({info['name']})", flush=True)
    
    # 4. Generate post
    post = generate_post(config, rank_data, games)
    print(post)

if __name__ == "__main__":
    main()
