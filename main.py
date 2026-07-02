import os
import sys
import time
import math
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf
import requests
from jinja2 import Environment, FileSystemLoader

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, RECIPIENTS, EMAIL_SUBJECT_PREFIX,
    MARKET_INDICATORS, FOREX, INDEXES, APAC_INDEXES, APAC_NOTE,
    EUROPE, EUROPE_NOTE, CHINA_INDICES, CHINA_INDICES_NOTE,
    COMMODITIES, MAGNIFICENT_SEVEN, BLUE_CHIPS,
    CHINA_STOCKS, CHINA_STOCKS_NOTE,
    SEMICONDUCTORS, ROBOTICS, ROBOTICS_NOTE,
    NEW_ENERGY, NEW_ENERGY_NOTE,
    CRYPTO_IDS, CRYPTO_NAMES, CRYPTO_UNITS, CRYPTO_VS_CURRENCY, COINGECKO_API,
    TICKER_FALLBACKS, FEAR_GREED_URL,
    COLOR_UP, COLOR_DOWN, COLOR_UNCHANGED, COLOR_BG_HEADER, COLOR_BG_SECTION,
    COLOR_TEXT, COLOR_TEXT_LIGHT,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# 工具函数
# ============================================================

def _isnan(v):
    try:
        return math.isnan(float(v))
    except Exception:
        return False


def _clean(val):
    return None if _isnan(val) else val


def safe_change_pct(current, prev):
    current = _clean(current)
    prev = _clean(prev)
    if current is not None and prev is not None and prev != 0:
        return round((current - prev) / prev * 100, 2)
    return None


def safe_52w_position(price, low, high):
    price = _clean(price)
    low = _clean(low)
    high = _clean(high)
    if price is not None and low is not None and high is not None and high > low:
        pos = (price - low) / (high - low) * 100
        return round(min(max(pos, 0), 100), 1)
    return None


def fmt_price(val, unit):
    """val=None → '-'，否则 unit+val"""
    val = _clean(val)
    if val is None:
        return "-"
    if abs(val) >= 1000:
        return f"{unit}{val:,.2f}"
    elif abs(val) >= 1:
        return f"{unit}{val:,.2f}"
    else:
        return f"{unit}{val:.4f}"


def fmt_change(pct):
    if pct is None:
        return "-"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def calc_hist_return(hist, window):
    if hist is None or len(hist) < 2:
        return None
    try:
        closes = hist["Close"]
        if len(closes) >= window + 1:
            start, end = float(closes.iloc[-(window + 1)]), float(closes.iloc[-1])
        else:
            start, end = float(closes.iloc[0]), float(closes.iloc[-1])
        if not _isnan(start) and not _isnan(end) and start != 0:
            return round((end - start) / start * 100, 2)
    except Exception:
        pass
    return None


def calc_volume_ratio(hist):
    if hist is None or "Volume" not in hist.columns or len(hist) < 6:
        return None, "-"
    try:
        last_vol = hist["Volume"].iloc[-1]
        avg_vol = hist["Volume"].iloc[:-1].mean()
        if avg_vol and avg_vol > 0:
            ratio = round(last_vol / avg_vol, 2)
            if ratio > 1.5:
                return ratio, "放量"
            elif ratio < 0.5:
                return ratio, "缩量"
            return ratio, "正常"
    except Exception:
        pass
    return None, "-"


def generate_commentary(change_pct, vol_label, change_5d, change_20d):
    if change_pct is None:
        return "-"
    if change_pct > 2:
        trend = "大涨"
    elif change_pct > 0.5:
        trend = "上涨"
    elif change_pct > 0:
        trend = "微涨"
    elif change_pct > -0.5:
        trend = "微跌"
    elif change_pct > -2:
        trend = "下跌"
    else:
        trend = "大跌"

    if vol_label == "放量":
        return f"{trend}放量" if change_pct > 0 else f"{trend}放量，警惕"
    elif vol_label == "缩量":
        return f"{trend}缩量"
    else:
        if change_5d is not None and change_20d is not None:
            if change_pct > 0 and change_5d > 0 and change_20d > 0:
                return f"{trend}，趋势向上"
            elif change_pct < 0 and change_5d < 0 and change_20d < 0:
                return f"{trend}，趋势偏弱"
        if abs(change_pct) < 0.3:
            return "窄幅震荡"
        return trend


def sector_summary(items):
    up = sum(1 for i in items if i.get("change_pct") is not None and i["change_pct"] > 0)
    down = sum(1 for i in items if i.get("change_pct") is not None and i["change_pct"] < 0)
    na = len(items) - up - down
    if na == len(items):
        return "数据暂不可用"
    if up > down:
        return f"{up}涨{down}跌，整体偏强"
    elif down > up:
        return f"{up}涨{down}跌，整体偏弱"
    else:
        return f"{up}涨{down}跌，涨跌互现"


