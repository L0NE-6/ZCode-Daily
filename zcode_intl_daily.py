#!/usr/bin/env python3
"""
🎁 ZCode 国际版 领套餐 - 青龙脚本
------------------------------------------------------------

📌 功能
   ZCode 限时套餐领取（不是传统签到）：
   1. GET  {zcode}/api/v1/zcode-plan/billing/preview?app_version=&platform=
   2. GET  {zcode}/api/v1/marketing/touch?seq=0
   3. 合并两个来源，按 priority 选可领套餐（同优先取最先出现的）
   4. POST {zcode}/api/v1/zcode-plan/billing/claim  body {"plan_id": "..."}

ℹ️ 区域：本脚本用于**国际版**账号（z.ai 侧签发的 JWT）；
   国内版账号请用 zcode_cn_daily.py，两边 JWT 不通用。

🕐 时间口径：所有展示时间固定按北京时间（UTC+8）换算，不随宿主机时区变化。

⚠️ 验证码
   上游通常要求 `X-Aliyun-Captcha-Verify-Param`（阿里云无痕验证）。
   纯脚本无法自动求解，两种做法：
   · 在浏览器里打开 ZCode 领取页，抓一次 claim 请求，把
     X-Aliyun-Captcha-Verify-Param 的值填进账号行（通常是当天一次性）；
   · 或先不填直接跑，上游回 3007 时按日志提示补参数再跑。

🔑 环境变量
   ZCODE_INTL_TOKENS  【必填】多账号用换行或 & 分隔，每条支持：
       jwt
       jwt|device_mid
       jwt|device_mid|captcha_param
       备注|jwt|device_mid|captcha_param
     device_mid 留空会自动生成固定 UUID 存到 zcode_intl_devices.json
     已确认领取记录存到 zcode_intl_claim_ledger.json，仅保留 90 天
   ZCODE_PLAN_ID       【可选】强制领取指定 plan_id
   ZCODE_APP_VERSION   【可选】客户端版本，默认 3.18.0；marketing/touch 需要 3.17.1+
   ZCODE_MARKETING_RECHECK 【可选】领取后复查营销活动位，默认 1
   ZCODE_CAPTCHA_PARAM 【可选】全局验证码参数（会覆盖未填写 captcha 的账号）

   推送通道（均可选）：PUSHPLUS_TOKEN / BARK_URL / WECOM_WEBHOOK / DINGTALK_WEBHOOK / DINGTALK_SECRET

⌨️ 命令
   python zcode_intl_daily.py               预览并领取
   python zcode_intl_daily.py --preview     只预览不领取
   python zcode_intl_daily.py --only 2      只跑第 2 个账号
   python zcode_intl_daily.py --no-notify   不推送

📄 依赖：requests
"""
import base64
import hashlib
import hmac
import json
import os
import platform as host_platform
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests

import urllib3
urllib3.disable_warnings()

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ORIGIN = "https://zcode.z.ai"
PREVIEW_PATH = "/api/v1/zcode-plan/billing/preview"
EVENT_REPORT_PATH = "/api/v1/event/report"
CLAIM_PATH = "/api/v1/zcode-plan/billing/claim"
MARKETING_QUERY_PATH = "/api/v1/marketing/touch"
MARKETING_ACTION_PATH = "/api/v1/marketing/touch/action"
DEFAULT_APP_VERSION = "3.18.0"
MARKETING_MIN_APP_VERSION = "3.17.1"
MARKETING_MAX_DEPTH = 12
MARKETING_MAX_NODES = 4096
MARKETING_MAX_DELIVERIES = 32
MARKETING_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DEVICE_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zcode_intl_devices.json")
REGION = "intl"
CLAIM_LEDGER_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zcode_intl_claim_ledger.json")
CLAIM_LEDGER_VERSION = 1
CLAIM_LEDGER_RETENTION_SECONDS = 90 * 24 * 60 * 60

# 展示时间固定按北京时间（UTC+8）：中国标准时间无夏令时，固定偏移即可，
# 不依赖宿主机时区（青龙 / NAS / 海外 VPS 上口径一致）。
BEIJING_TZ = timezone(timedelta(hours=8))

ONLY = None
PREVIEW_ONLY = False
NO_NOTIFY = False

FAILURE_LABELS = {
    1001: "没有这个套餐",
    1002: "活动还没开始或已经结束",
    1003: "该账号已经领过这一期",
    1004: "当前账号或客户端版本不在活动范围内",
    1005: "今天领取次数已经用完",
    3001: "请求参数不对（重点检查 device_mid）",
    3007: "验证码没通过（需要补充抓到的验证码参数）",
    401: "登录状态失效，重新登录一下吧",
}


def beijing_now():
    return datetime.now(BEIJING_TZ)


def log(msg):
    print("%s %s" % (beijing_now().strftime("[%H:%M:%S]"), msg), flush=True)


def mask(text, keep=6):
    text = str(text or "")
    if len(text) <= keep + 4:
        return text
    return text[:keep] + "****" + text[-4:]


def split_accounts(raw):
    out = []
    for chunk in (raw or "").replace("&", "\n").splitlines():
        chunk = chunk.strip().strip('"\'')
        if chunk and not chunk.startswith("#"):
            out.append(chunk)
    return out


def request(method, url, headers=None, body=None, timeout=15, retries=3):
    last = None
    for attempt in range(retries):
        try:
            session = requests.Session()
            session.trust_env = False
            return session.request(method, url, headers=headers or {},
                                   json=body if body is not None else None,
                                   timeout=timeout, verify=False)
        except Exception as error:
            last = error
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("请求失败: %s" % last)


def json_of(response):
    try:
        return response.json()
    except Exception:
        return {}


def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def app_version():
    return os.environ.get("ZCODE_APP_VERSION", "").strip() or DEFAULT_APP_VERSION


