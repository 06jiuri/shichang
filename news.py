import os
import sys
import time
import json
import base64
import smtplib
import logging
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf
import requests
from deep_translator import GoogleTranslator

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

NEWS_SOURCES = ["^GSPC", "^DJI", "^IXIC", "NVDA", "TSLA", "^HSI", "000001.SS",
                "^N225", "^KS11", "BABA", "TSM", "000660.KS", "BIDU", "GC=F"]

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


def translate_summary(text, label):
    """翻译英文摘要为中文，加标签前缀"""
    prefix = f"[{label}] "
    if not text or len(text.strip()) < 5:
        return prefix
    try:
        result = GoogleTranslator(source="auto", target="zh-CN").translate(text)
        if result and len(result) > 5:
            return prefix + result
    except Exception:
        pass
    # 翻译失败 → 保留英文原文
    return prefix + text[:90]


# ============================================================
# 拉取新闻
# ============================================================

def fetch_news(source_symbols, cutoff_start, cutoff_end):
    all_news = []
    seen_urls = set()
    source_stats = {}

    for sym in source_symbols:
        stats = {"raw": 0, "first_ts": ""}
        source_news = []
        try:
            ticker = yf.Ticker(sym)
            news_list = ticker.news
            stats["raw"] = len(news_list or [])
            if not news_list:
                source_stats[sym] = stats
                continue
            for item in news_list:
                content = item.get("content", {})
                url = (content.get("canonicalUrl", {}) or {}).get("url", "")
                if not url:
                    url = content.get("clickThroughUrl", {}).get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = content.get("title", "")
                pub_ts = 0
                pub_date_str = content.get("pubDate", "")
                if pub_date_str:
                    try:
                        s = pub_date_str.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(s)
                        pub_ts = int(dt.timestamp())
                    except Exception:
                        pass
                if not stats["first_ts"] and pub_date_str:
                    stats["first_ts"] = pub_date_str[:16]

                publisher = (content.get("provider", {}) or {}).get("displayName", "Unknown")
                raw_summary = content.get("summary", "") or content.get("description", "")
                label = annotate(title, publisher)
                short_text = (raw_summary or "").strip()[:200]
                cn_summary = translate_summary(short_text, label)
                time.sleep(0.15)

                source_news.append({
                    "title": title, "publisher": publisher, "url": url,
                    "ts": pub_ts, "summary": cn_summary,
                })
        except Exception as e:
            logger.warning("拉取 %s 新闻失败: %s", sym, e)

        source_stats[sym] = stats

        # 按时间倒序，每个源取最近 3 条兜底 + 窗口内其余
        source_news.sort(key=lambda x: x["ts"], reverse=True)
        guaranteed = []
        windowed = []
        for item in source_news:
            if len(guaranteed) < 3 and item["ts"] > 0:
                guaranteed.append(item)
            elif item["ts"] > 0 and cutoff_start <= item["ts"] <= cutoff_end:
                windowed.append(item)

        all_news.extend(guaranteed + windowed)
        logger.info("  %s: raw=%d guaranteed=%d windowed=%d first_ts=%s",
                    sym, stats["raw"], len(guaranteed), len(windowed), stats["first_ts"])

    all_news.sort(key=lambda x: x["ts"], reverse=True)
    return all_news[:25]


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
                <div class="meta">{n['publisher']}</div>
                <div class="summary">{n['summary']}</div>
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
.meta{{font-size:11px;color:#999;margin-bottom:4px}}
.summary{{font-size:13px;color:#555;line-height:1.5;margin-bottom:6px}}
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
# 发送状态
# ============================================================

_STATE_API = "https://api.github.com/repos/06jiuri/shichang/contents/state.json"


def _today_str():
    return datetime.now(BEIJING_TZ).strftime("%Y%m%d")


def _state_headers():
    t = os.environ.get("GH_PAT", "")
    return {'Authorization': f'Bearer {t}', 'Accept': 'application/vnd.github+json'}


def already_sent(report_type):
    try:
        h = _state_headers()
        r = requests.get(_STATE_API, headers=h)
        if r.status_code == 200:
            state = json.loads(base64.b64decode(r.json()['content']).decode())
            return state.get(report_type) == _today_str()
    except Exception:
        pass
    return False


def mark_sent(report_type):
    try:
        today = _today_str()
        h = _state_headers()
        r = requests.get(_STATE_API, headers=h)
        sha, state = None, {}
        if r.status_code == 200:
            sha = r.json()['sha']
            state = json.loads(base64.b64decode(r.json()['content']).decode())
        state[report_type] = today
        payload = {
            'message': f'state: {report_type} {today}',
            'content': base64.b64encode(json.dumps(state).encode()).decode(),
        }
        if sha:
            payload['sha'] = sha
        requests.put(_STATE_API, headers=h, json=payload)
    except Exception:
        pass


# ============================================================
# 主流程
# ============================================================

def main():
    now = datetime.now(BEIJING_TZ)
    today_start = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    hour = now.hour

    # 判断类型
    if hour <= 12:
        report_type = "noon"
        cutoff_start = today_start - 6 * 3600
        cutoff_end = today_start + 12 * 3600
        label = "午间金融要闻"
    else:
        report_type = "evening"
        cutoff_start = today_start + 12 * 3600
        cutoff_end = today_start + 18 * 3600
        label = "晚间金融要闻"

    if already_sent(report_type):
        logger.info("%s 今日已发过，跳过", label)
        sys.exit(0)

    logger.info("%s: 窗口 %d ～ %d", label, cutoff_start, cutoff_end)
    news_items = fetch_news(NEWS_SOURCES, cutoff_start, cutoff_end)
    logger.info("过滤后共 %d 条新闻", len(news_items))

    if not news_items:
        logger.warning("无新闻")
        return

    html = render_html(news_items, label)
    if not send_email(html, label):
        sys.exit(1)

    mark_sent(report_type)


if __name__ == "__main__":
    main()
