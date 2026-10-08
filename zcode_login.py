#!/usr/bin/env python3
"""
🎁 ZCode 网页授权登录工具
------------------------------------------------------------
发起一轮 CLI 授权 → 浏览器登录 → 自动轮询 → 拿到套餐 JWT

用法:
  python zcode_login.py                  # 国内版
  python zcode_login.py --region intl    # 国际版（z.ai）
  python zcode_login.py --note 主号      # 指定备注名
  python zcode_login.py --no-verify      # 跳过登录后校验

输出（直接作为 ZCODE_CN_TOKENS / ZCODE_INTL_TOKENS 的一行）:
  备注|jwt|device_mid

说明:
  · 授权页在浏览器打开，需要能访问 zcode.z.ai；
  · device_mid 是一串固定 UUID，用于风控关联同一设备，脚本会一并输出；
  运行环境：Python 3 + requests。
"""
import os
import platform as host_platform
import sys
import time
import uuid
import webbrowser

import requests

import urllib3
urllib3.disable_warnings()

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ORIGIN = "https://zcode.z.ai"
INIT_PATH = "/api/v1/oauth/cli/init"
POLL_PATH = "/api/v1/oauth/cli/poll"
PREVIEW_PATH = "/api/v1/zcode-plan/billing/preview"
APP_VERSION = os.environ.get("ZCODE_APP_VERSION", "").strip() or "3.14.0"
POLL_TIMEOUT = 300
POLL_FALLBACK = 2

REGIONS = {
    "cn": {"provider": "bigmodel", "label": "国内版", "env": "ZCODE_CN_TOKENS"},
    "intl": {"provider": "zai", "label": "国际版", "env": "ZCODE_INTL_TOKENS"},
}


def log(msg):
    print("%s %s" % (time.strftime("[%H:%M:%S]"), msg), flush=True)


def encode_component(value):
    safe = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    out = []
    for byte in value.encode("utf-8"):
        out.append(chr(byte) if byte in safe else "%%%02X" % byte)
    return "".join(out)


def request(method, url, headers=None, body=None, timeout=20, retries=2):
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
    return ""


def apply_interstitial(region_key, authorize_url):
    param = "redirect" if region_key == "cn" else "redirect_uri"
    target = encode_component(
        "%s/app/oauth/login?redirect=zcode%%3A%%2F%%2Foauth%%2Fcallback&app_version=%s" % (ORIGIN, APP_VERSION))
    head, _, fragment = authorize_url.partition("#")
    path, question, query = head.partition("?")
    if not question:
        return authorize_url
    prefix = param + "="
    segments = []
    replaced = False
    for segment in [item for item in query.split("&") if item]:
        if segment.startswith(prefix):
            if not replaced:
                segments.append(prefix + target)
                replaced = True
            continue
        segments.append(segment)
    rebuilt = path + "?" + "&".join(segments)
    return rebuilt + ("#" + fragment if fragment else "")


def platform_tag():
    system = host_platform.system().lower()
    machine = host_platform.machine().lower()
    if system == "windows":
        return "win32-x64"
    if system == "darwin":
        return "darwin-arm64" if "arm" in machine else "darwin-x64"
    return "linux-arm64" if ("arm" in machine or "aarch64" in machine) else "linux-x64"


def start_login(region_key):
    poll_token = os.urandom(32).hex()
    response = request("POST", ORIGIN + INIT_PATH,
                       headers={"authorization": "Bearer %s" % poll_token, "content-type": "application/json"},
                       body={"provider": REGIONS[region_key]["provider"]})
    payload = json_of(response)
    if payload.get("code") not in (0, None):
        raise RuntimeError("发起登录失败：%s" % (first_text(payload.get("msg"), payload.get("message")) or payload.get("code")))
    data = payload.get("data") or {}
    flow_id = first_text(data.get("flow_id"))
    authorize_url = first_text(data.get("authorize_url"))
    if not flow_id or not authorize_url:
        raise RuntimeError("发起登录响应缺少 flow_id / authorize_url")
    interval = data.get("poll_interval_sec")
    try:
        interval = max(1, int(interval))
    except Exception:
        interval = POLL_FALLBACK
    return {
        "poll_token": poll_token,
        "flow_id": flow_id,
        "auth_url": apply_interstitial(region_key, authorize_url),
        "interval": interval,
        "expires_at": data.get("expires_at") or 0,
    }


