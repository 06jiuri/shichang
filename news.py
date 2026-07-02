import os
import sys
import time
import smtplib
import logging
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
_RECIPIENTS_RAW = os.environ.get("RECIPIENTS", "")
RECIPIENTS = [r.strip() for r in _RECIPIENTS_RAW.split(",") if r.strip()]

BEIJING_TZ = timezone(timedelta(hours=8))

NEWS_SOURCES = ["^GSPC", "^DJI", "^IXIC", "NVDA", "TSLA", "^HSI", "000001.SS", "GC=F"]

# ============================================================
# 一句话标注
# ============================================================

def annotate(title, publisher):
    t = title.lower() if title else ""
    # 优先级从高到低
    for kw, label in [
        (["merge", "acquire", "buyout", "takeover", "deal", "收购", "并购"], "重大交易"),
        (["fed", "powell", "fomc", "rate cut", "rate hike", "hike", "联储", "降息", "加息", "联邦"], "关注利率"),
        (["cpi", "ppi", "inflation", "jobs", "payroll", "gdp", "pmi", "失业", "通胀", "就业", "数据"], "关注宏观"),
        (["earnings", "revenue", "profit", "beat", "miss", "财报", "营收", "利润", "业绩"], "关注业绩"),
        (["upgrade", "raise", "bull", "outperform", "上调", "看涨"], "利好"),
        (["downgrade", "cut", "bear", "underperform", "sell", "下调", "看跌"], "利空"),
        (["surge", "rally", "jump", "record", "新高", "暴涨", "飙升", "突破"], "大涨"),
        (["plunge", "crash", "tumble", "slump", "暴跌", "跳水", "重挫"], "大跌"),
        (["bitcoin", "btc", "ethereum", "eth", "crypto", "加密", "比特币", "以太坊"], "加密动态"),
        (["ai", "chip", "nvidia", "nvda", "英伟达", "人工智能", "芯片", "半导体"], "AI/芯片"),
        (["oil", "gold", "commodity", "crude", "原油", "黄金", "商品"], "商品动态"),
        (["china", "beijing", "xi", "pboc", "中国", "北京", "央行", "上证"], "中国动态"),
        (["trade", "tariff", "sanction", "贸易", "关税", "制裁"], "地缘贸易"),
    ]:
        if any(k in t for k in kw):
            return label
    return "市场动态"


# ============================================================
# 拉取新闻
# ============================================================

