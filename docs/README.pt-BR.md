# 🎁 ZCode Daily

Consulta e resgata o plano limitado disponível no ZCode chinês ou internacional. Cada região tem seu próprio script Python de arquivo único, e o resultado mostra o período de validade do plano.

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

A documentação completa em chinês está em [../README.md](../README.md).

## Recursos

- Lê os planos disponíveis e escolhe o maior `priority`; em empate, mantém o primeiro item retornado.
- Separa contas chinesas `bigmodel` e internacionais `z.ai`; os JWTs não são intercambiáveis.
- Usa polling OAuth pela CLI para a autorização no navegador.
- Envia `app_launch` e `app_daily_active` antes do resgate por padrão; falhas de evento não bloqueiam a operação.
- Trata `1003` como já resgatado no período e usa `1005` para mostrar a janela informada pelo servidor.
- Exibe logs e horários no UTC+8, independentemente do fuso do host.

## Início rápido no Qinglong

```bash
python3 -m pip install -r requirements.txt
```

Envie `zcode_cn_daily.py` e/ou `zcode_intl_daily.py`, configure a variável de token correspondente e crie as tarefas:

```text
25 8 * * * task zcode_cn_daily.py
25 8 * * * task zcode_intl_daily.py
```

Autorize uma conta:

```bash
python zcode_login.py
python zcode_login.py --region intl
python zcode_login.py --region intl --note principal
```

## GitHub Actions

Crie estes Secrets em **Settings → Secrets and variables → Actions**:

```text
ZCODE_CN_TOKENS
ZCODE_INTL_TOKENS
PUSHPLUS_TOKEN          # opcional
BARK_URL                # opcional
WECOM_WEBHOOK           # opcional
DINGTALK_WEBHOOK        # opcional
DINGTALK_SECRET         # opcional
```

Execute **Actions → ZCode Daily → Run workflow**. O workflow é manual por padrão; habilite o agendamento comentado em `.github/workflows/daily.yml` se necessário. O cron usa UTC.

O workflow do repositório mapeia apenas os Secrets de conta e notificação. `ZCODE_PLAN_ID`, `ZCODE_APP_VERSION`, `ZCODE_CAPTCHA_PARAM` e `ZCODE_ACTIVATION` podem ser definidos no Qinglong ou localmente; para usá-los no Actions, adicione-os ao mapeamento do workflow.

## Variáveis principais

| Variável | Uso |
| :--- | :--- |
| `ZCODE_CN_TOKENS` | Contas chinesas: `jwt\|device_mid`, `note\|jwt\|device_mid` ou `note\|jwt\|device_mid\|captcha` |
| `ZCODE_INTL_TOKENS` | Contas internacionais no mesmo formato |
| `ZCODE_PLAN_ID` | ID opcional para forçar um plano |
| `ZCODE_APP_VERSION` | Substitui a versão do cliente; padrão `3.16.2` |
| `ZCODE_CAPTCHA_PARAM` | Valor global de `X-Aliyun-Captcha-Verify-Param` |
| `ZCODE_ACTIVATION` | Padrão `1`; use `0` para desativar eventos de ativação |

Separe contas por linha ou `&`. Não use `|` dentro da observação.

## Sucesso e privacidade

O resgate só é confirmado com HTTP 200, `code=0` e um objeto de plano com período de validade. `1003` é tratado como resultado idempotente de já resgatado no período. O CAPTCHA não é resolvido automaticamente; se ocorrer `3007`, capture um valor `X-Aliyun-Captcha-Verify-Param` de uma solicitação claim no navegador.

`zcode_cn_devices.json` e `zcode_intl_devices.json` contêm identificadores fixos de dispositivo e são ignorados pelo Git. Não publique JWT, ID de usuário, parâmetros de CAPTCHA ou arquivos de estado em uma issue ou pull request.

## Limites de uso e redistribuição

As versões oficiais deste projeto são gratuitas, incluindo o repositório, os scripts, as instruções de implantação e os Releases.

Sem autorização escrita explícita do autor, não empacote o projeto como recurso pago, edição interna ou exclusiva, benefício de assinatura, curso pago, implantação paga ou serviço de atualização; não o republique em contas, grupos ou canais sem relação para gerar tráfego ou captar usuários; não remova avisos de autoria e direitos autorais nem reivindique o trabalho como seu; não use o nome, avatar, QR codes ou nome do projeto para sugerir endosso oficial.

Em caso de violação, o autor pode solicitar a remoção do conteúdo e pode pausar atualizações, arquivar ou excluir o repositório. Consulte [NOTICE.md](../NOTICE.md) para as regras completas.

## Links

- [Releases](https://github.com/L0NE-6/ZCode-Daily/releases)
- [Issues](https://github.com/L0NE-6/ZCode-Daily/issues)
- [Código e guia completo em chinês](../README.md)
