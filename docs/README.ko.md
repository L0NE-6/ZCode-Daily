# 🎁 ZCode Daily

ZCode 중국판 또는 국제판에서 현재 받을 수 있는 기간 한정 플랜을 조회하고 우선순위에 따라 수령합니다. 지역별 단일 Python 스크립트를 사용하며 결과에 플랜 유효 기간이 포함됩니다.

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

전체 중국어 문서는 [../README.md](../README.md)에서 확인하세요.

## 주요 기능

- 사용 가능한 플랜을 읽고 가장 높은 `priority`를 선택하며, 동일 우선순위에서는 먼저 나온 항목을 유지합니다.
- 중국판 `bigmodel`과 국제판 `z.ai` 계정을 분리하며 JWT는 서로 호환되지 않습니다.
- CLI OAuth 폴링으로 브라우저 인증을 수행합니다.
- 기본적으로 수령 전 `app_launch`, `app_daily_active`를 보내며 이벤트 실패는 수령을 막지 않습니다.
- `1003`은 이번 기간 이미 수령, `1005`는 서버가 알려준 재시도 가능 시점으로 처리합니다.
- 로그와 플랜 시간은 호스트 시간대와 무관하게 UTC+8로 표시합니다.

## Qinglong 최소 설정

```bash
python3 -m pip install -r requirements.txt
```

`zcode_cn_daily.py` 또는 `zcode_intl_daily.py`를 업로드하고 해당 토큰 변수를 설정한 뒤 작업을 만듭니다.

```text
25 8 * * * task zcode_cn_daily.py
25 8 * * * task zcode_intl_daily.py
```

계정 인증:

```bash
python zcode_login.py
python zcode_login.py --region intl
python zcode_login.py --region intl --note main
```

## GitHub Actions

**Settings → Secrets and variables → Actions**에서 다음 Secrets를 만듭니다.

```text
ZCODE_CN_TOKENS
ZCODE_INTL_TOKENS
PUSHPLUS_TOKEN          # 선택
BARK_URL                # 선택
WECOM_WEBHOOK           # 선택
DINGTALK_WEBHOOK        # 선택
DINGTALK_SECRET         # 선택
```

**Actions → ZCode Daily → Run workflow**에서 수동 실행합니다. 기본값은 수동 실행이며, 예약 실행이 필요하면 `.github/workflows/daily.yml`의 `schedule:` 주석을 해제하세요. cron은 UTC 기준입니다.

저장소 workflow는 계정과 알림 Secrets만 매핑합니다. `ZCODE_PLAN_ID`, `ZCODE_APP_VERSION`, `ZCODE_CAPTCHA_PARAM`, `ZCODE_ACTIVATION`은 Qinglong 또는 로컬 환경에서 설정할 수 있으며, Actions에서 사용하려면 workflow에도 추가해야 합니다.

## 핵심 환경 변수

| 변수 | 용도 |
| :--- | :--- |
| `ZCODE_CN_TOKENS` | 중국판: `jwt\|device_mid`, `note\|jwt\|device_mid`, `note\|jwt\|device_mid\|captcha` |
| `ZCODE_INTL_TOKENS` | 국제판, 같은 필드 형식 |
| `ZCODE_PLAN_ID` | 선택. 지정 플랜 강제 수령 |
| `ZCODE_APP_VERSION` | 클라이언트 버전 재정의, 기본 `3.16.2` |
| `ZCODE_CAPTCHA_PARAM` | 공통 `X-Aliyun-Captcha-Verify-Param` |
| `ZCODE_ACTIVATION` | 기본 `1`; `0`이면 활성화 이벤트 전송 생략 |

계정은 줄바꿈 또는 `&`로 구분합니다. 메모에는 `|`를 넣지 마세요.

## 성공 기준과 개인정보

HTTP 200, `code=0`, 유효 기간이 있는 플랜 객체가 모두 확인되어야 수령 성공입니다. `1003`은 이번 기간 이미 수령한 멱등 결과로 처리합니다. CAPTCHA는 자동으로 풀지 않으며 `3007`이면 브라우저 claim 요청에서 `X-Aliyun-Captcha-Verify-Param` 값을 한 번 캡처해야 합니다.

`zcode_cn_devices.json`과 `zcode_intl_devices.json`에는 고정 기기 식별자가 저장되며 Git에서 제외됩니다. JWT, 사용자 ID, CAPTCHA 값, 기기 상태 파일을 Issue나 Pull Request에 공개하지 마세요.

## 링크

- [Releases](https://github.com/L0NE-6/ZCode-Daily/releases)
- [Issues](https://github.com/L0NE-6/ZCode-Daily/issues)
- [소스와 전체 중국어 문서](../README.md)
