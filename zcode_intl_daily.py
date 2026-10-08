#!/usr/bin/env python3
"""
🎁 ZCode 国际版 领套餐 - 青龙脚本
------------------------------------------------------------

📌 功能
   ZCode 限时套餐领取（不是传统签到）：
   1. GET  {zcode}/api/v1/zcode-plan/billing/preview?app_version=&platform=
   2. 按 priority 选可领套餐（同优先取最先出现的）
   3. POST {zcode}/api/v1/zcode-plan/billing/claim  body {"plan_id": "..."}

ℹ️ 区域：本脚本用于**国际版**账号（z.ai 侧签发的 JWT）；
   国内版账号请用 zcode_cn_daily.py，两边 JWT 不通用。

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
   ZCODE_PLAN_ID       【可选】强制领取指定 plan_id
   ZCODE_APP_VERSION   【可选】客户端版本，默认 3.14.0
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

import requests

import urllib3
urllib3.disable_warnings()

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ORIGIN = "https://zcode.z.ai"
PREVIEW_PATH = "/api/v1/zcode-plan/billing/preview"
CLAIM_PATH = "/api/v1/zcode-plan/billing/claim"
DEFAULT_APP_VERSION = "3.14.0"
DEVICE_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zcode_intl_devices.json")

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


def log(msg):
    print("%s %s" % (time.strftime("[%H:%M:%S]"), msg), flush=True)


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


def parse_plans(payload):
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    raw = data.get("plans")
    plans = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            plan_id = first_text(item.get("plan_id"), item.get("planId"))
            if not plan_id:
                continue
            entitlements = []
            for entry in item.get("entitlements") or []:
                if not isinstance(entry, dict):
                    continue
                show_name = first_text(entry.get("show_name"), entry.get("showName"))
                if show_name:
                    entitlements.append({
                        "name": show_name,
                        "unit": first_text(entry.get("unit_type"), entry.get("unitType")),
                        "grant": entry.get("grant_units", entry.get("grantUnits", 0)),
                        "period": first_text(entry.get("period")),
                    })
            plans.append({
                "plan_id": plan_id,
                "name": first_text(item.get("name")) or plan_id,
                "description": first_text(item.get("description")),
                "priority": int(item.get("priority") or 0),
                "starts_at": item.get("starts_at", item.get("startsAt")),
                "ends_at": item.get("ends_at", item.get("endsAt")),
                "entitlements": entitlements,
            })
    return plans


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


def format_time(seconds):
    if not seconds:
        return "立即"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(seconds)))
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


def do_claim(account):
    preview_response = preview(account["jwt"], account["device_mid"])
    if preview_response.status_code == 404:
        return False, "领取接口尚未部署（活动未上线）"
    if preview_response.status_code == 401:
        return False, "登录状态失效，重新登录一下吧该账号"
    payload = json_of(preview_response)
    if preview_response.status_code != 200 or payload.get("code") not in (0, None):
        message = first_text(payload.get("msg"), payload.get("message")) or ("HTTP %s" % preview_response.status_code)
        return False, "套餐探测失败: %s" % message

    plans = parse_plans(payload)
    if not plans:
        return False, "现在没有可领取的套餐"
    plan = pick_plan(plans)
    if plan is None:
        return False, "指定的 ZCODE_PLAN_ID 不在可领列表里"

    log("   🎯 目标套餐: %s" % describe_plan(plan))
    if PREVIEW_ONLY:
        return False, "仅预览（--preview），未发起领取"

    response = claim(account["jwt"], plan["plan_id"], account["device_mid"], account["captcha"])
    body = json_of(response)
    code = body.get("code")
    if response.status_code == 200 and code == 0 and isinstance(body.get("data"), dict) \
            and isinstance(body["data"].get("plan"), dict):
        result = body["data"]["plan"]
        starts = result.get("starts_at", result.get("startsAt"))
        ends = result.get("ends_at", result.get("endsAt"))
        return True, "领取成功: %s（%s ~ %s）" % (plan["name"], format_time(starts), format_time(ends))

    label = FAILURE_LABELS.get(code)
    if label is None:
        label = first_text(body.get("msg"), body.get("message")) or ("HTTP %s" % response.status_code)
    if code == 3007 and not account["captcha"]:
        label += "；从浏览器抓一次 claim 请求，把该头填到账号行第 4 段或 ZCODE_CAPTCHA_PARAM"
    return False, "领取未成功: %s（code=%s）" % (label, code)


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
        accounts.append({"note": note, "jwt": jwt, "device_mid": mid, "captcha": captcha})
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

    summary = "🎁 ZCode 国际版领套餐报告\n" + "\n".join(report) + "\n🕐 " + time.strftime("%Y-%m-%d %H:%M")
    log(summary)
    if not NO_NOTIFY and not PREVIEW_ONLY:
        notify_all("🎁 ZCode 国际版领套餐报告", summary)


if __name__ == "__main__":
    main()
