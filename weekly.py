import os
import sys
import time
import math
import smtplib
import logging
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf
import requests

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, RECIPIENTS,
    EARNINGS_STOCKS, INDEXES, MAGNIFICENT_SEVEN, SEMICONDUCTORS,
    BLUE_CHIPS, COMMODITIES, CRYPTO_NAMES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))


def _isnan(v):
    try:
        return math.isnan(float(v))
    except Exception:
        return False


def _clean(val):
    return None if _isnan(val) else val


def fmt_change(pct):
    if pct is None:
        return "-"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def fetch_weekly_returns(symbols):
    """拉取每只标的的周涨跌幅"""
    results = []
    for sym in symbols:
        try:
            time.sleep(0.3)
            hist = yf.download(sym, period="1wk", progress=False, auto_adjust=True)
            if hist is None or len(hist) < 2:
                continue
            start = float(hist["Close"].iloc[0])
            end = float(hist["Close"].iloc[-1])
            if not _isnan(start) and not _isnan(end) and start != 0:
                pct = round((end - start) / start * 100, 2)
                # 获取标的名
                try:
                    t = yf.Ticker(sym)
                    name = t.info.get("shortName") or sym
                except Exception:
                    name = sym
                results.append({"sym": sym, "name": name, "change_pct": pct})
        except Exception as e:
            logger.warning("获取 %s 周数据失败: %s", sym, e)
    return results


def fetch_earnings_calendar():
    """获取接下来 7 天内将发财报的公司"""
    now = datetime.now(BEIJING_TZ)
    next_week = now + timedelta(days=7)
    upcoming = []

    for sym in EARNINGS_STOCKS:
        try:
            time.sleep(0.2)
            t = yf.Ticker(sym)
            cal = t.calendar
            if cal is None:
                continue
            # earnings date 可能是日期范围或列表
            dates_raw = cal.get("Earnings Date", [])
            if not dates_raw:
                continue
            if isinstance(dates_raw, (int, float)):
                dates_raw = [dates_raw]

            # 检查是否有日期在未来 7 天内
            in_range = False
            for d in dates_raw:
                try:
                    if isinstance(d, (int, float)):
                        dt = datetime.fromtimestamp(d, tz=BEIJING_TZ)
                    elif hasattr(d, "strftime"):
                        dt = d.replace(tzinfo=BEIJING_TZ) if d.tzinfo is None else d
                    else:
                        continue
                    if now <= dt <= next_week:
                        in_range = True
                        break
                except Exception:
                    continue

            if in_range:
                eps_avg = _clean(cal.get("Earnings Average"))
                rev_avg = _clean(cal.get("Revenue Average"))
                try:
                    name = t.info.get("shortName") or sym
                except Exception:
                    name = sym
                upcoming.append({
                    "sym": sym, "name": name,
                    "eps": f"{eps_avg:.2f}" if eps_avg is not None else "N/A",
                    "revenue": f"{rev_avg:.0f}" if rev_avg is not None else "N/A" if rev_avg is not None else "N/A",
                })
                logger.info("财报: %s EPS≈%s", sym, upcoming[-1]["eps"])
        except Exception as e:
            logger.warning("获取 %s 财报日历失败: %s", sym, e)

    return upcoming


def render_html(week_str, top5, bottom5, earnings, index_weekly):
    items_html = ""
    if top5:
        items_html += '<div class="subtitle">Top 5 涨幅</div><table>'
        for s in top5:
            items_html += f'<tr><td class="name">{s["name"]}</td><td class="val up">{fmt_change(s["change_pct"])}</td></tr>'
        items_html += '</table>'
    if bottom5:
        items_html += '<div class="subtitle">Top 5 跌幅</div><table>'
        for s in bottom5:
            items_html += f'<tr><td class="name">{s["name"]}</td><td class="val down">{fmt_change(s["change_pct"])}</td></tr>'
        items_html += '</table>'
    if index_weekly:
        items_html += '<div class="subtitle">三大指数</div><table>'
        for s in index_weekly:
            items_html += f'<tr><td class="name">{s["name"]}</td><td class="val {"up" if s["change_pct"]>0 else "down" if s["change_pct"]<0 else ""}">{fmt_change(s["change_pct"])}</td></tr>'
        items_html += '</table>'

    earnings_html = ""
    if earnings:
        earnings_html = '<div class="subtitle">下周发财报</div><table>'
        for e in earnings:
            earnings_html += f'<tr><td class="name">{e["name"]}</td><td class="val">EPS≈{e["eps"]}</td></tr>'
        earnings_html += '</table>'
    else:
        earnings_html = '<p style="font-size:12px;color:#999;">下周无持仓股发财报</p>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>周报 - {week_str}</title>
<style>
body{{margin:0;padding:0;background:#e8e8e8;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#333}}
.container{{max-width:500px;margin:0 auto;background:#fff}}
.header{{background:#1a1a2e;padding:24px;text-align:center}}
.header h1{{margin:0;font-size:20px;color:#fff;font-weight:700}}
.header .date{{margin-top:6px;font-size:13px;color:#999}}
.content{{padding:16px 20px}}
.subtitle{{font-size:14px;font-weight:700;color:#1a1a2e;margin:16px 0 8px;padding-bottom:4px;border-bottom:2px solid #1a1a2e}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
td{{padding:5px 0;border-bottom:1px solid #f0f0f0}}
td.name{{text-align:left;font-weight:500}}
td.val{{text-align:right;font-weight:600}}
td.up{{color:#d32f2f}}
td.down{{color:#2e7d32}}
.footer{{padding:16px 20px;text-align:center;font-size:11px;color:#999;background:#f5f5f5}}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>每周市场周报</h1><div class="date">{week_str}</div></div>
<div class="content">
{items_html}
{earnings_html}
</div>
<div class="footer">每周日自动发送 · 仅覆盖晨报持仓标的<br>仅供参考，不构成投资建议</div>
</div>
</body>
</html>"""
    return html


def send_email(html_content, week_str):
    if not SMTP_USER or not SMTP_PASS or not RECIPIENTS:
        logger.error("SMTP 未配置"); return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"每周市场周报 - {week_str}"
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, RECIPIENTS, msg.as_string())
        server.quit()
        logger.info("周报发送成功")
        return True
    except Exception as e:
        logger.error("发送失败: %s", e)
        return False


def main():
    now = datetime.now(BEIJING_TZ)
    week_str = now.strftime("%Y年%m月第%d周")

    # 1. 收集所有持股标的（排除指数/商品/ETF）
    all_stocks = list(EARNINGS_STOCKS)

    logger.info("拉取 %d 只个股周涨跌...", len(all_stocks))
    weekly = fetch_weekly_returns(all_stocks)
    weekly.sort(key=lambda x: x["change_pct"], reverse=True)

    top5 = [w for w in weekly if w["change_pct"] > 0][:5]
    bottom5 = sorted([w for w in weekly if w["change_pct"] < 0], key=lambda x: x["change_pct"])[:5]

    logger.info("三大指数周涨跌...")
    index_symbols = [i["symbol"] for i in INDEXES]
    index_weekly = fetch_weekly_returns(index_symbols)

    logger.info("拉取财报日历...")
    earnings = fetch_earnings_calendar()

    html = render_html(week_str, top5, bottom5, earnings, index_weekly)
    if not send_email(html, week_str):
        sys.exit(1)


if __name__ == "__main__":
    main()
