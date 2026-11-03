<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🎁 ZCode Daily

**读取 ZCode 国内版与国际版可领套餐，按优先级领取并回显有效期的单文件脚本。**

[简体中文](README.md) · [English](docs/README.en.md) · [繁體中文](docs/README.zh-Hant.md) · [日本語](docs/README.ja.md) · [한국어](docs/README.ko.md) · [Português (BR)](docs/README.pt-BR.md)

<p>
  <img src="https://img.shields.io/github/v/release/L0NE-6/ZCode-Daily?style=for-the-badge&label=Release&color=2ea44f&logo=github" alt="Release" />
  <img src="https://img.shields.io/github/stars/L0NE-6/ZCode-Daily?style=for-the-badge&label=Stars&color=FFC75F&logo=github" alt="Stars" />
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/%E9%9D%92%E9%BE%99-%E5%8D%95%E6%96%87%E4%BB%B6-4EAA25?style=for-the-badge" alt="Qinglong" />
  <img src="https://img.shields.io/badge/GitHub%20Actions-Supported-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions" />
  <img src="https://img.shields.io/badge/License-MIT-F472B6?style=for-the-badge" alt="MIT License" />
  <a href="https://github.com/L0NE-6/ZCode-Daily/releases"><img src="https://img.shields.io/badge/%E2%AC%87%20Download-Releases-2ea44f?style=for-the-badge&logo=github" alt="Download Releases" /></a>
</p>

