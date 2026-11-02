# 🎁 ZCode Daily

Previews and claims the currently available ZCode limited plan for the China or international service. Each region has its own single-file Python script, and the result includes the plan validity window.

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

For the complete Chinese documentation, see [../README.md](../README.md).

## Highlights

- Reads available plans and selects the highest `priority`; ties keep the first server entry.
- Separates China `bigmodel` and international `z.ai` accounts; their JWTs are not interchangeable.
- Uses CLI OAuth polling for browser authorization.
- Sends `app_launch` and `app_daily_active` before claiming by default; event failures do not block the claim.
- Treats `1003` as already claimed for the current period, and uses `1005` to show the server recovery window.
- Formats logs and plan times in UTC+8 regardless of host timezone.

## Qinglong Quick Start

```bash
python3 -m pip install -r requirements.txt
```

Upload `zcode_cn_daily.py` and/or `zcode_intl_daily.py`, configure the matching token variable, and create tasks:

```text
25 8 * * * task zcode_cn_daily.py
25 8 * * * task zcode_intl_daily.py
```

Authorize an account:

```bash
python zcode_login.py
python zcode_login.py --region intl
python zcode_login.py --region intl --note main
```

## GitHub Actions

Create these repository secrets under **Settings → Secrets and variables → Actions**:

```text
ZCODE_CN_TOKENS
ZCODE_INTL_TOKENS
PUSHPLUS_TOKEN          # optional
BARK_URL                # optional
WECOM_WEBHOOK           # optional
DINGTALK_WEBHOOK        # optional
DINGTALK_SECRET         # optional
```

Then run **Actions → ZCode Daily → Run workflow**. The workflow is manual by default. Enable the commented schedule in `.github/workflows/daily.yml` if needed; cron uses UTC.

The checked-in workflow maps account and notification secrets only. `ZCODE_PLAN_ID`, `ZCODE_APP_VERSION`, `ZCODE_CAPTCHA_PARAM`, and `ZCODE_ACTIVATION` can be set in Qinglong or a local environment; using them in Actions requires adding them to the workflow mapping.

## Key Environment Variables

| Variable | Meaning |
| :--- | :--- |
| `ZCODE_CN_TOKENS` | China accounts: `jwt\|device_mid`, `note\|jwt\|device_mid`, or `note\|jwt\|device_mid\|captcha` |
| `ZCODE_INTL_TOKENS` | International accounts in the same field layout |
| `ZCODE_PLAN_ID` | Optional forced plan ID |
| `ZCODE_APP_VERSION` | Client version override; default `3.16.2` |
| `ZCODE_CAPTCHA_PARAM` | Global `X-Aliyun-Captcha-Verify-Param` value for accounts without a per-account captcha |
| `ZCODE_ACTIVATION` | `1` by default; set `0` to skip activation event reporting |

Use newlines or `&` between accounts. Do not put `|` inside a note.

## Success and Privacy

A claim succeeds when the server returns HTTP 200, `code=0`, and a plan object with its validity window. `1003` is treated as an idempotent already-claimed result. A captcha is not solved automatically; if the server returns `3007`, capture one `X-Aliyun-Captcha-Verify-Param` value from a browser claim request.

`zcode_cn_devices.json` and `zcode_intl_devices.json` contain stable device identifiers and are ignored by Git. Never publish JWT values, user IDs, captcha parameters, or device state files in an issue or pull request.

## Project Links

- [Releases](https://github.com/L0NE-6/ZCode-Daily/releases)
- [Issues](https://github.com/L0NE-6/ZCode-Daily/issues)
- [Source and complete Chinese guide](../README.md)