# ============================================================
# 贪婪指数
# ============================================================

def fetch_fear_greed():
    try:
        resp = requests.get(FEAR_GREED_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        item = data.get("data", [{}])[0]
        score = item.get("value")
        label_en = item.get("value_classification", "")
        label_map = {
            "Extreme Fear": "极度恐惧", "Fear": "恐惧", "Neutral": "中性",
            "Greed": "贪婪", "Extreme Greed": "极度贪婪",
        }
        label = label_map.get(label_en, label_en)
        if score is not None:
            return float(score), label
    except Exception as e:
        logger.warning("贪婪指数获取失败: %s", e)
    return None, ""


# ============================================================
# 数据获取
# ============================================================

def fetch_yfinance_batch(symbols):
    result = {}
    # 分批下载历史数据
    all_hist_map = {}
    chunk = 12
    for start in range(0, len(symbols), chunk):
        batch = symbols[start:start + chunk]
        s, e = start + 1, min(start + chunk, len(symbols))
        logger.info("下载历史 %d-%d/%d (%d个)...", s, e, len(symbols), len(batch))
        for attempt in range(3):
            try:
                ticker_str = " ".join(batch)
                data = yf.download(ticker_str, period="1mo", group_by="ticker",
                                   progress=False, auto_adjust=True)
                if data is not None and not data.empty:
                    tickers_in_data = []
                    try:
                        tickers_in_data = list(data.columns.get_level_values(0).unique())
                    except Exception:
                        if "Close" in data.columns:
                            tickers_in_data = [batch[0]]
                    for sym in tickers_in_data:
                        try:
                            sym_df = data[sym]
                            if sym_df is not None and not sym_df.empty:
                                all_hist_map[sym] = sym_df
                        except Exception:
                            pass
                    logger.info("批次 %d-%d 成功，拿到 %d 个标的", s, e, len(tickers_in_data))
                    break
                else:
                    logger.warning("批次 %d-%d 返回空，重试 %d/3", s, e, attempt + 1)
                    time.sleep(2)
            except Exception as ex:
                logger.warning("批次 %d-%d 失败: %s，重试 %d/3", s, e, ex, attempt + 1)
                time.sleep(3)

    # 逐个获取 info
    for i, sym in enumerate(symbols):
        time.sleep(0.12)
        info = {}
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info
        except Exception:
            pass

        sym_hist = all_hist_map.get(sym)

        prev_close = _clean(info.get("regularMarketPreviousClose") or info.get("previousClose"))
        current    = _clean(info.get("regularMarketPrice") or info.get("currentPrice"))
        if prev_close is None and sym_hist is not None and len(sym_hist) >= 2:
            prev_close = _clean(sym_hist["Close"].iloc[-2])
        if current is None and sym_hist is not None and len(sym_hist) >= 1:
            current = _clean(sym_hist["Close"].iloc[-1])

        change_5d  = calc_hist_return(sym_hist, 5) if sym_hist is not None else None
        change_20d = calc_hist_return(sym_hist, 20) if sym_hist is not None else None
        vol_ratio, vol_label = calc_volume_ratio(sym_hist) if sym_hist is not None else (None, "-")

        result[sym] = {
            "price":      current,
            "prev_close": prev_close,
            "high_52w":   _clean(info.get("fiftyTwoWeekHigh")),
            "low_52w":    _clean(info.get("fiftyTwoWeekLow")),
            "change_5d":  change_5d,
            "change_20d": change_20d,
            "vol_ratio":  vol_ratio,
            "vol_label":  vol_label,
        }

        if (i + 1) % 20 == 0:
            has_hist = sum(1 for v in result.values() if v.get("change_5d") is not None)
            logger.info("进度 %d/%d，有历史数据: %d", i + 1, len(symbols), has_hist)

    return result


def apply_fallbacks(raw_data):
    for sym, fallback_list in TICKER_FALLBACKS.items():
        data = raw_data.get(sym, {})
        price_ok = _clean(data.get("price")) is not None
        hist_ok  = data.get("change_5d") is not None
        prev_ok  = _clean(data.get("prev_close")) is not None
        if price_ok and prev_ok and hist_ok:
            continue

        reason = []
        if not price_ok: reason.append("price")
        if not prev_ok: reason.append("prev_close")
        if not hist_ok: reason.append("history")
        logger.info("%s 缺失 %s，尝试备选链", sym, ",".join(reason))

        for fb_sym in fallback_list:
            try:
                time.sleep(0.3)
                ticker = yf.Ticker(fb_sym)
                fb_info = ticker.info
                fb_hist = ticker.history(period="1mo")
                p  = _clean(fb_info.get("regularMarketPrice") or fb_info.get("currentPrice"))
                pc = _clean(fb_info.get("regularMarketPreviousClose") or fb_info.get("previousClose"))
                if pc is None and fb_hist is not None and len(fb_hist) >= 2:
                    pc = _clean(fb_hist["Close"].iloc[-2])
                if p is None and fb_hist is not None and len(fb_hist) >= 1:
                    p = _clean(fb_hist["Close"].iloc[-1])
                if p is not None and p != 0:
                    raw_data[sym] = {
                        "price": p, "prev_close": pc,
                        "high_52w": _clean(fb_info.get("fiftyTwoWeekHigh")),
                        "low_52w": _clean(fb_info.get("fiftyTwoWeekLow")),
                        "change_5d": calc_hist_return(fb_hist, 5) if fb_hist is not None else None,
                        "change_20d": calc_hist_return(fb_hist, 20) if fb_hist is not None else None,
                        "vol_ratio": None, "vol_label": "-",
                    }
                    logger.info("%s -> %s 成功", sym, fb_sym)
                    break
            except Exception as e:
                logger.warning("备选 %s 失败: %s", fb_sym, e)
        else:
            logger.warning("%s 所有备选均失败", sym)
    return raw_data


def fetch_crypto_data():
    try:
        ids = ",".join(CRYPTO_IDS)
        url = f"{COINGECKO_API}/coins/markets"
        params = {
            "vs_currency": CRYPTO_VS_CURRENCY,
            "ids": ids, "order": "market_cap_desc", "sparkline": "false",
            "price_change_percentage": "24h,7d,30d",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data_list = resp.json()
        result = {}
        for coin in data_list:
            cid = coin.get("id")
            if cid not in CRYPTO_IDS:
                continue
            price = coin.get("current_price")
            pct_24h = coin.get("price_change_percentage_24h_in_currency")
            pct_7d = coin.get("price_change_percentage_7d_in_currency")
            pct_30d = coin.get("price_change_percentage_30d_in_currency")
            result[cid] = {
                "price": price,
                "prev_close": price / (1 + pct_24h / 100) if price and pct_24h is not None and 1 + pct_24h / 100 > 0 else None,
                "change_pct": pct_24h,
                "change_5d": pct_7d, "change_20d": pct_30d,
                "vol_ratio": None, "vol_label": "-",
                "high_52w": None, "low_52w": None,
            }
        return result
    except Exception as e:
        logger.error("CoinGecko 请求失败: %s", e)
        return {}


# ============================================================
# 数据处理
# ============================================================

def build_item(display_name, raw_data, unit=""):
    price = raw_data.get("price")
    prev_close = raw_data.get("prev_close")
    change_pct = raw_data.get("change_pct")
    if change_pct is None:
        change_pct = safe_change_pct(price, prev_close)
    change_5d = raw_data.get("change_5d")
    change_20d = raw_data.get("change_20d")
    vol_label = raw_data.get("vol_label", "-")
    commentary = generate_commentary(change_pct, vol_label, change_5d, change_20d)
    pos_52w = safe_52w_position(price, raw_data.get("low_52w"), raw_data.get("high_52w"))
    return {
        "name": display_name,
        "unit": unit,
        "price": price,
        "price_fmt": fmt_price(price, unit),
        "change_pct": change_pct,
        "change_fmt": fmt_change(change_pct),
        "change_5d": change_5d,
        "change_5d_fmt": fmt_change(change_5d),
        "change_20d": change_20d,
        "change_20d_fmt": fmt_change(change_20d),
        "vol_label": vol_label,
        "commentary": commentary,
        "pos_52w": pos_52w,
    }


def process_category(category_list, raw_data):
    items = []
    for item in category_list:
        raw = raw_data.get(item["symbol"], {})
        items.append(build_item(item["name"], raw, item.get("unit", "")))
    return items


def process_crypto_category(crypto_list, raw_data):
    items = []
    for item in crypto_list:
        cid = item["cid"]
        data = raw_data.get(cid, {})
        unit = CRYPTO_UNITS.get(cid, "")
        items.append(build_item(item["name"], data, unit))
    return items


# ============================================================
# 邮件
# ============================================================

def render_html(all_data):
    today_str = datetime.now().strftime("%Y年%m月%d日")
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("template.html")
    return template.render(
        title=f"{EMAIL_SUBJECT_PREFIX} - {today_str}",
        date_str=today_str,
        color_up=COLOR_UP,
        color_down=COLOR_DOWN,
        color_unchanged=COLOR_UNCHANGED,
        color_bg_header=COLOR_BG_HEADER,
        color_bg_section=COLOR_BG_SECTION,
        color_text=COLOR_TEXT,
        color_text_light=COLOR_TEXT_LIGHT,
        **all_data,
    )


def send_email(html_content):
    today_str = datetime.now().strftime("%Y年%m月%d日")
    if not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP 未配置")
        return False
    if not RECIPIENTS:
        logger.error("收件人为空")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{EMAIL_SUBJECT_PREFIX} - {today_str}"
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, RECIPIENTS, msg.as_string())
        server.quit()
        logger.info("邮件发送成功，收件人: %s", RECIPIENTS)
        return True
    except Exception as e:
        logger.error("邮件发送失败: %s", e)
        return False


# ============================================================
# 主流程
# ============================================================

def main():
    # 1. 收集所有 yfinance symbols
    all_categories = [
        MARKET_INDICATORS, FOREX, INDEXES, APAC_INDEXES, EUROPE,
        CHINA_INDICES, COMMODITIES, MAGNIFICENT_SEVEN, BLUE_CHIPS,
        CHINA_STOCKS, SEMICONDUCTORS, ROBOTICS, NEW_ENERGY,
    ]
    all_symbols = []
    for cat in all_categories:
        for item in cat:
            all_symbols.append(item["symbol"])

    logger.info("拉取 %d 个标的数据...", len(all_symbols))
    raw_equity = fetch_yfinance_batch(all_symbols)
    raw_equity = apply_fallbacks(raw_equity)

    # 加密货币
    logger.info("拉取加密货币数据...")
    raw_crypto = fetch_crypto_data()

    # 贪婪指数
    fg_score, fg_rating = fetch_fear_greed()
    if fg_score is not None:
        fg_item = {
            "name": f"贪婪指数({fg_rating})",
            "unit": "",
            "price": fg_score,
            "price_fmt": f"{fg_score:.0f} {fg_rating}",
            "change_pct": None, "change_fmt": "-",
            "change_5d": None, "change_5d_fmt": "-",
            "change_20d": None, "change_20d_fmt": "-",
            "vol_label": "-", "commentary": "-", "pos_52w": None,
        }
    else:
        fg_item = {"name": "贪婪指数", "unit": "", "price": None, "price_fmt": "-",
                    "change_pct": None, "change_fmt": "-",
                    "change_5d": None, "change_5d_fmt": "-",
                    "change_20d": None, "change_20d_fmt": "-",
                    "vol_label": "-", "commentary": "-", "pos_52w": None}

    # 2. 组装各分类
    all_data = {
        "indicators":      process_category(MARKET_INDICATORS, raw_equity) + [fg_item],
        "forex":           process_category(FOREX, raw_equity),
        "indexes":         process_category(INDEXES, raw_equity),
        "apac_indexes":    process_category(APAC_INDEXES, raw_equity),
        "apac_note":       APAC_NOTE,
        "europe":          process_category(EUROPE, raw_equity),
        "europe_note":     EUROPE_NOTE,
        "china_indices":   process_category(CHINA_INDICES, raw_equity),
        "china_indices_note": CHINA_INDICES_NOTE,
        "commodities":     process_category(COMMODITIES, raw_equity),
        "mag7":            process_category(MAGNIFICENT_SEVEN, raw_equity),
        "blue_chips":      process_category(BLUE_CHIPS, raw_equity),
        "china_stocks":    process_category(CHINA_STOCKS, raw_equity),
        "china_stocks_note": CHINA_STOCKS_NOTE,
        "semiconductors":  process_category(SEMICONDUCTORS, raw_equity),
        "robotics":        process_category(ROBOTICS, raw_equity),
        "robotics_note":   ROBOTICS_NOTE,
        "new_energy":      process_category(NEW_ENERGY, raw_equity),
        "new_energy_note": NEW_ENERGY_NOTE,
        "cryptos":         process_crypto_category(
            [{"cid": cid, "name": CRYPTO_NAMES[cid]} for cid in CRYPTO_IDS],
            raw_crypto
        ),
    }

    # 3. 板块总结
    for key in ["indicators", "forex", "indexes", "apac_indexes", "europe",
                "china_indices", "commodities", "mag7", "blue_chips",
                "china_stocks", "semiconductors", "robotics", "new_energy", "cryptos"]:
        all_data[f"{key}_summary"] = sector_summary(all_data[key])

    # 4. 渲染 & 发送
    html = render_html(all_data)
    logger.info("HTML 渲染完成")
    if not send_email(html):
        sys.exit(1)


if __name__ == "__main__":
    main()
