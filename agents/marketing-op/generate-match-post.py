#!/usr/bin/env python3
"""乐天娱乐 - 五大联赛明日赛程文案生成器"""

import json
import urllib.request
from datetime import datetime, timedelta, timezone

# ESPN API - 五大联赛
LEAGUES = {
    "eng.1": {"name": "英格兰超级联赛", "emoji": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "ger.1": {"name": "德国甲组联赛", "emoji": "🇩🇪"},
    "esp.1": {"name": "西班牙甲组联赛", "emoji": "🇪🇸"},
    "ita.1": {"name": "意大利甲组联赛", "emoji": "🇮🇹"},
    "fra.1": {"name": "法国甲组联赛", "emoji": "🇫🇷"},
}

# 中文队名映射（常见队名）
TEAM_NAME_ZH = {
    # 英超
    "Arsenal": "阿森纳", "Aston Villa": "阿斯顿维拉", "AFC Bournemouth": "伯恩茅斯",
    "Brentford": "布伦特福德", "Brighton & Hove Albion": "布莱顿", "Chelsea": "切尔西",
    "Crystal Palace": "水晶宫", "Everton": "埃弗顿", "Fulham": "富勒姆",
    "Liverpool": "利物浦", "Manchester City": "曼城", "Manchester United": "曼联",
    "Newcastle United": "纽卡斯尔联", "Nottingham Forest": "诺丁汉森林",
    "Tottenham Hotspur": "托特纳姆热刺", "West Ham United": "西汉姆联",
    "Wolverhampton Wanderers": "狼队", "Ipswich Town": "伊普斯维奇",
    "Leicester City": "莱斯特城", "Southampton": "南安普顿",
    # 德甲
    "Bayern Munich": "拜仁慕尼黑", "Borussia Dortmund": "多特蒙德",
    "RB Leipzig": "RB莱比锡", "Bayer Leverkusen": "勒沃库森",
    "Eintracht Frankfurt": "法兰克福", "VfB Stuttgart": "斯图加特",
    "SC Freiburg": "弗赖堡", "VfL Wolfsburg": "沃尔夫斯堡",
    "Borussia Mönchengladbach": "门兴格拉德巴赫", "Werder Bremen": "云达不莱梅",
    "1. FC Union Berlin": "柏林联", "TSG Hoffenheim": "霍芬海姆",
    "Mainz": "美因茨", "FC Augsburg": "奥格斯堡",
    "1. FC Heidenheim 1846": "海登海姆", "St. Pauli": "圣保利",
    "FC Cologne": "科隆", "Hamburg SV": "汉堡",
    # 西甲
    "Barcelona": "巴塞罗那", "Real Madrid": "皇家马德里",
    "Atlético Madrid": "马德里竞技", "Real Sociedad": "皇家社会",
    "Athletic Club": "毕尔巴鄂竞技", "Real Betis": "皇家贝蒂斯",
    "Villarreal": "比利亚雷亚尔", "Sevilla": "塞维利亚",
    "Valencia": "巴伦西亚", "Celta Vigo": "维戈塞尔塔",
    "Getafe": "赫塔菲", "Osasuna": "奥萨苏纳", "Mallorca": "马洛卡",
    "Rayo Vallecano": "巴列卡诺", "Espanyol": "西班牙人",
    "Alavés": "阿拉维斯", "Levante": "莱万特",
    "Real Oviedo": "奥维耶多", "Leganés": "莱加内斯",
    "Las Palmas": "拉斯帕尔马斯", "Girona": "赫罗纳",
    # 意甲
    "Internazionale": "国际米兰", "AC Milan": "AC米兰", "Juventus": "尤文图斯",
    "SSC Napoli": "那不勒斯", "AS Roma": "罗马", "Lazio": "拉齐奥",
    "Atalanta": "亚特兰大", "Fiorentina": "佛罗伦萨", "Bologna": "博洛尼亚",
    "Torino": "都灵", "Cagliari": "卡利亚里", "Parma": "帕尔马",
    "Hellas Verona": "维罗纳", "Sassuolo": "萨索洛", "Cremonese": "克雷莫纳",
    "Pisa": "比萨", "Genoa": "热那亚", "Udinese": "乌迪内斯",
    # 法甲
    "Paris Saint-Germain": "巴黎圣日耳曼", "Marseille": "马赛",
    "AS Monaco": "摩纳哥", "Lyon": "里昂", "Lille": "里尔",
    "Nice": "尼斯", "Lens": "朗斯", "Stade Rennais": "雷恩",
    "Brest": "布雷斯特", "Strasbourg": "斯特拉斯堡",
    "Nantes": "南特", "Angers": "昂热", "AJ Auxerre": "欧塞尔",
    "Le Havre AC": "勒阿弗尔", "Lorient": "洛里昂",
    "Metz": "梅斯", "Paris FC": "巴黎FC", "Montpellier": "蒙彼利埃",
    "Toulouse": "图卢兹", "Reims": "兰斯", "Saint-Étienne": "圣埃蒂安",
}

# GMT+8 时区
GMT8 = timezone(timedelta(hours=8))

def get_zh_name(en_name):
    """Get Chinese team name, fallback to English"""
    return TEAM_NAME_ZH.get(en_name, en_name)

def fetch_matches(date_str):
    """Fetch matches from ESPN API for given date (YYYYMMDD)"""
    all_matches = {}
    
    for league_code, league_info in LEAGUES.items():
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard?dates={date_str}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"⚠️ Failed to fetch {league_code}: {e}")
            continue
        
        events = data.get("events", [])
        if not events:
            continue
        
        matches = []
        for e in events:
            comp = e.get("competitions", [{}])[0]
            teams = comp.get("competitors", [])
            if len(teams) != 2:
                continue
            
            home = [t for t in teams if t.get("homeAway") == "home"]
            away = [t for t in teams if t.get("homeAway") == "away"]
            
            home_name = home[0]["team"]["displayName"] if home else teams[0]["team"]["displayName"]
            away_name = away[0]["team"]["displayName"] if away else teams[1]["team"]["displayName"]
            
            # Parse UTC time and convert to GMT+8
            utc_time = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            gmt8_time = utc_time.astimezone(GMT8)
            
            matches.append({
                "home": get_zh_name(home_name),
                "away": get_zh_name(away_name),
                "time": gmt8_time.strftime("%Y-%m-%d %H:%M:%S"),
                "home_en": home_name,
                "away_en": away_name,
            })
        
        if matches:
            # Sort by time
            matches.sort(key=lambda x: x["time"])
            all_matches[league_code] = matches
    
    return all_matches