[✨ 30 秒速览](#quick-overview) · [🎯 领取逻辑](#claim-flow) · [🚀 青龙部署](#quick-boot) · [☁️ Actions](#actions) · [🔐 授权登录](#credentials) · [🔧 环境变量](#environment) · [✅ 成功判据](#result) · [🚫 使用边界](#usage-policy) · [✦ 星轨](#star-trail)

</div>

---

<a id="quick-overview"></a>

<a id="usage-policy"></a>
## 🚫 使用边界与转载声明

> [!IMPORTANT]
> **官方版本永久免费。** 未经作者书面许可，禁止付费包装、搬运引流、冒充作者，或使用作者身份与二维码制造官方授权假象。违规内容可能被要求下架；作者可暂停更新、归档或删除仓库及相关 Release。

本项目仓库、脚本、部署说明和 Release 下载始终免费公开。未经作者明确书面许可，禁止将本项目包装为付费资源、内部版、独家版、会员权益、收费课程、付费部署或包更新服务；禁止搬运到其他账号、群组、频道、网盘、电商或付费平台进行涨粉、截流、倒卖和引流；禁止删除作者与版权信息后冒充原创；禁止使用作者昵称、头像、二维码和项目名称制造官方授权假象。

> 如需商业合作、品牌授权、联合分发或使用作者名义提供付费服务，请先取得作者明确书面授权。完整规则、收款码防诈骗说明和违规处理方式见 **[NOTICE.md](NOTICE.md)**。

> 官方仓库和 Release 始终免费。第三方以“下载费 / 激活费 / 内部版 / 代部署 / 会员门槛”等名义收费，均与作者无关，请停止付款并保留证据。

> 对上述违规行为，作者有权要求立即停止传播、删除内容并下架相关商品或页面；并可视情况暂停更新、归档或删除本仓库及相关 Release、向平台投诉或采取进一步必要措施。

<a id="support"></a>

---

## ✨ 30 秒速览

| 维度 | 说明 |
| :--- | :--- |
| **用途** | 预览并领取 ZCode 国内版或国际版当前可领取的限时套餐。 |
| **输入** | `ZCODE_CN_TOKENS` / `ZCODE_INTL_TOKENS`；按需配置套餐 ID、客户端版本、验证码与激活上报。 |
| **输出** | 目标套餐、领取结果、套餐有效期和服务端名额恢复时间。 |
| **部署** | 青龙面板、GitHub Actions，或本地 Python 运行。 |
| **依赖** | Python 3.8+，仅需 `requests`。 |
| **成功判据** | HTTP 200 且业务 `code=0`，回执含套餐对象与有效期；`1003` 表示本期已领取，按成功状态处理。 |

<a id="signals"></a>

## 🎯 核心能力

- 🎁 **按优先级选套餐**：读取可领列表，使用 `priority` 选择最高优先级套餐，同优先级保留先出现者。
- 🌍 **国内 / 国际分流**：两个脚本分别使用 bigmodel 与 z.ai 账号体系，Token 不通用。
- 🔐 **网页授权登录**：命令行 OAuth 轮询，无需在脚本里输入验证码登录账号。
- 🧭 **默认客户端版本更新**：当前默认 `app_version=3.16.2`，低于活动门槛时不会继续使用旧版本空跑。
- 📣 **激活事件补报**：领取前上报 `app_launch` / `app_daily_active`，失败只记日志，不阻断领取。
- 🧾 **状态语义完整**：`1003` 已领取按成功，`1005` 显示服务端结束时间，`3001` / `3007` 分别提示设备与验证码问题。
- 📒 **领取台账去重**：按账号与活动期合并服务端预览和已确认领取事实，保留 90 天；身份变化时隔离旧记录。
- 🕐 **固定北京时间**：日志与套餐时间统一按 UTC+8 展示，不跟随宿主机时区。

<a id="claim-flow"></a>

## 🔁 领取逻辑

```text
GET  /api/v1/zcode-plan/billing/preview?app_version=...&platform=...
POST /api/v1/event/report          # app_launch / app_daily_active
POST /api/v1/zcode-plan/billing/claim
{"plan_id": "..."}
```

1. 按账号 JWT 载荷提取用户标识，补报两条激活事件。
2. 读取可领套餐并合并本地领取台账；指定 `ZCODE_PLAN_ID` 时优先匹配该套餐。
3. 已确认同一活动期的记录会跳过重复请求；存在新套餐时继续处理。
4. 未指定时选择可领取且未在台账命中的最高 `priority` 套餐。
5. 发起领取并解析套餐对象、开始时间与结束时间。
6. `--preview` 只预览目标套餐，不发送领取请求。

> 验证码参数不会自动求解。若上游返回 `3007`，请从浏览器抓取一次 `claim` 请求中的 `X-Aliyun-Captcha-Verify-Param`，填入账号行或 `ZCODE_CAPTCHA_PARAM`。
>
> 台账只记录服务端已经确认的领取结果。文件缺失、损坏或账号身份变化时，不会把旧记录当作新的领取成功。

## 📦 文件说明

| 文件 | 用途 |
| :--- | :--- |
| `zcode_login.py` | 国内版 / 国际版网页授权登录 |
| `zcode_cn_daily.py` | 国内版套餐预览与领取 |
| `zcode_intl_daily.py` | 国际版套餐预览与领取 |
| `requirements.txt` | Python 依赖清单 |

<a id="quick-boot"></a>

## 🚀 青龙部署

1. 安装依赖：`python3 -m pip install -r requirements.txt`。
2. 上传需要的签到脚本到青龙「脚本管理」。
3. 添加国内版和/或国际版账号变量。
4. 用青龙运行器建立定时任务。

```text
# 每天北京时间 08:25，可分别启用
25 8 * * * task zcode_cn_daily.py
25 8 * * * task zcode_intl_daily.py
```

<a id="actions"></a>

## ☁️ GitHub Actions

1. Fork 或导入仓库到自己的账号。
2. 在 **Settings → Secrets and variables → Actions** 新建 Secrets。
3. 从 **Actions → ZCode Daily → Run workflow** 手动验证。
4. 默认仅手动触发；需要定时时，在 `.github/workflows/daily.yml` 取消 `schedule:` 两行注释。cron 使用 UTC。

| Secret | 必填 | 说明 |
| :--- | :---: | :--- |
| `ZCODE_CN_TOKENS` | 可选 | 只跑国际版时可留空 |
| `ZCODE_INTL_TOKENS` | 可选 | 只跑国内版时可留空 |
| `PUSHPLUS_TOKEN` / `BARK_URL` | 可选 | PushPlus / Bark |
| `WECOM_WEBHOOK` / `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` | 可选 | 企业微信 / 钉钉 |

> 仓库现有 Actions 工作流直接映射账号与推送 Secrets。`ZCODE_PLAN_ID`、`ZCODE_APP_VERSION`、`ZCODE_CAPTCHA_PARAM`、`ZCODE_ACTIVATION` 可在青龙或本地环境变量中设置；如要在 Actions 使用，需要同步把变量映射进 workflow。
>
> GitHub Actions runner 没有持久化目录时，领取台账只在当前 job 的 checkout 内有效，不保证跨 job 保留；依赖跨运行去重时，应使用带持久化脚本目录的青龙部署或自行提供持久化存储。

<a id="credentials"></a>

## 🔐 获取 Token

```bash
python zcode_login.py
python zcode_login.py --region intl
python zcode_login.py --region intl --note 国际主号
python zcode_login.py --no-verify
```

浏览器完成授权后，工具轮询 CLI OAuth 状态并输出一行 `备注|jwt|device_mid`，分别填入 `ZCODE_CN_TOKENS` 或 `ZCODE_INTL_TOKENS`。

| 参数 | 作用 |
| :--- | :--- |
| `--region cn` | 国内版 bigmodel，默认值 |
| `--region intl` | 国际版 z.ai |
| `--note 主号` | 添加账号备注 |
| `--no-verify` | 跳过登录后的套餐列表校验 |

`device_mid` 用于风控关联同一设备。登录工具会生成固定 UUID；若账号行未提供，签到脚本也会为 JWT 生成并保存固定值。

<a id="environment"></a>

## 🔧 环境变量与参数

多账号使用换行或 `&` 分隔。单条账号使用 `|` 分隔字段，备注中不要包含 `|`。

| 环境变量 | 格式 | 说明 |
| :--- | :--- | :--- |
| `ZCODE_CN_TOKENS` | `jwt\|device_mid` / `备注\|jwt\|device_mid` / `备注\|jwt\|device_mid\|captcha` | 国内版账号 |
| `ZCODE_INTL_TOKENS` | 同上 | 国际版账号 |
| `ZCODE_PLAN_ID` | 套餐 ID | 强制领取指定套餐 |
| `ZCODE_APP_VERSION` | 版本号 | 覆盖默认客户端版本，默认 `3.16.2` |
| `ZCODE_CAPTCHA_PARAM` | 验证码参数 | 为未单独填写验证码的账号提供全局值 |
| `ZCODE_ACTIVATION` | `1` / `0` | 领取前补报激活事件，默认 `1` |
| `PUSHPLUS_TOKEN` / `BARK_URL` | Token / URL | 可选推送 |
| `WECOM_WEBHOOK` / `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` | Webhook / 加签密钥 | 可选推送 |
| `QL_URL` / `QL_TOKEN` | 面板地址 / 旧版面板 Token | 可选青龙通知 |

| 参数 | 作用 |
| :--- | :--- |
| `--preview` | 只读预览目标套餐，不领取 |
| `--only 2` | 只跑第 2 个账号 |
| `--no-notify` | 关闭本轮推送 |

<a id="result"></a>

## ✅ 成功判据与状态码

- 领取成功：HTTP 200、`code=0`，且 `data.plan` 含套餐对象；报告套餐名称与 UTC+8 有效期。
- `1003`：该账号已领取本期套餐，按成功幂等状态处理。
- `1005`：本轮名额或次数已用完；若服务端返回套餐结束时间，会给出下一轮重试不早于该时间。
- `3001`：重点检查 `device_mid`、客户端版本与验证码是否过期。
- `3007`：验证码未通过；补充 `X-Aliyun-Captcha-Verify-Param`。
- 台账命中表示本机记录过已确认领取，可能中性显示“今日已领取”或“当前无新套餐”，不等同于本轮重新领取成功。
- 无套餐且台账无命中时，可能是活动未开始、已结束或账号无资格，脚本按服务端现状报告，不推测成功。

```text
[08:25:01] 👤 [1] 主号  jwt=eyJhbGci****abcd  mid=1111...
[08:25:02]    🎯 目标套餐: Start Plan：额度 1000000 tokens（每日）
[08:25:03]    ✅ 领取成功: Start Plan（2026-10-09 10:00 ~ 2026-10-10 09:59）
```

<a id="data-privacy"></a>

## 🗂️ 数据文件与隐私

| 文件 | 内容 | 是否提交 |
| :--- | :--- | :---: |
| `zcode_cn_devices.json` | 国内版账号的固定 `device_mid` | 否，已忽略 |
| `zcode_intl_devices.json` | 国际版账号的固定 `device_mid` | 否，已忽略 |
| `zcode_cn_claim_ledger.json` | 国内版账号领取台账：账号稳定哈希、region、plan_id、claimed_at、expiry | 否，已忽略 |
| `zcode_intl_claim_ledger.json` | 国际版账号领取台账：账号稳定哈希、region、plan_id、claimed_at、expiry | 否，已忽略 |

- 仓库不内置账号、手机号、JWT 或设备标识。
- 凭据由环境变量或 GitHub Secrets 注入。
- 设备文件按 JWT 的哈希索引保存；JWT 本身不应出现在 Issue。
- 领取台账只保存账号稳定哈希、region、plan_id、claimed_at、expiry，不保存 JWT、user_id 或验证码。
- 国内版与国际版使用不同台账文件，不共享领取状态。
- 当前用户标识从 JWT 载荷读取；读取失败时跳过激活补报，不伪造身份。

## ❓ 常见问题

**提示 `3007` 验证码怎么办？**
从浏览器抓取一次 `claim` 请求中的 `X-Aliyun-Captcha-Verify-Param`，追加到账号行作为第四个字段，或设置 `ZCODE_CAPTCHA_PARAM`。

**国内版 JWT 能用在国际版吗？**
不能。bigmodel 与 z.ai 是不同账号体系，请分别登录并填写对应变量。

**为什么套餐列表为空？**
活动可能未开始或已结束、账号无资格，或客户端版本低于门槛。当前默认版本为 `3.16.2`，必要时用 `ZCODE_APP_VERSION` 覆盖。v1.0.6 起会合并本地领取台账：服务端预览为空但台账有当日已确认记录时，会中性提示“今日已领取”；没有台账命中时仍按服务端为空报告。

**`1003` 是失败吗？**
不是。它表示本期已经领取过，脚本按成功状态报告。

<a id="release"></a>

## 📦 版本与发布

当前 CHANGELOG 记录最新版本为 `v1.0.6`（2026-11-04）。每个版本单独发布 Release，附完整包、脚本单文件与 `SHA256SUMS.txt`。下载页：[Releases](https://github.com/L0NE-6/ZCode-Daily/releases)。

## ⚠️ 说明

本项目用于学习与个人自动化。请遵守对应平台的服务条款，并自行承担运行风险。

## ☕ 支持与反馈

脚本完全免费，支持不影响任何功能。

- [提交 Issue](https://github.com/L0NE-6/ZCode-Daily/issues)：请附运行日志、复现步骤与脱敏后的状态码。
- [发起 Pull Request](https://github.com/L0NE-6/ZCode-Daily/pulls)：欢迎修复、测试与文档贡献。
- [点一个 Star](https://github.com/L0NE-6/ZCode-Daily)：让更多使用者找到这个项目。

<p align="center">
  <img src="assets/donate-wechat.png" width="240" alt="微信赞赏码" />
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/donate-alipay.jpg" width="240" alt="支付宝收款码" />
</p>
<p align="center"><sub>微信支付（左） · 支付宝（右）</sub></p>

> ⚠️ 收款码仅用于向作者自愿赞赏。任何第三方以代下载、代部署、内部资源或会员群为由收费，均与作者无关，请停止付款并保留证据。

<a id="star-trail"></a>

## ✦ 星轨 Star Trail

> 活动会结束，名额会变化；每一次 Star 都在为这条自动化轨迹保留一个发光的节点。

<a href="https://star-history.com/#L0NE-6/ZCode-Daily&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=l0ne-6/zcode-daily&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=l0ne-6/zcode-daily&type=Date&theme=light" />
    <img alt="ZCode Daily Star Trail" src="https://api.star-history.com/svg?repos=l0ne-6/zcode-daily&type=Date&theme=light" />
  </picture>
</a>

---

<div align="center">
  <sub>L0NE-6 · DAILY SIGNAL</sub>
  <br />
  <a href="https://github.com/L0NE-6/ZCode-Daily/releases">Releases</a>
  ·
  <a href="https://github.com/L0NE-6/ZCode-Daily/issues">Issues</a>
  ·
  <a href="https://github.com/L0NE-6/ZCode-Daily">Star</a>
</div>