def poll_once(login_state):
    url = "%s%s/%s" % (ORIGIN, POLL_PATH, login_state["flow_id"])
    try:
        response = request("GET", url, headers={"authorization": "Bearer %s" % login_state["poll_token"]}, retries=1)
    except Exception:
        return None
    if response.status_code >= 500 or response.status_code in (408, 429):
        return None
    payload = json_of(response)
    if payload.get("code") not in (0, None):
        raise RuntimeError("轮询被拒：%s" % (first_text(payload.get("msg"), payload.get("message")) or payload.get("code")))
    if response.status_code >= 400:
        raise RuntimeError("轮询被拒（HTTP %s）" % response.status_code)
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    status = data.get("status") or ""
    if status == "failed":
        raise RuntimeError("授权被拒绝或已失效，请重新运行")
    if status != "ready":
        return None
    return data


def parse_ready(data, region_key):
    provider = REGIONS[region_key]["provider"]
    access_token = first_text((data.get(provider) or {}).get("access_token")) \
        if isinstance(data.get(provider), dict) else ""
    jwt = first_text(data.get("token"))
    user_id = first_text((data.get("user") or {}).get("user_id")) if isinstance(data.get("user"), dict) else ""
    if not jwt:
        raise RuntimeError("授权响应缺少套餐 token")
    return {"jwt": jwt, "access_token": access_token, "user_id": user_id}


def verify(region_key, jwt, device_mid):
    log("🔎 校验 token ...")
    url = "%s%s?app_version=%s&platform=%s" % (ORIGIN, PREVIEW_PATH, APP_VERSION, platform_tag())
    headers = {"Authorization": "Bearer %s" % jwt, "X-Device-Mid": device_mid}
    try:
        response = request("GET", url, headers=headers)
        payload = json_of(response)
        if response.status_code == 200 and payload.get("code") == 0:
            log("✅ token 可用（已读到套餐列表）")
            return True
        log("⚠️ 校验返回 HTTP %s / code=%s" % (response.status_code, payload.get("code")))
    except Exception as error:
        log("⚠️ 校验异常：%s" % error)
    return False


def main():
    args = sys.argv[1:]
    region_key = "cn"
    if "--region" in args:
        try:
            region_key = args[args.index("--region") + 1].strip().lower()
        except Exception:
            region_key = "cn"
    if region_key not in REGIONS:
        print("❌ --region 只支持 cn / intl")
        return 1
    do_verify = "--no-verify" not in args
    note = ""
    if "--note" in args:
        try:
            note = args[args.index("--note") + 1]
        except Exception:
            note = ""
    region = REGIONS[region_key]

    print("╔══════════════════════════════════════════╗")
    print("║ 🎁 ZCode 网页授权登录（%s）      ║" % region["label"])
    print("╚══════════════════════════════════════════╝")

    login_state = start_login(region_key)
    print("👉 请在浏览器打开下面的地址并完成登录：")
    print(login_state["auth_url"])
    try:
        webbrowser.open(login_state["auth_url"])
    except Exception:
        pass
    print("⏳ 等待授权（最长 %d 秒）..." % POLL_TIMEOUT)

    deadline = time.time() + POLL_TIMEOUT
    ready = None
    while time.time() < deadline:
        time.sleep(login_state["interval"])
        ready = poll_once(login_state)
        if ready:
            break
    if not ready:
        print("❌ 授权超时或未完成，请重新运行")
        return 1

    credentials = parse_ready(ready, region_key)
    log("✅ 授权成功  user_id=%s" % (credentials["user_id"] or "?"))
    device_mid = str(uuid.uuid4())
    if do_verify:
        verify(region_key, credentials["jwt"], device_mid)

    env_line = "%s|%s" % (credentials["jwt"], device_mid)
    if note:
        env_line = note + "|" + env_line
    print("\n" + "-" * 50)
    print("✅ 将下面这行追加到 %s" % region["env"])
    print("-" * 50)
    print(env_line)
    print("-" * 50)
    if credentials["access_token"]:
        print("推理 access_token（一般不用填）: %s..." % credentials["access_token"][:16])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)
    except Exception as error:
        print("❌ %s" % error)
        sys.exit(1)