def generate_post(target_date, all_matches):
    """Generate the Telegram post"""
    date_display = target_date.strftime("%-m月%-d日")
    
    if not all_matches:
        return f"🇧🇷🇧🇷🇧🇷 明日热门足球比赛预告 📅\n\n{date_display} 五大联赛无赛事安排\n\n📺 更多赛事请关注乐天体育！\n👉[直播链接：前往观看赛事 高清直播不卡顿](https://ltyl777.com/zh-CN/game_play2/Letian)"
    
    sections = []
    num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for league_code, matches in all_matches.items():
        league_info = LEAGUES[league_code]
        section = f"➡️ {league_info['name']}"
        
        for i, m in enumerate(matches):
            num = num_emojis[i] if i < len(num_emojis) else f"{i+1}."
            section += f"\n{num}{m['home']}VS{m['away']}"
            section += f"\n⏰开始:{m['time']}"
        
        sections.append(section)
    
    matches_text = "\n".join(sections)
    
    post = f"""🇧🇷🇧🇷🇧🇷 明日热门足球比赛预告 📅

想边看球边感受激情？➡️我们都帮你整理好了！以下时间统一为（GMT+8）

{matches_text}

📺 一起锁定赛场，见证每一个进球瞬间！ 🔥
👉[直播链接：前往观看赛事 高清直播不卡顿](https://ltyl777.com/zh-CN/game_play2/Letian)"""
    
    return post

def main():
    # 明日日期
    tomorrow = datetime.now() + timedelta(days=1)
    date_str = tomorrow.strftime("%Y%m%d")
    
    # 获取赛事
    all_matches = fetch_matches(date_str)
    
    # 生成文案
    post = generate_post(tomorrow, all_matches)
    print(post)

if __name__ == "__main__":
    main()