def fetch_news(source_symbols, cutoff_start, cutoff_end):
    """从 yfinance 拉取新闻，过滤时间窗口"""
    all_news = []
    seen_urls = set()

    for sym in source_symbols:
        try:
            ticker = yf.Ticker(sym)
            news_list = ticker.news
            logger.info("%s 返回 %d 条原始新闻", sym, len(news_list or []))
            if not news_list:
                continue
            # 打印第一条的结构用于调试
            if news_list:
                first = news_list[0]
                logger.info("  [debug] keys: %s", list(first.keys())[:10])
                content = first.get("content", {})
                if content:
                    logger.info("  [debug] content keys: %s", list(content.keys())[:15])
                    logger.info("  [debug] content sample: %s", str(content)[:300])
            for item in news_list:
                content = item.get("content", {})
                url = content.get("canonicalUrl", {}).get("url", "") or content.get("canonical_url", "") or content.get("link", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = content.get("title", "")
                pub_ts = content.get("pubDate") or content.get("providerPublishTime") or content.get("pub_date", 0)
                try:
                    pub_ts = int(pub_ts)
                except (ValueError, TypeError):
                    pub_ts = 0

                if pub_ts < cutoff_start or pub_ts > cutoff_end:
                    continue

                publisher = content.get("provider", {}).get("displayName", "") or content.get("publisher", "Unknown")
                all_news.append({
                    "title": title,
                    "publisher": publisher,
                    "url": url,
                    "ts": pub_ts,
                    "label": annotate(title, publisher),
                })

            time.sleep(0.25)
        except Exception as e:
            logger.warning("拉取 %s 新闻失败: %s", sym, e)

    # 按时间倒序
    all_news.sort(key=lambda x: x["ts"], reverse=True)
    return all_news[:15]


# ============================================================
# HTML 渲染
# ============================================================

def render_html(news_items, period_label):
    now = datetime.now(BEIJING_TZ)
    date_str = now.strftime("%Y年%m月%d日")
    title = f"{period_label} - {date_str}"

    items_html = ""
    for n in news_items:
        items_html += f"""
        <tr>
            <td class="news-item">
                <div class="title">{n['title']}</div>
                <div class="meta">{n['publisher']} · <span class="label">{n['label']}</span></div>
                <a class="link" href="{n['url']}">→ 阅读原文</a>
            </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>
body{{margin:0;padding:0;background:#e8e8e8;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#333}}
.container{{max-width:600px;margin:0 auto;background:#fff}}
.header{{background:#1a1a2e;padding:20px 24px;text-align:center}}
.header h1{{margin:0;font-size:20px;color:#fff;font-weight:700}}
.header .sub{{margin-top:4px;font-size:12px;color:#999}}
.content{{padding:16px 20px}}
table{{width:100%;border-collapse:collapse}}
td.news-item{{padding:12px 0;border-bottom:1px solid #eee}}
.title{{font-size:14px;font-weight:600;line-height:1.4;margin-bottom:4px}}
.meta{{font-size:11px;color:#999;margin-bottom:6px}}
.label{{color:#1a1a2e;font-weight:600}}
.link{{font-size:12px;color:#1a1a2e;text-decoration:none}}
.footer{{padding:16px 20px;text-align:center;font-size:11px;color:#999;background:#f5f5f5}}
@media(max-width:480px){{.header h1{{font-size:17px}}}}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>{title}</h1><div class="sub">共 {len(news_items)} 条</div></div>
<div class="content"><table>{items_html}</table></div>
<div class="footer">每日自动发送 · 数据来源 Yahoo Finance<br>仅供参考，不构成投资建议</div>
</div>
</body>
</html>"""
    return html


# ============================================================
# 发送
# ============================================================

def send_email(html_content, period_label):
    now = datetime.now(BEIJING_TZ)
    date_str = now.strftime("%Y年%m月%d日")
    if not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP 未配置"); return False
    if not RECIPIENTS:
        logger.error("收件人为空"); return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{period_label} - {date_str}"
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, RECIPIENTS, msg.as_string())
        server.quit()
        logger.info("发送成功: %s, %d 条新闻", period_label, sum(1 for _ in html_content.split("<tr><td class=\"news-item\">")) - 1)
        return True
    except Exception as e:
        logger.error("发送失败: %s", e)
        return False


# ============================================================
# 主流程
# ============================================================

def main():
    now = datetime.now(BEIJING_TZ)
    today_start = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    hour = now.hour
    if hour < 12:
        logger.error("此脚本应在 12:00 或 18:00 运行，当前 %d 点", hour)
        sys.exit(1)

    if hour < 15:
        # 午间: 0:00-12:00
        cutoff_start = today_start
        cutoff_end = today_start + 12 * 3600
        label = "午间金融要闻"
    else:
        # 晚间: 12:00-18:00
        cutoff_start = today_start + 12 * 3600
        cutoff_end = today_start + 18 * 3600
        label = "晚间金融要闻"

    logger.info("%s: 窗口 %d ～ %d", label, cutoff_start, cutoff_end)
    news_items = fetch_news(NEWS_SOURCES, cutoff_start, cutoff_end)
    logger.info("过滤后共 %d 条新闻", len(news_items))

    if not news_items:
        logger.warning("无新闻")
        return

    html = render_html(news_items, label)
    if not send_email(html, label):
        sys.exit(1)


if __name__ == "__main__":
    main()
