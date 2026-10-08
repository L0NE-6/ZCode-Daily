<div align="center">

# 🎁 ZCode Daily

**ZCode 国内版 / 国际版 领套餐 · 单文件青龙脚本 · 多账号**

<img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/%E9%9D%92%E9%BE%99%E9%9D%A2%E6%9D%BF-%E5%8D%95%E6%96%87%E4%BB%B6%E8%BF%90%E8%A1%8C-4EAA25?style=flat-square" />
<img src="https://img.shields.io/badge/%E5%A4%9A%E8%B4%A6%E5%8F%B7-%E6%8D%A2%E8%A1%8C%E6%88%96%20%26%20%E5%88%86%E9%9A%94-2088FF?style=flat-square" />
<img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />

</div>

---

## ✨ 这是什么

完成 ZCode 限时套餐的预览与领取：读取可领套餐 → 按优先级选一个 → 领取并回显有效期。国内版与国际版各一个签到脚本，共用同一个网页授权登录工具。

## 📦 文件说明

| 文件 | 作用 |
|---|---|
| `zcode_login.py` | 网页授权登录（国内 / 国际） |
| `zcode_cn_daily.py` | 国内版领套餐 |
| `zcode_intl_daily.py` | 国际版领套餐 |

## 🔑 先获取 Token

```bash
python zcode_login.py                 # 国内版
python zcode_login.py --region intl   # 国际版
```

浏览器完成登录后工具自动轮询，输出一行 `jwt|device_mid`，粘贴进 `ZCODE_CN_TOKENS` 或 `ZCODE_INTL_TOKENS`。

## 🧩 环境变量（支持多账号）

> 多账号用 **换行** 或 **`&`** 分隔，两种可以混用。`|` 是单条账号内部的字段分隔符，备注里不要再写 `|`。

| 环境变量 | 单条格式 |
|---|---|
| `ZCODE_CN_TOKENS / ZCODE_INTL_TOKENS` | `jwt\|device_mid` / `备注\|jwt\|device_mid`（可在最后再加一段验证码参数） |

## 🚀 青龙部署

1. 安装依赖：`pip install -r requirements.txt`
2. 把签到脚本上传到青龙（或把整个仓库放进脚本目录）。
3. 在「环境变量」里添加上面的变量，值按单条格式填写。
4. 新建定时任务，参考：

```cron
25 8 * * * python zcode_cn_daily.py
25 8 * * * python zcode_intl_daily.py
```

## ⚙️ 常用参数

- `--preview`：只读预览，不发领取请求
- `--only 2`：只跑第 2 个账号
- `--no-notify`：关闭推送

## 📢 推送（可选）

支持 `PUSHPLUS_TOKEN`、`BARK_URL`、`WECOM_WEBHOOK`、`DINGTALK_WEBHOOK`、`DINGTALK_SECRET`；青龙面板自带通知也会自动尝试。配了哪个用哪个，都没配就只打日志。

## ⚠️ 注意事项

- 领取时上游可能要求 `X-Aliyun-Captcha-Verify-Param`，按日志提示抓一次补齐即可。
- `device_mid` 会自动生成并保存在同目录 `zcode_*_devices.json`，保持固定不要更换。
- 国内版与国际版的 JWT 不通用。

## 🔒 安全

- 环境变量和运行期生成的 JSON 缓存都包含账号凭据，不要提交到公开仓库、不要外发。
- 仓库里的 `.gitignore` 已排除缓存文件；如果自己改过目录结构，请确认缓存文件没有被 `git add`。

## 📄 License

MIT © 2026 [L0NE-6](https://github.com/L0NE-6)
