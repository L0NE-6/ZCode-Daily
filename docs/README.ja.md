# 🎁 ZCode Daily

ZCode 中国版または国際版で現在取得できる期間限定プランを確認し、その優先度に従って取得します。地域ごとに単一ファイルの Python スクリプトがあり、結果にはプランの有効期間が含まれます。

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

完全な中国語ドキュメントは [../README.md](../README.md) を参照してください。

## 主な機能

- 利用可能なプランを読み、最も高い `priority` を選択します。同じ優先度では先に返されたものを保持します。
- 中国版 `bigmodel` と国際版 `z.ai` は別アカウント体系で、JWT を相互利用できません。
- CLI OAuth ポーリングでブラウザ認証を行います。
- 既定で取得前に `app_launch` と `app_daily_active` を送信し、失敗しても取得処理は継続します。
- `1003` は今期取得済み、`1005` はサーバー側の再試行可能時期として扱います。
- ログとプラン時刻はホストのタイムゾーンに関係なく UTC+8 で表示します。

## Qinglong 最小構成

```bash
python3 -m pip install -r requirements.txt
```

`zcode_cn_daily.py` または `zcode_intl_daily.py` をアップロードし、対応するトークン変数を設定してタスクを作成します。

```text
25 8 * * * task zcode_cn_daily.py
25 8 * * * task zcode_intl_daily.py
```

アカウント認証:

```bash
python zcode_login.py
python zcode_login.py --region intl
python zcode_login.py --region intl --note main
```

## GitHub Actions

**Settings → Secrets and variables → Actions** で次を作成します。

```text
ZCODE_CN_TOKENS
ZCODE_INTL_TOKENS
PUSHPLUS_TOKEN          # 任意
BARK_URL                # 任意
WECOM_WEBHOOK           # 任意
DINGTALK_WEBHOOK        # 任意
DINGTALK_SECRET         # 任意
```

**Actions → ZCode Daily → Run workflow** から手動実行します。既定では手動のみです。スケジュールを使う場合は `.github/workflows/daily.yml` の `schedule:` を有効にしてください。cron は UTC です。

リポジトリの workflow はアカウントと通知の Secrets のみをマッピングします。`ZCODE_PLAN_ID`、`ZCODE_APP_VERSION`、`ZCODE_CAPTCHA_PARAM`、`ZCODE_ACTIVATION` は Qinglong またはローカル環境で設定できます。Actions で使うには workflow への追加が必要です。

## 主要な環境変数

| 変数 | 用途 |
| :--- | :--- |
| `ZCODE_CN_TOKENS` | 中国版: `jwt\|device_mid`、`note\|jwt\|device_mid`、`note\|jwt\|device_mid\|captcha` |
| `ZCODE_INTL_TOKENS` | 国際版。同じフィールド形式 |
| `ZCODE_PLAN_ID` | 任意。指定プランを強制選択 |
| `ZCODE_APP_VERSION` | クライアント版の上書き。既定値 `3.16.2` |
| `ZCODE_CAPTCHA_PARAM` | 共通の `X-Aliyun-Captcha-Verify-Param` |
| `ZCODE_ACTIVATION` | 既定値 `1`。`0` で起動イベント送信を無効化 |

複数アカウントは改行または `&` で区切ります。メモ欄に `|` を含めないでください。

## 成功判定とプライバシー

HTTP 200、`code=0`、有効期間を含むプランオブジェクトの返却がそろった場合に取得成功です。`1003` は冪等な「今期取得済み」として扱います。CAPTCHA は自動解決しません。`3007` の場合はブラウザの claim リクエストから `X-Aliyun-Captcha-Verify-Param` を一度取得してください。

`zcode_cn_devices.json` と `zcode_intl_devices.json` には固定デバイス識別子が入り、Git 対象外です。JWT、ユーザー ID、CAPTCHA パラメータ、デバイス状態ファイルを Issue や Pull Request に公開しないでください。

## 利用範囲と再配布について

本プロジェクトの公式版は無料です。リポジトリ、スクリプト、デプロイ手順、Release ダウンロードを含みます。

作者の明示的な書面許可なく、本プロジェクトを有料リソース、内部版、限定版、会員特典、有料講座、有料デプロイ、更新販売として再パッケージしないでください。無関係なアカウント、グループ、チャンネルへ転載して集客や誘導を行うこと、作者・著作権表示を削除して自作と主張すること、作者名・アバター・QR コード・プロジェクト名を使って公式承認を装うことも禁止します。

違反時は削除要請の対象となる場合があります。作者は更新の停止、リポジトリのアーカイブまたは削除を行うことがあります。完全な規則は [NOTICE.md](../NOTICE.md) を参照してください。

## リンク

- [Releases](https://github.com/L0NE-6/ZCode-Daily/releases)
- [Issues](https://github.com/L0NE-6/ZCode-Daily/issues)
- [ソースと完全な中国語ガイド](../README.md)
