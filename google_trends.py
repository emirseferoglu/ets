"""
google_trends.py — Son 1 ay Google Trends verisiyle wall art/poster
temalarını tarar. pytrends (resmi olmayan ama yaygın kullanılan Google
Trends istemcisi) ile SEED_KEYWORDS için "rising" (yükselen) ilgili
aramaları ve genel ilgi trendini çeker.

NOT: trends.google.com'a çıkış gerektirir. Bu depo sandbox'ında (agent
proxy) bu host engelli — droplette (açık internet) çalıştırılmalı.

Çıktı:
  reports/google_trends.md          — okunabilir rapor
  data/google_trends_opportunities.json  — action_plan/product_ideas'a beslenebilir ham liste

Kullanım:
    pip install pytrends
    python google_trends.py
    python google_trends.py --keywords "frame tv art" "printable poster" "wall art"
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "reports" / "google_trends.md"
OUT_JSON = ROOT / "data" / "google_trends_opportunities.json"

SEED_KEYWORDS = [
    "wall art",
    "frame tv art",
    "printable poster",
    "poster print",
]


def fetch_trends(keywords: list[str], timeframe: str = "today 1-m",
                  geo: str = "US") -> dict:
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-US", tz=360)
    result: dict[str, dict] = {}

    for kw in keywords:
        print(f"Taranıyor: '{kw}'…")
        pytrends.build_payload([kw], timeframe=timeframe, geo=geo)

        interest = pytrends.interest_over_time()
        trend_direction = None
        if not interest.empty and kw in interest.columns:
            series = interest[kw]
            first_half = series.iloc[: len(series) // 2].mean()
            second_half = series.iloc[len(series) // 2:].mean()
            if first_half > 0:
                trend_direction = round((second_half - first_half) / first_half * 100, 1)

        related = pytrends.related_queries()
        rising = related.get(kw, {}).get("rising")
        top = related.get(kw, {}).get("top")

        result[kw] = {
            "trend_change_pct": trend_direction,
            "rising_queries": (
                rising[["query", "value"]].to_dict("records") if rising is not None else []
            ),
            "top_queries": (
                top[["query", "value"]].to_dict("records") if top is not None else []
            ),
        }
        time.sleep(1.5)  # nazik ol, rate-limit yeme

    return result


def write_report(data: dict) -> None:
    lines = ["# Google Trends — son 1 ay (wall art / poster)", ""]
    for kw, d in data.items():
        change = d["trend_change_pct"]
        arrow = "📈" if (change or 0) > 0 else ("📉" if (change or 0) < 0 else "➡️")
        lines.append(f"## '{kw}' {arrow} ({change}% ay içi değişim)")
        if d["rising_queries"]:
            lines.append("\n**Yükselen ilgili aramalar (rising):**")
            for q in d["rising_queries"][:15]:
                val = q["value"]
                val_str = "YENİ (breakout)" if val == "Breakout" or val == 5000 else f"+{val}%"
                lines.append(f"- {q['query']} — {val_str}")
        if d["top_queries"]:
            lines.append("\n**En yüksek hacimli ilgili aramalar (top):**")
            for q in d["top_queries"][:10]:
                lines.append(f"- {q['query']} ({q['value']})")
        lines.append("")

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines))
    print(f"Yazıldı: {REPORT_PATH.relative_to(ROOT)}")


def write_opportunities(data: dict) -> None:
    opps = []
    for kw, d in data.items():
        for q in d["rising_queries"]:
            opps.append({
                "seed": kw,
                "keyword": q["query"],
                "growth": q["value"],
                "source": "google_trends",
            })
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(opps, ensure_ascii=False, indent=2))
    print(f"Yazıldı: {OUT_JSON.relative_to(ROOT)}  ({len(opps)} fırsat)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", nargs="+", default=SEED_KEYWORDS)
    ap.add_argument("--timeframe", default="today 1-m",
                     help="pytrends timeframe, örn. 'today 1-m', 'today 3-m'")
    args = ap.parse_args()

    data = fetch_trends(args.keywords, timeframe=args.timeframe)
    write_report(data)
    write_opportunities(data)


if __name__ == "__main__":
    main()
