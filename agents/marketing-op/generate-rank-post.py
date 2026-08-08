#!/usr/bin/env python3
"""乐天娱乐 - 每周热门游戏排行榜文案生成器

重要约定：
  stdout 只输出「要发到 Telegram 的文案」，其他任何日志/警告一律走 stderr。
  workflow 是 `python3 generate-rank-post.py > message.txt`，stdout 会被原样发出去。
"""

import json
import sys
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

LOGIN_CREDENTIALS = {
    "username": "beiai01",
    "password": "111111",
}

# 真人厅游戏的名称关键字（用于判断该给 /game_play2/ 还是 /slot/ 链接）
LIVE_KEYWORDS = (
    "百家乐", "百家樂", "baccarat",
    "轮盘", "輪盤", "roulette",
    "龙虎", "龍虎", "dragon tiger",
    "骰宝", "骰寶", "sicbo", "sic bo",
    "21点", "21點", "blackjack",
    "牛牛", "色碟", "番摊", "番攤",
    "真人", "视讯", "視訊", "live casino",
)


def log(msg):
    """所有诊断信息走 stderr —— 绝对不能进 stdout，否则会被当成贴文发出去。"""
    print(msg, file=sys.stderr, flush=True)


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
    # 更新内存中的 config（CI runner 是临时的，写回文件只对本地运行有意义）
    config["api"]["params"]["token"] = token
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except OSError as e:
        log(f"（config.json 未能写回，不影响本次运行: {e}）")
    log("✅ 自动登录成功，Token 已更新")
    return token


def build_form_data(params_dict):
    """Build multipart form data for the API"""
    return {key: (None, str(value)) for key, value in params_dict.items()}


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

    resp = requests.post(url, files=build_form_data(params), headers=api["headers"], timeout=20)
    data = resp.json()

    # Token 过期时自动重新登录
    if data.get("status") in (10129, 1100301, 401) and retry:
        log("⚠️ Token 已过期，自动重新登录...")
        auto_login(config)
        params["token"] = config["api"]["params"]["token"]
        resp = requests.post(url, files=build_form_data(params), headers=api["headers"], timeout=20)
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

    resp = requests.post(url, files=build_form_data(params), headers=api["headers"], timeout=20)
    data = resp.json()

    games = {}
    for g in data.get("data", {}).get("game_list", {}).get("list", []):
        bi = g["base_info"]
        games[bi["vendor_product_id"]] = {
            "name": bi.get("vendor_product_name", ""),
            "vendor_type": bi.get("vendor_type", 0),
            # 保留原始 base_info，用来在 stderr 里排查新游戏该归到哪个厂商 / 哪种链接
            "raw": bi,
        }
    return games


def get_vendor_name(config, pid, info):
    """取得厂商前缀。查不到就回传空字串（宁可不显示，也不要印出 '??'）。"""
    for vendor, pids in config.get("vendor_map", {}).items():
        if pid in pids:
            return vendor

    # 退路：config 里若有 vendor_type -> 厂商名 的对照表就用它
    vtype = info.get("vendor_type")
    if vtype is not None:
        vt_map = config.get("vendor_type_map", {})
        name = vt_map.get(str(vtype))
        if name:
            return name

    return ""


def is_live_game(config, pid, info):
    """判断是否为真人厅游戏"""
    if pid in config.get("known_live_games", []):
        return True

    vtype = info.get("vendor_type")
    if vtype is not None and vtype in config.get("live_vendor_types", []):
        return True

    name = (info.get("name") or "").lower()
    return any(kw in name for kw in LIVE_KEYWORDS)


def get_game_url(config, pid, info):
    """依游戏类型给出正确的链接（真人厅走 game_play2，其余走 slot）"""
    url_map = config.get("game_url_map", {})
    key = "live" if is_live_game(config, pid, info) else "slot"
    template = url_map.get(key)
    if template:
        return template.replace("{id}", str(pid))
    site = config["api"].get("site_url", "https://ltyl777.com")
    path = "game_play2" if key == "live" else "slot"
    return f"{site}/zh-CN/{path}/{pid}"


def generate_post(config, rank_data, games):
    """Generate the Telegram post"""
    today = datetime.now().strftime("%-m月%-d日")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    lines = []
    for item in rank_data:
        pid = item["vendor_product_id"]
        rank = item["rank"]
        info = games.get(pid, {})
        name = info.get("name") or str(pid)
        vendor = get_vendor_name(config, pid, info)
        url = get_game_url(config, pid, info)
        prefix = medals.get(rank, f"{rank}、")
        # vendor 为空时不要留下多余空格
        label = f"{vendor} {name}".strip()
        lines.append(f"{prefix} {label} [游玩]({url})")

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


def report_unmapped(config, games):
    """把还没归类的新游戏印到 stderr —— 附上原始栏位，方便下次直接补进 config.json"""
    mapped = set()
    for pids in config.get("vendor_map", {}).values():
        mapped.update(pids)

    for pid, info in games.items():
        if pid in mapped:
            continue
        raw = info.get("raw", {})
        log(
            f"⚠️ 新游戏未归类: {pid} ({info.get('name')}) "
            f"vendor_type={info.get('vendor_type')} "
            f"live={is_live_game(config, pid, info)}"
        )
        log(f"   base_info 栏位: {sorted(raw.keys())}")


def main():
    config = load_config()

    # 0. 每次运行先自动刷新 Token（保持最新）
    try:
        auto_login(config)
    except Exception as e:
        log(f"⚠️ 自动登录失败，使用现有 Token: {e}")

    # 1. Fetch rankings
    rank_data = fetch_rank(config)
    if not rank_data:
        log("❌ 排行榜为空，中止（不发送）")
        sys.exit(1)

    # 2. Fetch game details
    product_ids = [item["vendor_product_id"] for item in rank_data]
    games = fetch_game_details(config, product_ids)

    # 3. 记录尚未归类的新游戏（只进 stderr）
    report_unmapped(config, games)

    # 4. Generate post —— 只有这一行进 stdout
    post = generate_post(config, rank_data, games)
    print(post)


if __name__ == "__main__":
    main()
