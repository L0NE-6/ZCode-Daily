# 🎁 ZCode Daily

讀取並領取 ZCode 國內版或國際版目前可用的限時套餐。兩個地區各有一個單檔 Python 腳本，領取結果會顯示套餐有效期。

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

完整中文文件請見 [../README.md](../README.md)。

## 核心能力

- 讀取可領套餐並依 `priority` 選擇最高優先級；同級保留最先出現者。
- 分離國內版 `bigmodel` 與國際版 `z.ai` 帳號，JWT 不通用。
- 使用 CLI OAuth 輪詢完成瀏覽器授權。
- 預設在領取前補報 `app_launch` / `app_daily_active`；上報失敗不阻斷領取。
- `1003` 視為本期已領取，`1005` 顯示服務端名額恢復時間。
- 日誌與套餐時間固定使用 UTC+8。

## 青龍最短配置

```bash
python3 -m pip install -r requirements.txt
```

上傳 `zcode_cn_daily.py` 或 `zcode_intl_daily.py`、設定帳號變數、建立任務：

```text
25 8 * * * task zcode_cn_daily.py
25 8 * * * task zcode_intl_daily.py
```

取得授權：

```bash
python zcode_login.py
python zcode_login.py --region intl
python zcode_login.py --region intl --note 國際主號
```

## GitHub Actions

在 **Settings → Secrets and variables → Actions** 建立：

```text
ZCODE_CN_TOKENS
ZCODE_INTL_TOKENS
PUSHPLUS_TOKEN          # 選填
BARK_URL                # 選填
WECOM_WEBHOOK           # 選填
DINGTALK_WEBHOOK        # 選填
DINGTALK_SECRET         # 選填
```

從 **Actions → ZCode Daily → Run workflow** 手動執行。預設僅手動觸發；需要排程時取消 `.github/workflows/daily.yml` 中 `schedule:` 註解。cron 使用 UTC。

現有工作流只映射帳號與通知 Secrets。`ZCODE_PLAN_ID`、`ZCODE_APP_VERSION`、`ZCODE_CAPTCHA_PARAM`、`ZCODE_ACTIVATION` 可在青龍或本機環境設定；若要在 Actions 使用，需同步加入 workflow 映射。

## 關鍵環境變數

| 變數 | 用途 |
| :--- | :--- |
| `ZCODE_CN_TOKENS` | 國內版：`jwt\|device_mid`、`備註\|jwt\|device_mid`、`備註\|jwt\|device_mid\|captcha` |
| `ZCODE_INTL_TOKENS` | 國際版，欄位格式相同 |
| `ZCODE_PLAN_ID` | 選填，強制領取指定套餐 |
| `ZCODE_APP_VERSION` | 覆寫客戶端版本，預設 `3.16.2` |
| `ZCODE_CAPTCHA_PARAM` | 全局 `X-Aliyun-Captcha-Verify-Param` |
| `ZCODE_ACTIVATION` | 預設 `1`；設 `0` 可關閉啟動事件補報 |

多帳號用換行或 `&` 分隔；備註不要包含 `|`。

## 成功判據與隱私

HTTP 200、`code=0` 且回執含套餐物件與有效期時，才算領取成功。`1003` 按冪等的本期已領取處理。驗證碼不會自動求解；若返回 `3007`，請從瀏覽器 claim 請求抓取一次 `X-Aliyun-Captcha-Verify-Param`。

`zcode_cn_devices.json` 與 `zcode_intl_devices.json` 含固定設備識別並被 Git 忽略。請勿在 Issue 或 Pull Request 公開 JWT、用戶 ID、驗證碼參數或設備狀態檔。

## 專案連結

- [Releases](https://github.com/L0NE-6/ZCode-Daily/releases)
- [Issues](https://github.com/L0NE-6/ZCode-Daily/issues)
- [原始碼與完整中文文件](../README.md)