def client_platform():
    system = host_platform.system().lower()
    machine = host_platform.machine().lower()
    if system == "windows":
        return "win32-x64"
    if system == "darwin":
        return "darwin-arm64" if "arm" in machine else "darwin-x64"
    return "linux-arm64" if ("arm" in machine or "aarch64" in machine) else "linux-x64"


def load_device_store():
    try:
        with open(DEVICE_STORE, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_device_store(store):
    try:
        with open(DEVICE_STORE, "w", encoding="utf-8") as handle:
            json.dump(store, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _epoch_seconds(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number > 0 else None


def _safe_identifier(value, limit=256):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or len(value) > limit or any(ord(char) < 32 for char in value):
        return ""
    return value


def stable_account_hash(account):
    user_id = str(account.get("user_id") or "").strip()
    if user_id:
        subject = "user:" + user_id
    else:
        token_hash = hashlib.sha256(str(account.get("jwt") or "").encode("utf-8")).hexdigest()
        subject = "token:" + token_hash
    return hashlib.sha256(("%s:%s" % (REGION, subject)).encode("utf-8")).hexdigest()


def empty_claim_ledger():
    return {"version": CLAIM_LEDGER_VERSION, "claims": []}


def _same_beijing_day(timestamp, now):
    try:
        claimed = datetime.fromtimestamp(int(timestamp), BEIJING_TZ)
    except (TypeError, ValueError, OverflowError, OSError):
        return False
    return claimed.date() == now.astimezone(BEIJING_TZ).date()


def _normalize_claim_ledger(raw, now):
    if not isinstance(raw, dict) or raw.get("version") != CLAIM_LEDGER_VERSION:
        return empty_claim_ledger()
    raw_claims = raw.get("claims")
    if not isinstance(raw_claims, list):
        return empty_claim_ledger()

    now_ts = int(now.timestamp())
    cutoff = now_ts - CLAIM_LEDGER_RETENTION_SECONDS
    claims = []
    seen = set()
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        account_hash = _safe_identifier(item.get("account"), 64)
        region = _safe_identifier(item.get("region"), 16)
        plan_id = _safe_identifier(item.get("plan_id"))
        claimed_at = _epoch_seconds(item.get("claimed_at"))
        expiry = _epoch_seconds(item.get("expiry"))
        if len(account_hash) != 64 or any(char not in "0123456789abcdef" for char in account_hash):
            continue
        if region != REGION or not plan_id or claimed_at is None or claimed_at < cutoff:
            continue
        if claimed_at > now_ts + 24 * 60 * 60:
            continue
        claim = {
            "account": account_hash,
            "region": REGION,
            "plan_id": plan_id,
            "claimed_at": claimed_at,
            "expiry": expiry,
        }
        key = (account_hash, plan_id, claimed_at, expiry)
        if key in seen:
            continue
        seen.add(key)
        claims.append(claim)
    claims.sort(key=lambda claim: claim["claimed_at"])
    return {"version": CLAIM_LEDGER_VERSION, "claims": claims}


def save_claim_ledger(ledger):
    directory = os.path.dirname(os.path.abspath(CLAIM_LEDGER_STORE))
    temp_path = "%s.%s.tmp" % (CLAIM_LEDGER_STORE, uuid.uuid4().hex)
    try:
        os.makedirs(directory, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(ledger, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, CLAIM_LEDGER_STORE)
        return True, ""
    except Exception as error:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return False, str(error)


def load_claim_ledger():
    try:
        with open(CLAIM_LEDGER_STORE, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return empty_claim_ledger()
    except Exception as error:
        log("   ⚠️ 领取台账不可读，按服务端现状继续: %s" % error)
        return empty_claim_ledger()

    if not isinstance(raw, dict) or raw.get("version") != CLAIM_LEDGER_VERSION \
            or not isinstance(raw.get("claims"), list):
        log("   ⚠️ 领取台账格式或版本不支持，按服务端现状继续")
        return empty_claim_ledger()
    ledger = _normalize_claim_ledger(raw, beijing_now())
    if ledger != raw:
        saved, error = save_claim_ledger(ledger)
        if not saved:
            log("   ⚠️ 领取台账清理后保存失败: %s" % error)
    return ledger


def _claim_matches_plan(claim, plan, now):
    if claim.get("plan_id") != plan.get("plan_id"):
        return False
    now_ts = int(now.timestamp())
    claim_expiry = _epoch_seconds(claim.get("expiry"))
    claimed_at = _epoch_seconds(claim.get("claimed_at"))
    plan_expiry = _epoch_seconds(plan.get("ends_at"))
    plan_start = _epoch_seconds(plan.get("starts_at"))
    if claim_expiry is not None and claim_expiry <= now_ts:
        return False
    if claim_expiry is not None and plan_start is not None:
        if plan_start >= claim_expiry:
            return False
        if plan_expiry is not None and claimed_at is not None and plan_expiry <= claimed_at:
            return False
        return True
    if claim_expiry is not None and plan_expiry is not None and claim_expiry == plan_expiry:
        return True
    return _same_beijing_day(claim.get("claimed_at"), now)


def find_claimed_plan(ledger, account_hash, plan, now):
    for claim in ledger.get("claims", []):
        if claim.get("account") == account_hash and claim.get("region") == REGION \
                and _claim_matches_plan(claim, plan, now):
            return claim
    return None


def latest_account_claim(ledger, account_hash, now, plan_id=""):
    candidates = [
        claim for claim in ledger.get("claims", [])
        if claim.get("account") == account_hash and claim.get("region") == REGION
        and (not plan_id or claim.get("plan_id") == plan_id)
    ]
    same_day = [claim for claim in candidates if _same_beijing_day(claim.get("claimed_at"), now)]
    if same_day:
        return max(same_day, key=lambda claim: claim["claimed_at"])
    now_ts = int(now.timestamp())
    active = [
        claim for claim in candidates
        if _epoch_seconds(claim.get("expiry")) is not None
        and _epoch_seconds(claim.get("expiry")) > now_ts
    ]
    if active:
        return max(active, key=lambda claim: claim["claimed_at"])
    return None


def claim_status_message(claim, now):
    plan_id = claim.get("plan_id")
    expiry = _epoch_seconds(claim.get("expiry"))
    if _same_beijing_day(claim.get("claimed_at"), now):
        message = "今日已领取: %s" % plan_id
    else:
        message = "当前无新套餐；最近已领取: %s" % plan_id
    if expiry:
        message += "（有效期至 %s）" % format_time(expiry)
    return message


def record_confirmed_claim(ledger, account_hash, plan, result, now):
    expiry = _epoch_seconds(plan.get("ends_at")) \
        or _epoch_seconds(result.get("ends_at", result.get("endsAt")))
    claim = {
        "account": account_hash,
        "region": REGION,
        "plan_id": plan["plan_id"],
        "claimed_at": int(now.timestamp()),
        "expiry": expiry,
    }
    claims = []
    for existing in ledger.get("claims", []):
        same_period = (
            existing.get("account") == account_hash
            and existing.get("region") == REGION
            and existing.get("plan_id") == claim["plan_id"]
            and (
                _epoch_seconds(existing.get("expiry")) == expiry
                or (
                    _epoch_seconds(existing.get("expiry")) is None
                    and expiry is None
                    and _same_beijing_day(existing.get("claimed_at"), now)
                )
            )
        )
        if not same_period:
            claims.append(existing)
    claims.append(claim)
    ledger["claims"] = claims
    ledger = _normalize_claim_ledger(ledger, now)
    return save_claim_ledger(ledger)


def stable_device_mid(jwt, provided, note):
    if provided:
        return provided
    key = hashlib.sha256(jwt.encode("utf-8")).hexdigest()[:16]
    store = load_device_store()
    mid = store.get(key, {}).get("mid", "")
    if not mid:
        mid = str(uuid.uuid4())
        store[key] = {"mid": mid, "note": note, "at": int(time.time())}
        save_device_store(store)
        log("   🆕 已为该账号生成固定 device_mid: %s" % mid)
    return mid



# ---------- 激活事件上报 ----------
# 领取资格的前置动作：官方客户端启动 / 日活时会向事件接口报两条
# （app_launch、app_daily_active），运营系统据此发放资格，套餐探测才列得出来。
# 纯脚本走不到那条链，所以领取前主动补报一次（失败只记一行日志，不阻断领取）。


def local_timezone():
    if host_platform.system().lower() != "windows":
        return "unknown"
    try:
        import subprocess
        out = subprocess.run(["tzutil", "/g"], capture_output=True, text=True, timeout=5)
        name = (out.stdout or "").strip()
        return {
            "China Standard Time": "Asia/Shanghai",
            "China Daylight Time": "Asia/Shanghai",
            "Singapore Standard Time": "Asia/Singapore",
            "Tokyo Standard Time": "Asia/Tokyo",
            "UTC": "UTC",
        }.get(name, "unknown")
    except Exception:
        return "unknown"


def local_os_version():
    if host_platform.system().lower() != "windows":
        return ""
    try:
        import subprocess
        out = subprocess.run(
            ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion",
             "/v", "CurrentBuildNumber"],
            capture_output=True, text=True, timeout=5)
        for line in (out.stdout or "").splitlines():
            if "CurrentBuildNumber" in line:
                parts = line.split()
                if parts:
                    return "10.0." + parts[-1]
    except Exception:
        pass
    return ""


def os_category():
    system = host_platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def activation_event_body(event, user_id, device_mid):
    return {
        "event_id": str(uuid.uuid4()),
        "client_timezone": local_timezone(),
        "client_language": "zh-CN",
        "element_name": event,
        "event_region": "app",
        "event_type": "view",
        "event_text": "",
        "event_extra_detail": {},
        "user_id": user_id,
        "screen_resolution": "2560x1440",
        "app_version": app_version(),
        "device_os_category": os_category(),
        "device_os_version": local_os_version(),
        "device_mid": device_mid,
        "source_page": "",
        "source_element": "{}",
    }


def report_activation(user_id, device_mid):
    """补报 app_launch / app_daily_active；返回 (是否成功, 说明)。"""
    if os.environ.get("ZCODE_ACTIVATION", "1").strip() == "0":
        return False, "已关闭激活事件上报"
    if not user_id:
        return False, "缺少用户标识，跳过激活事件上报"
    url = ORIGIN + EVENT_REPORT_PATH
    errors = []
    for event in ("app_launch", "app_daily_active"):
        try:
            response = request("POST", url, headers={}, body=activation_event_body(event, user_id, device_mid), timeout=10)
            payload = json_of(response)
            if response.status_code != 200 or payload.get("code") != 0:
                errors.append("%s: HTTP %s code=%s" % (event, response.status_code, payload.get("code")))
        except Exception as error:
            errors.append("%s: %s" % (event, error))
    if errors:
        return False, "；".join(errors)
    return True, "ok"

# ---------- 上游协议 ----------

def preview(region_jwt, device_mid):
    url = "%s%s?app_version=%s&platform=%s" % (ORIGIN, PREVIEW_PATH, app_version(), client_platform())
    headers = {"X-Device-Mid": device_mid} if device_mid else {}
    if region_jwt:
        headers["Authorization"] = "Bearer %s" % region_jwt
    return request("GET", url, headers=headers)


def claim(jwt, plan_id, device_mid, captcha):
    headers = {
        "Authorization": "Bearer %s" % jwt,
        "Content-Type": "application/json",
        "X-ZCode-App-Version": app_version(),
        "X-Platform": client_platform(),
    }
    if captcha:
        headers["X-Aliyun-Captcha-Verify-Param"] = captcha
    if device_mid:
        headers["X-Device-Mid"] = device_mid
    return request("POST", ORIGIN + CLAIM_PATH, headers=headers, body={"plan_id": plan_id})


def _int_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _version_tuple(value):
    text = str(value or "").strip().lower().lstrip("v").split("-", 1)[0]
    if not text:
        return None
    parts = text.split(".")
    numbers = []
    for part in parts[:3]:
        try:
            numbers.append(int(part))
        except (TypeError, ValueError):
            return None
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def _version_at_least(value, minimum):
    current = _version_tuple(value)
    required = _version_tuple(minimum)
    if current is None or required is None:
        return False
    return current >= required


def _marketing_headers(jwt, device_mid):
    headers = {
        "X-Client-Language": "zh-CN",
        "X-ZCode-App-Version": app_version(),
    }
    if jwt:
        headers["Authorization"] = "Bearer %s" % jwt
    if device_mid:
        headers["X-Device-Mid"] = device_mid
    return headers


def _response_too_large(response):
    content = getattr(response, "content", None)
    return isinstance(content, (bytes, bytearray)) and len(content) > MARKETING_MAX_RESPONSE_BYTES


def _source_result(ok, plans=None, error="", skipped=False, deployed=True, delivery_count=None):
    return {
        "ok": bool(ok),
        "plans": plans or [],
        "error": error,
        "skipped": bool(skipped),
        "deployed": bool(deployed),
        "delivery_count": delivery_count,
    }


def _payload_code(payload):
    return _int_value(payload.get("code")) if isinstance(payload, dict) else None


def _payload_error(payload, status_code):
    if isinstance(payload, dict):
        return first_text(payload.get("msg"), payload.get("message")) or ("HTTP %s" % status_code)
    return "HTTP %s" % status_code


def _parse_entitlements(raw):
    entitlements = []
    if not isinstance(raw, list):
        return entitlements
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        show_name = first_text(entry.get("show_name"), entry.get("showName"), entry.get("name"))
        if not show_name:
            continue
        entitlements.append({
            "name": show_name,
            "unit": first_text(entry.get("unit_type"), entry.get("unitType"), entry.get("unit")),
            "grant": entry.get("grant_units", entry.get("grantUnits", entry.get("grant", 0))),
            "period": first_text(entry.get("period")),
        })
    return entitlements


def _normalize_plan(raw, source, default_priority=0, campaign_ids=None):
    if not isinstance(raw, dict):
        return None
    plan_id = _safe_identifier(first_text(raw.get("plan_id"), raw.get("planId")))
    if not plan_id:
        return None
    priority = _int_value(raw.get("priority"))
    if priority is None:
        priority = default_priority
    campaigns = []
    for campaign in campaign_ids or []:
        campaign = _safe_identifier(campaign)
        if campaign and campaign not in campaigns:
            campaigns.append(campaign)
    return {
        "plan_id": plan_id,
        "name": first_text(raw.get("name")) or plan_id,
        "description": first_text(raw.get("description")),
        "priority": priority,
        "starts_at": _epoch_seconds(raw.get("starts_at", raw.get("startsAt"))),
        "ends_at": _epoch_seconds(raw.get("ends_at", raw.get("endsAt"))),
        "entitlements": _parse_entitlements(raw.get("entitlements")),
        "sources": [source],
        "campaign_ids": campaigns,
    }


def parse_plans(payload):
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    raw = data.get("plans")
    plans = []
    if isinstance(raw, list):
        for item in raw:
            plan = _normalize_plan(item, "billing")
            if plan is not None:
                plans.append(plan)
    return plans


def _merge_plan_into(existing, incoming):
    if not existing.get("name") or existing.get("name") == existing.get("plan_id"):
        existing["name"] = incoming.get("name") or existing.get("name")
    if not existing.get("description"):
        existing["description"] = incoming.get("description", "")
    existing["priority"] = max(existing.get("priority", 0), incoming.get("priority", 0))
    if existing.get("starts_at") is None and incoming.get("starts_at") is not None:
        existing["starts_at"] = incoming["starts_at"]
    if existing.get("ends_at") is None and incoming.get("ends_at") is not None:
        existing["ends_at"] = incoming["ends_at"]
    if not existing.get("entitlements") and incoming.get("entitlements"):
        existing["entitlements"] = [dict(entry) for entry in incoming["entitlements"]]
    for source in incoming.get("sources", []):
        if source not in existing["sources"]:
            existing["sources"].append(source)
    for campaign in incoming.get("campaign_ids", []):
        if campaign not in existing["campaign_ids"]:
            existing["campaign_ids"].append(campaign)


def merge_plan_sources(*groups):
    plans = []
    by_id = {}
    for group in groups:
        for raw in group or []:
            if not isinstance(raw, dict):
                continue
            plan_id = _safe_identifier(raw.get("plan_id"))
            if not plan_id:
                continue
            incoming = {
                "plan_id": plan_id,
                "name": first_text(raw.get("name")) or plan_id,
                "description": first_text(raw.get("description")),
                "priority": _int_value(raw.get("priority")) or 0,
                "starts_at": _epoch_seconds(raw.get("starts_at")),
                "ends_at": _epoch_seconds(raw.get("ends_at")),
                "entitlements": _parse_entitlements(raw.get("entitlements")),
                "sources": list(raw.get("sources") or []),
                "campaign_ids": list(raw.get("campaign_ids") or []),
            }
            existing = by_id.get(plan_id)
            if existing is None:
                existing = incoming
                by_id[plan_id] = existing
                plans.append(existing)
            else:
                _merge_plan_into(existing, incoming)
    return plans


def _marketing_plan_metadata(raw, default_priority):
    plan = _normalize_plan(raw, "marketing", default_priority)
    if plan is None:
        plan = _normalize_plan(raw.get("zcode_plan") if isinstance(raw, dict) else None,
                               "marketing", default_priority)
    return plan


def _walk_marketing_delivery(delivery):
    metadata = {}
    action_plan_ids = []
    seen = set()
    budget = [MARKETING_MAX_NODES]
    delivery_priority = _int_value(delivery.get("priority")) or 0

    def remember_plan(plan):
        if plan is None:
            return
        existing = metadata.get(plan["plan_id"])
        if existing is None:
            metadata[plan["plan_id"]] = plan
        else:
            _merge_plan_into(existing, plan)

    def walk(node, depth):
        if depth > MARKETING_MAX_DEPTH or budget[0] <= 0:
            return
        if isinstance(node, (dict, list)):
            marker = id(node)
            if marker in seen:
                return
            seen.add(marker)
        budget[0] -= 1
        if isinstance(node, dict):
            remember_plan(_marketing_plan_metadata(node, delivery_priority))
            nested = node.get("zcode_plan")
            if isinstance(nested, dict):
                remember_plan(_normalize_plan(nested, "marketing", delivery_priority))
            action = node.get("action")
            if isinstance(action, dict) and action.get("type") == "claim_zcode_plan":
                args = action.get("args")
                plan_id = _safe_identifier(args.get("plan_id")) if isinstance(args, dict) else ""
                if plan_id and plan_id not in action_plan_ids:
                    action_plan_ids.append(plan_id)
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                walk(value, depth + 1)

    walk(delivery, 0)
    campaign_id = _safe_identifier(delivery.get("campaign_id"))
    found = []
    for plan_id in action_plan_ids:
        plan = metadata.get(plan_id)
        if plan is None:
            plan = {
                "plan_id": plan_id,
                "name": plan_id,
                "description": "",
                "priority": delivery_priority,
                "starts_at": None,
                "ends_at": None,
                "entitlements": [],
                "sources": ["marketing"],
                "campaign_ids": [],
            }
        else:
            plan = dict(plan)
            plan["entitlements"] = [dict(entry) for entry in plan.get("entitlements", [])]
            plan["sources"] = list(plan.get("sources", []))
            plan["campaign_ids"] = list(plan.get("campaign_ids", []))
        if campaign_id and campaign_id not in plan["campaign_ids"]:
            plan["campaign_ids"].append(campaign_id)
        found.append(plan)
    return found


def parse_marketing_plans(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    deliveries = data.get("deliveries") if isinstance(data, dict) else None
    if not isinstance(deliveries, list):
        return [], "营销套餐查询失败：上游未返回有效活动列表"
    if len(deliveries) > MARKETING_MAX_DELIVERIES:
        return [], "营销套餐查询失败：活动列表超过上限 %d" % MARKETING_MAX_DELIVERIES
    plans = []
    for delivery in deliveries:
        if not isinstance(delivery, dict):
            continue
        plans.extend(_walk_marketing_delivery(delivery))
    return merge_plan_sources(plans), ""


def query_billing_plans(jwt, device_mid):
    try:
        response = preview(jwt, device_mid)
    except Exception as error:
        return _source_result(False, error="套餐预览请求失败: %s" % error)
    if response.status_code == 404:
        return _source_result(False, error="领取接口尚未部署（活动未上线）")
    if response.status_code == 401:
        return _source_result(False, error="登录状态失效，重新登录一下吧该账号")
    if _response_too_large(response):
        return _source_result(False, error="套餐预览查询失败：响应超过大小上限")
    try:
        payload = response.json()
    except Exception:
        return _source_result(False, error="套餐预览查询失败：上游响应不是 JSON")
    if not isinstance(payload, dict):
        return _source_result(False, error="套餐预览查询失败：上游响应格式异常")
    code = _payload_code(payload)
    if response.status_code != 200 or code not in (0, None):
        return _source_result(False, error="套餐预览查询失败: %s" % _payload_error(payload, response.status_code))
    return _source_result(True, plans=parse_plans(payload))


def query_marketing_plans(jwt, device_mid):
    version = app_version()
    if not _version_at_least(version, MARKETING_MIN_APP_VERSION):
        return _source_result(
            False,
            error="营销套餐查询跳过：ZCODE_APP_VERSION=%s 低于 marketing/touch 最低版本 %s"
                  % (version, MARKETING_MIN_APP_VERSION),
            skipped=True,
        )
    try:
        response = request(
            "GET",
            ORIGIN + MARKETING_QUERY_PATH + "?seq=0",
            headers=_marketing_headers(jwt, device_mid),
            timeout=15,
        )
    except Exception as error:
        return _source_result(False, error="营销套餐查询失败: %s" % error)
    if response.status_code == 404:
        return _source_result(True, plans=[], deployed=False)
    if _response_too_large(response):
        return _source_result(False, error="营销套餐查询失败：响应超过大小上限")
    try:
        payload = response.json()
    except Exception:
        return _source_result(False, error="营销套餐查询失败：上游响应不是 JSON")
    if response.status_code != 200 or _payload_code(payload) != 0 \
            or (isinstance(payload, dict) and payload.get("success") is False):
        return _source_result(
            False,
            error="营销套餐查询失败: %s" % _payload_error(payload, response.status_code),
        )
    plans, error = parse_marketing_plans(payload)
    if error:
        return _source_result(False, error=error)
    data = payload.get("data") if isinstance(payload, dict) else None
    deliveries = data.get("deliveries") if isinstance(data, dict) else None
    return _source_result(True, plans=plans, delivery_count=len(deliveries))


def source_warning(*sources):
    failures = []
    skipped = []
    for label, result in sources:
        if result.get("ok"):
            continue
        item = "%s: %s" % (label, result.get("error") or "未知错误")
        if result.get("skipped"):
            skipped.append(item)
        else:
            failures.append(item)
    parts = []
    if failures:
        parts.append("部分来源失败: %s" % "；".join(failures))
    if skipped:
        parts.append("来源未查询: %s" % "；".join(skipped))
    return "；" + "；".join(parts) if parts else ""


def confirm_marketing_claim(jwt, device_mid, plan):
    campaign_ids = []
    for campaign in plan.get("campaign_ids") or []:
        campaign = _safe_identifier(campaign)
        if campaign and campaign not in campaign_ids:
            campaign_ids.append(campaign)
    if not campaign_ids:
        return None, ""
    errors = []
    confirmed = 0
    for campaign_id in campaign_ids:
        try:
            response = request(
                "POST",
                ORIGIN + MARKETING_ACTION_PATH,
                headers=_marketing_headers(jwt, device_mid),
                body={"campaign_id": campaign_id, "action_type": "confirm"},
                timeout=15,
                retries=1,
            )
        except Exception as error:
            errors.append("%s: %s" % (campaign_id, error))
            continue
        if _response_too_large(response):
            errors.append("%s: 响应超过大小上限" % campaign_id)
            continue
        try:
            payload = response.json()
        except Exception:
            errors.append("%s: 响应不是 JSON" % campaign_id)
            continue
        if 200 <= response.status_code < 300 and _payload_code(payload) == 0 \
                and not (isinstance(payload, dict) and payload.get("success") is False):
            confirmed += 1
        else:
            errors.append("%s: %s" % (campaign_id, _payload_error(payload, response.status_code)))
    if errors:
        if confirmed:
            return False, "营销回执部分成功（%d/%d）: %s" % (
                confirmed, len(campaign_ids), "；".join(errors))
        return False, "营销回执失败: %s" % "；".join(errors)
    return True, "营销回执已确认（%d 个 campaign）" % confirmed


def recheck_marketing_claim(jwt, device_mid, plan):
    if os.environ.get("ZCODE_MARKETING_RECHECK", "1").strip() == "0":
        return ""
    result = query_marketing_plans(jwt, device_mid)
    if not result.get("ok"):
        return "；营销复查询失败: %s" % result.get("error")
    if not result.get("deployed", True):
        return "；营销复查询接口未部署，不能作为活动位下线证据"
    delivery_count = result.get("delivery_count")
    if delivery_count == 0:
        return "；营销活动位已下线（正向证据）"
    remaining = any(item.get("plan_id") == plan.get("plan_id") for item in result.get("plans", []))
    if remaining:
        return "；营销活动位仍返回该套餐（不作为失败）"
    if delivery_count is not None:
        return "；营销活动位仍有 %d 条，但未匹配到该套餐（不作为下线证据）" % delivery_count
    return "；营销复查询未返回 deliveries 数量，不能作为活动位下线证据"


def finalize_marketing_claim(account, plan):
    if PREVIEW_ONLY or not plan.get("campaign_ids"):
        return ""
    notes = []
    confirmed, confirm_note = confirm_marketing_claim(account["jwt"], account["device_mid"], plan)
    if confirmed is True:
        notes.append(confirm_note)
    elif confirmed is False:
        notes.append(confirm_note + "（不影响已确认领取）")
    recheck_note = recheck_marketing_claim(account["jwt"], account["device_mid"], plan)
    if recheck_note:
        notes.append(recheck_note.lstrip("；"))
    return "；" + "；".join(notes) if notes else ""


def _best_plan(plans):
    best = None
    for plan in plans:
        if best is None or plan.get("priority", 0) > best.get("priority", 0):
            best = plan
    return best


def pick_plan(plans):
    wanted = os.environ.get("ZCODE_PLAN_ID", "").strip()
    if wanted:
        for plan in plans:
            if plan["plan_id"] == wanted:
                return plan
        return None
    best = None
    for plan in plans:          # 同优先级取最先出现的
        if best is None or plan["priority"] > best["priority"]:
            best = plan
    return best


def plan_window_state(plan, now):
    now_ts = int(now.timestamp())
    starts_at = _epoch_seconds(plan.get("starts_at"))
    ends_at = _epoch_seconds(plan.get("ends_at"))
    if starts_at is not None and now_ts < starts_at:
        return "future"
    if ends_at is not None and now_ts >= ends_at:
        return "expired"
    return "active"


def format_time(seconds):
    if not seconds:
        return "立即"
    try:
        return datetime.fromtimestamp(int(seconds), BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(seconds)


def describe_plan(plan):
    text = plan["name"]
    if plan.get("entitlements"):
        parts = []
        for entry in plan["entitlements"]:
            unit = entry.get("unit") or ""
            grant = entry.get("grant") or 0
            period = "每日" if entry.get("period") == "daily" else "一次性"
            parts.append("%s %s%s（%s）" % (entry["name"], grant, unit, period))
        text += "：" + "，".join(parts)
    return text


def _plan_sources(plan):
    sources = plan.get("sources") or []
    return "/".join(sources) if sources else "unknown"


def _finish_already_claimed(account, plan, claim_record, now, warning):
    marketing_note = finalize_marketing_claim(account, plan)
    return True, claim_status_message(claim_record, now) + marketing_note + warning


def do_claim(account):
    now = beijing_now()
    ledger = load_claim_ledger()
    account_hash = stable_account_hash(account)
    activation_ok, activation_note = report_activation(account.get("user_id", ""), account["device_mid"])
    if activation_ok:
        log("   📣 已补报激活事件（app_launch / app_daily_active）")
    else:
        log("   ℹ️ 激活事件未上报: %s" % activation_note)
    billing = query_billing_plans(account["jwt"], account["device_mid"])
    marketing = query_marketing_plans(account["jwt"], account["device_mid"])
    now = beijing_now()
    plans = merge_plan_sources(billing.get("plans", []), marketing.get("plans", []))
    warning = source_warning(("billing", billing), ("marketing", marketing))
    if not plans:
        wanted = os.environ.get("ZCODE_PLAN_ID", "").strip()
        ledger_claim = latest_account_claim(ledger, account_hash, now, wanted)
        if ledger_claim is None and wanted:
            ledger_claim = latest_account_claim(ledger, account_hash, now)
        if ledger_claim is not None:
            log("   📒 服务端两来源为空，本地台账确认已有领取记录")
            return True, claim_status_message(ledger_claim, now) + warning
        if warning:
            return False, "套餐来源查询未完成且本地台账无命中%s" % warning
        return False, "当前无新套餐（billing / marketing 均未返回可领套餐，本地台账无命中）"

    target = pick_plan(plans)
    if target is None:
        wanted = os.environ.get("ZCODE_PLAN_ID", "").strip()
        ledger_claim = latest_account_claim(ledger, account_hash, now, wanted)
        if ledger_claim is not None:
            return True, claim_status_message(ledger_claim, now) + warning
        if warning:
            return False, "指定套餐未在完整来源中确认%s" % warning
        return False, "指定的 ZCODE_PLAN_ID 不在可领列表里"
    wanted = os.environ.get("ZCODE_PLAN_ID", "").strip()
    target_claim = find_claimed_plan(ledger, account_hash, target, now)
    if wanted and target_claim is not None:
        log("   📒 本地台账确认该活动期已领取，跳过重复请求")
        return _finish_already_claimed(account, target, target_claim, now, warning)

    candidates = [target] if wanted else plans
    claimed_candidates = []
    available = []
    for candidate in candidates:
        claim_record = find_claimed_plan(ledger, account_hash, candidate, now)
        if claim_record is None:
            available.append(candidate)
        else:
            claimed_candidates.append((candidate, claim_record))
    if not available:
        candidate, claim_record = claimed_candidates[0]
        log("   📒 当前套餐活动期均已在本地台账确认")
        return _finish_already_claimed(account, candidate, claim_record, now, warning)

    future = []
    active = []
    expired = []
    for candidate in available:
        state = plan_window_state(candidate, now)
        if state == "future":
            future.append(candidate)
        elif state == "expired":
            expired.append(candidate)
        else:
            active.append(candidate)
    if not active:
        if future:
            plan = min(future, key=lambda item: item.get("starts_at") or 0)
            message = "活动窗口未开启: %s（北京时间 %s 开启）" % (
                plan["name"], format_time(plan.get("starts_at")))
            return False, message + warning
        plan = _best_plan(expired)
        message = "活动已结束: %s（北京时间 %s 结束）" % (
            plan["name"], format_time(plan.get("ends_at")))
        return False, message + warning
    plan = _best_plan(active)

    log("   🎯 目标套餐: %s [来源: %s]" % (describe_plan(plan), _plan_sources(plan)))
    if PREVIEW_ONLY:
        return False, "仅预览（--preview），未发起领取" + warning

    claim_response = claim(account["jwt"], plan["plan_id"], account["device_mid"], account["captcha"])
    body = json_of(claim_response)
    code = _payload_code(body)
    if claim_response.status_code == 200 and code == 0 and isinstance(body.get("data"), dict) \
            and isinstance(body["data"].get("plan"), dict):
        result = body["data"]["plan"]
        starts = result.get("starts_at", result.get("startsAt"))
        ends = result.get("ends_at", result.get("endsAt"))
        saved, save_error = record_confirmed_claim(ledger, account_hash, plan, result, beijing_now())
        suffix = "" if saved else "；本地领取台账保存失败: %s" % save_error
        marketing_note = finalize_marketing_claim(account, plan)
        return True, "领取成功: %s（%s ~ %s）%s%s%s" % (
            plan["name"], format_time(starts), format_time(ends), suffix, marketing_note, warning)

    label = FAILURE_LABELS.get(code)
    if code == 1003:
        saved, save_error = record_confirmed_claim(ledger, account_hash, plan, {}, beijing_now())
        suffix = "" if saved else "；本地领取台账保存失败: %s" % save_error
        marketing_note = finalize_marketing_claim(account, plan)
        return True, "该账号已领取过这一期%s%s%s" % (suffix, marketing_note, warning)
    if label is None:
        label = first_text(body.get("msg"), body.get("message")) or ("HTTP %s" % claim_response.status_code)
    if code == 1005:
        plan = (body.get("data") or {}).get("plan") if isinstance(body.get("data"), dict) else {}
        ends = plan.get("ends_at", plan.get("endsAt")) if isinstance(plan, dict) else None
        if ends:
            return False, "领取未成功: %s（下轮重试不早于 %s）%s" % (
                label, format_time(ends), warning)
    if code == 3007 and not account["captcha"]:
        label += "；从浏览器抓一次 claim 请求，把该头填到账号行第 4 段或 ZCODE_CAPTCHA_PARAM"
    if code == 3001:
        label += "；检查 device_mid 与客户端版本；若带验证码，确认参数未过期"
    return False, "领取未成功: %s（code=%s）%s" % (label, code, warning)


# ---------- 推送 ----------

def post_json(url, payload, timeout=20):
    session = requests.Session()
    session.trust_env = False
    return session.post(url, json=payload, timeout=timeout, verify=False)


def _env(name):
    return os.environ.get(name, "").strip()


def notify_pushplus(title, content):
    token = _env("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        text = (content[:18000] + "\n...(已截断)") if len(content) > 18000 else content
        answer = post_json("https://www.pushplus.plus/send",
                           {"token": token, "title": title, "content": text, "template": "txt"})
        return str(json_of(answer).get("code")) == "200"
    except Exception:
        return False


def notify_bark(title, content):
    endpoint = _env("BARK_URL").rstrip("/")
    if not endpoint:
        return False
    try:
        answer = post_json(endpoint, {"title": title, "body": content, "group": "ZCode"})
        return json_of(answer).get("code") == 200
    except Exception:
        return False


def notify_wecom(title, content):
    hook = _env("WECOM_WEBHOOK")
    if not hook:
        return False
    if not hook.startswith("http"):
        hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
    try:
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": ("%s\n%s" % (title, content))[:2000]}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_dingtalk(title, content):
    hook = _env("DINGTALK_WEBHOOK")
    if not hook:
        return False
    try:
        secret = _env("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            digest = hmac.new(secret.encode(), ("%s\n%s" % (stamp, secret)).encode(),
                              hashlib.sha256).digest()
            hook += ("&" if "?" in hook else "?") + "timestamp=%s&sign=%s" % (
                stamp, requests.utils.quote(base64.b64encode(digest)))
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": "%s\n%s" % (title, content)}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_ql(title, content):
    try:
        from notify import send as panel_send
        panel_send(title, content)
        return True
    except Exception:
        pass
    endpoint = _env("QL_URL").rstrip("/")
    token = _env("QL_TOKEN")
    if not endpoint or not token:
        return False
    try:
        session = requests.Session()
        session.trust_env = False
        answer = session.post(endpoint + "/api/system/notify?token=" + token,
                              json={"title": title, "content": content}, timeout=15, verify=False)
        return str(json_of(answer).get("code")) in ("0", "200")
    except Exception:
        return False


def notify_all(title, content):
    handlers = (notify_pushplus, notify_bark, notify_wecom, notify_dingtalk, notify_ql)
    if not any(handler(title, content) for handler in handlers):
        log("（未配置推送渠道，本次只记录日志）")


# ---------- 账号解析与主流程 ----------

def looks_like_jwt(value):
    value = (value or "").strip()
    return value.startswith("eyJ") or value.count(".") >= 2


def jwt_user_id(jwt):
    """从 JWT 载荷里取用户标识（激活事件上报用）；取不到返回空串。"""
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return ""
    for key in ("user_id", "userId", "uid", "sub", "id"):
        value = claims.get(key) if isinstance(claims, dict) else None
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    data = claims.get("data") if isinstance(claims, dict) else None
    if isinstance(data, dict):
        for key in ("id", "user_id", "uid"):
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return ""


def parse_accounts(raw):
    accounts = []
    default_captcha = os.environ.get("ZCODE_CAPTCHA_PARAM", "").strip()
    for index, line in enumerate(split_accounts(raw), 1):
        parts = [part.strip() for part in line.split("|")]
        note = "账号%d" % index
        jwt = mid = captcha = ""
        if len(parts) >= 4:
            note, jwt, mid, captcha = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 3:
            first, second, third = parts
            if looks_like_jwt(first):
                jwt, mid, captcha = first, second, third
            else:
                note, jwt, mid = first, second, third
        elif len(parts) == 2:
            first, second = parts
            if looks_like_jwt(first) and not looks_like_jwt(second):
                jwt, mid = first, second
            elif looks_like_jwt(second):
                note, jwt = first, second
            else:
                jwt, mid = first, second
        else:
            jwt = parts[0]
        if not jwt:
            continue
        if not captcha:
            captcha = default_captcha
        mid = stable_device_mid(jwt, mid, note)
        accounts.append({"note": note, "jwt": jwt, "device_mid": mid, "captcha": captcha,
                         "user_id": jwt_user_id(jwt)})
    return accounts


def main():
    global ONLY, PREVIEW_ONLY, NO_NOTIFY
    args = sys.argv[1:]
    if "--preview" in args:
        PREVIEW_ONLY = True
    if "--no-notify" in args:
        NO_NOTIFY = True
    if "--only" in args:
        try:
            ONLY = int(args[args.index("--only") + 1])
        except Exception:
            ONLY = None

    accounts = parse_accounts(os.environ.get("ZCODE_INTL_TOKENS", ""))
    if not accounts:
        log("❌ 未配置 ZCODE_INTL_TOKENS（多条用换行或 & 分隔；每条: jwt 或 jwt|device_mid|captcha）")
        return

    log("╔════════════════════════════════════╗")
    log("║ 🎁 ZCode 国际版 领套餐             ║")
    log("╚════════════════════════════════════╝")
    log("👥 账号数: %d  平台: %s  版本: %s" % (len(accounts), client_platform(), app_version()))

    report = []
    for index, account in enumerate(accounts, 1):
        if ONLY and index != ONLY:
            continue
        log("👤 [%d] %s  jwt=%s  mid=%s" % (index, account["note"], mask(account["jwt"]), account["device_mid"]))
        try:
            success, message = do_claim(account)
            log("   %s %s" % ("✅" if success else "ℹ️", message))
            report.append("账号%d %s: %s %s" % (index, account["note"], "✅" if success else "ℹ️", message))
        except Exception as error:
            log("   ❌ 异常: %s" % error)
            report.append("账号%d %s: ❌ %s" % (index, account["note"], error))
        time.sleep(2)

    summary = "🎁 ZCode 国际版领套餐报告\n" + "\n".join(report) + "\n🕐 " + beijing_now().strftime("%Y-%m-%d %H:%M")
    log(summary)
    if not NO_NOTIFY and not PREVIEW_ONLY:
        notify_all("🎁 ZCode 国际版领套餐报告", summary)


if __name__ == "__main__":
    main()
