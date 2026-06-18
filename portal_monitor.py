#!/usr/bin/env python3
"""Monitor Steam prices for Portal 1 & 2. Run by GitHub Actions daily."""

import json
import os
import sys
import urllib.request
from datetime import datetime

# ── Config ──────────────────────────────────────────────
APP_IDS = {400: "Portal", 620: "Portal 2"}
BASE_PRICE = 4200  # 42 RMB in cents
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "price_state.json")
ALERT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alert.md")
# ─────────────────────────────────────────────────────────

def fetch_price(app_id):
    """Fetch current price for a Steam app. Returns (final, initial, discount) in cents."""
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=cn&filters=price_overview"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Portal-Monitor/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        app_data = data.get(str(app_id), {}).get("data", {})
        if app_data is None:
            raise ValueError(f"App {app_id} returned null data (region/key issue)")
        price_info = app_data.get("price_overview", {})
        if not price_info:
            return None, None, None
        return price_info.get("final"), price_info.get("initial"), price_info.get("discount_percent", 0)
    except Exception as e:
        print(f"❌ 获取 {app_id} 价格失败: {e}")
        return None, None, None


def main():
    print(f"=== Portal 价格监控 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    # Load previous state
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)

    alerts = []

    for app_id, name in APP_IDS.items():
        final, initial, discount = fetch_price(app_id)
        if final is None:
            print(f"[{name}] ⚠️ 无法获取价格，跳过\n")
            continue

        final_yuan = final / 100
        initial_yuan = initial / 100 if initial else None
        key = str(app_id)
        last_recorded = state.get(key, BASE_PRICE)
        state[key] = final  # always update

        # Print current status
        print(f"[{name}] 当前价格: ¥{final_yuan:.2f}", end="")
        if initial and discount > 0:
            print(f" (原价 ¥{initial_yuan:.2f}, -{discount}%)", end="")
        print()

        # Check for price drop
        if final < last_recorded:
            prev_yuan = last_recorded / 100
            drop = prev_yuan - final_yuan
            print(f"  🔔 降价了！ ¥{prev_yuan:.2f} → ¥{final_yuan:.2f} (↓¥{drop:.2f})\n")
            alerts.append({
                "name": name,
                "app_id": app_id,
                "prev_price": last_recorded,
                "new_price": final,
            })
        elif final > last_recorded:
            print(f"  📈 价格上涨: ¥{last_recorded/100:.2f} → ¥{final_yuan:.2f}\n")
        else:
            print(f"  价格未变\n")

    # Persist state
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    # Generate alert markdown
    if alerts:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = ["# 🎮 Portal 系列降价提醒！\n"]
        lines.append(f"**检测时间**: {now} (UTC)\n")
        lines.append("| 游戏 | AppID | 原记录价 | 当前价 | 降幅 |")
        lines.append("|------|-------|----------|--------|------|")
        total_drop = 0
        for a in alerts:
            drop = (a["prev_price"] - a["new_price"]) / 100
            total_drop += drop
            lines.append(
                f"| [{a['name']}](https://store.steampowered.com/app/{a['app_id']}) "
                f"| {a['app_id']} "
                f"| ¥{a['prev_price']/100:.2f} "
                f"| **¥{a['new_price']/100:.2f}** "
                f"| ↓¥{drop:.2f} |"
            )
        if len(alerts) > 1:
            lines.append(f"\n💰 合计可省 ¥{total_drop:.2f}")
        lines.append(f"\n👉 [打开 Steam 商店](https://store.steampowered.com/search/?term=portal)")

        with open(ALERT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"✅ 检测到 {len(alerts)} 个降价，已生成通知文件。")
    else:
        # Clean up stale alert file
        if os.path.exists(ALERT_FILE):
            os.remove(ALERT_FILE)
        print("✅ 无降价，一切正常。")


if __name__ == "__main__":
    main()
