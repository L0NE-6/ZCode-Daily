import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CN = load_script("zcode_cn_marketing_test", "zcode_cn_daily.py")
INTL = load_script("zcode_intl_marketing_test", "zcode_intl_daily.py")


class FakeResponse:
    def __init__(self, payload, status_code=200, content=None):
        self.payload = payload
        self.status_code = status_code
        self.content = content

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def account(user_id="user-1", jwt="secret-jwt-value"):
    return {
        "note": "test",
        "jwt": jwt,
        "device_mid": "device-test",
        "captcha": "",
        "user_id": user_id,
    }


def source_plan(plan_id="marketing-plan", source="marketing", starts_at=None, ends_at=None,
                priority=10, campaigns=None):
    now = int(time.time())
    return {
        "plan_id": plan_id,
        "name": "Marketing Plan",
        "description": "",
        "priority": priority,
        "starts_at": starts_at if starts_at is not None else now,
        "ends_at": ends_at if ends_at is not None else now + 3600,
        "entitlements": [
            {
                "name": "GLM-5.3-Flash",
                "unit": "tokens",
                "grant": 300000000,
                "period": "",
            }
        ],
        "sources": [source],
        "campaign_ids": list(campaigns or ("campaign-1",) if source == "marketing" else ()),
    }


def marketing_payload(plan_id="marketing-plan", campaign_id="campaign-1",
                      starts_at=None, ends_at=None):
    now = int(time.time())
    return {
        "code": 0,
        "data": {
            "deliveries": [
                {
                    "campaign_id": campaign_id,
                    "priority": 7,
                    "resource_position": "banner",
                    "banner": {
                        "buttons": [
                            {"action": {"type": "close"}},
                            {
                                "action": {
                                    "type": "claim_zcode_plan",
                                    "args": {"plan_id": plan_id},
                                }
                            },
                        ],
                        "background": {
                            "args": {
                                "zcode_plan": {
                                    "plan_id": plan_id,
                                    "name": "ZCODE GLOBAL BUILD",
                                    "starts_at": starts_at if starts_at is not None else now,
                                    "ends_at": ends_at if ends_at is not None else now + 3600,
                                    "priority": 8,
                                    "entitlements": [
                                        {
                                            "show_name": "GLM-5.3-Flash",
                                            "grant_units": 300000000,
                                            "period": "daily",
                                        }
                                    ],
                                }
                            }
                        },
                    },
                }
            ]
        },
    }


def claim_success(plan_id="marketing-plan", starts_at=None, ends_at=None):
    now = int(time.time())
    return {
        "code": 0,
        "data": {
            "plan": {
                "plan_id": plan_id,
                "starts_at": starts_at if starts_at is not None else now,
                "ends_at": ends_at if ends_at is not None else now + 3600,
            }
        },
    }


def success(plans, delivery_count=None):
    return {
        "ok": True,
        "plans": plans,
        "error": "",
        "skipped": False,
        "deployed": True,
        "delivery_count": delivery_count,
    }


def failure(message):
    return {
        "ok": False,
        "plans": [],
        "error": message,
        "skipped": False,
        "deployed": True,
        "delivery_count": None,
    }


class MarketingProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)

    def claim_path(self, module):
        return self.base / Path(module.CLAIM_LEDGER_STORE).name

    def run_claim(self, module, billing, marketing, claim_payload=None,
                  confirm_result=(True, "营销回执已确认（1 个 campaign）"),
                  recheck_note="；营销活动位已下线（正向证据）", env=None):
        claim_calls = []

        def fake_claim(*args, **kwargs):
            claim_calls.append((args, kwargs))
            return FakeResponse(claim_payload or claim_success())

        environment = {
            "ZCODE_PLAN_ID": "",
            "ZCODE_APP_VERSION": "3.18.0",
            "ZCODE_MARKETING_RECHECK": "1",
        }
        environment.update(env or {})
        with mock.patch.dict(module.os.environ, environment, clear=True), \
                mock.patch.object(module, "CLAIM_LEDGER_STORE", str(self.claim_path(module))), \
                mock.patch.object(module, "report_activation", return_value=(False, "test")), \
                mock.patch.object(module, "query_billing_plans", return_value=billing) as billing_query, \
                mock.patch.object(module, "query_marketing_plans", return_value=marketing) as marketing_query, \
                mock.patch.object(module, "claim", side_effect=fake_claim), \
                mock.patch.object(module, "confirm_marketing_claim", return_value=confirm_result) as confirm_query, \
                mock.patch.object(module, "recheck_marketing_claim", return_value=recheck_note):
            result = module.do_claim(account())
        return result, claim_calls, billing_query, marketing_query, confirm_query

    def test_default_version_is_3_18_0_and_override_is_kept(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), \
                    mock.patch.dict(module.os.environ, {"ZCODE_APP_VERSION": ""}, clear=True):
                self.assertEqual(module.app_version(), "3.18.0")
            with mock.patch.dict(module.os.environ, {"ZCODE_APP_VERSION": "3.17.1"}, clear=True):
                self.assertEqual(module.app_version(), "3.17.1")

    def test_marketing_version_gate_and_headers(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                with mock.patch.dict(module.os.environ, {"ZCODE_APP_VERSION": "3.16.3"}, clear=True), \
                        mock.patch.object(module, "request") as request_mock:
                    result = module.query_marketing_plans("jwt", "mid")
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["skipped"])
                    request_mock.assert_not_called()

                with mock.patch.dict(module.os.environ, {"ZCODE_APP_VERSION": "3.17.1"}, clear=True), \
                        mock.patch.object(
                            module,
                            "request",
                            return_value=FakeResponse(marketing_payload()),
                        ) as request_mock:
                    result = module.query_marketing_plans("jwt", "mid")
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(len(result["plans"]), 1)
                    args, kwargs = request_mock.call_args
                    self.assertEqual(args[0], "GET")
                    self.assertTrue(args[1].endswith("/api/v1/marketing/touch?seq=0"))
                    self.assertEqual(kwargs["headers"], {
                        "X-Client-Language": "zh-CN",
                        "X-ZCode-App-Version": "3.17.1",
                        "Authorization": "Bearer jwt",
                        "X-Device-Mid": "mid",
                    })
                self.assertFalse(module._version_at_least("bad-version", "3.17.1"))
                self.assertFalse(module._version_at_least("3.16.99", "3.17.1"))
                self.assertTrue(module._version_at_least("3.17.1", "3.17.1"))
                skipped_warning = module.source_warning((
                    "marketing",
                    module._source_result(False, error="version gate", skipped=True),
                ))
                self.assertNotIn("部分来源失败", skipped_warning)
                self.assertIn("来源未查询", skipped_warning)

    def test_nested_banner_plan_metadata_is_collected(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                plans, error = module.parse_marketing_plans(marketing_payload())
                self.assertEqual(error, "")
                self.assertEqual(len(plans), 1)
                plan = plans[0]
                self.assertEqual(plan["plan_id"], "marketing-plan")
                self.assertEqual(plan["campaign_ids"], ["campaign-1"])
                self.assertEqual(plan["sources"], ["marketing"])
                self.assertEqual(plan["priority"], 8)
                self.assertEqual(plan["entitlements"][0]["name"], "GLM-5.3-Flash")

    def test_two_sources_merge_by_plan_id(self):
        now = int(time.time())
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                billing_plan = source_plan(
                    "same-plan", "billing", now + 100, now + 900, priority=4
                )
                marketing_plan = source_plan(
                    "same-plan", "marketing", now + 200, now + 800, priority=9
                )
                merged = module.merge_plan_sources([billing_plan], [marketing_plan])
                self.assertEqual(len(merged), 1)
                self.assertEqual(merged[0]["sources"], ["billing", "marketing"])
                self.assertEqual(merged[0]["campaign_ids"], ["campaign-1"])
                self.assertEqual(merged[0]["starts_at"], now + 100)
                self.assertEqual(merged[0]["ends_at"], now + 900)
                self.assertEqual(merged[0]["priority"], 9)

    def test_non_overlapping_same_plan_uses_first_complete_window(self):
        now = int(time.time())
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                billing_plan = source_plan(
                    "same-plan", "billing", now, now + 100, priority=5
                )
                marketing_plan = source_plan(
                    "same-plan", "marketing", now + 1000, now + 1100, priority=9
                )
                merged = module.merge_plan_sources([billing_plan], [marketing_plan])
                self.assertEqual(merged[0]["starts_at"], now)
                self.assertEqual(merged[0]["ends_at"], now + 100)
                self.assertLess(merged[0]["starts_at"], merged[0]["ends_at"])

    def test_same_plan_from_both_sources_claims_once(self):
        now = int(time.time())
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                billing_plan = source_plan(
                    "same-plan", "billing", now, now + 3600, priority=5
                )
                marketing_plan = source_plan(
                    "same-plan", "marketing", now, now + 3600, priority=8
                )
                result, calls, _, _, confirm_query = self.run_claim(
                    module,
                    success([billing_plan]),
                    success([marketing_plan]),
                    claim_payload=claim_success("same-plan", now, now + 3600),
                )
                self.assertTrue(result[0], result)
                self.assertEqual(len(calls), 1)
                confirm_query.assert_called_once()
                ledger = json.loads(self.claim_path(module).read_text(encoding="utf-8"))
                self.assertEqual(len(ledger["claims"]), 1)

    def test_changed_end_same_start_uses_ledger(self):
        now = int(time.time())
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                first_plan = source_plan(
                    "same-plan", "billing", now, now + 3600, priority=5
                )
                first, _, _, _, _ = self.run_claim(
                    module,
                    success([first_plan]),
                    success([]),
                    claim_payload=claim_success("same-plan", now, now + 3600),
                )
                self.assertTrue(first[0], first)

                shifted_plan = source_plan(
                    "same-plan", "marketing", now, now + 3000, priority=8
                )
                second, second_calls, _, _, _ = self.run_claim(
                    module,
                    success([]),
                    success([shifted_plan]),
                )
                self.assertTrue(second[0], second)
                self.assertEqual(second_calls, [])

    def test_billing_empty_marketing_hit_claims(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                plan = source_plan()
                result, calls, billing_query, marketing_query, confirm_query = self.run_claim(
                    module, success([]), success([plan])
                )
                self.assertTrue(result[0], result)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][0][1], "marketing-plan")
                billing_query.assert_called_once()
                marketing_query.assert_called_once()
                confirm_query.assert_called_once()
                self.assertIn("营销回执已确认", result[1])

    def test_one_source_failure_does_not_clear_other(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                result, calls, billing_query, marketing_query, _ = self.run_claim(
                    module,
                    failure("billing down"),
                    success([source_plan()]),
                )
                self.assertTrue(result[0], result)
                self.assertEqual(len(calls), 1)
                billing_query.assert_called_once()
                marketing_query.assert_called_once()
                self.assertIn("部分来源失败", result[1])
                self.assertIn("billing down", result[1])

    def test_marketing_failure_does_not_clear_billing(self):
        now = int(time.time())
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                plan = source_plan("billing-plan", "billing", now, now + 3600)
                result, calls, billing_query, marketing_query, _ = self.run_claim(
                    module,
                    success([plan]),
                    failure("marketing down"),
                    claim_payload=claim_success("billing-plan", now, now + 3600),
                )
                self.assertTrue(result[0], result)
                self.assertEqual(len(calls), 1)
                billing_query.assert_called_once()
                marketing_query.assert_called_once()
                self.assertIn("部分来源失败", result[1])
                self.assertIn("marketing down", result[1])

    def test_both_sources_fail_without_ledger_is_explicit_error(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                result, calls, _, _, _ = self.run_claim(
                    module,
                    failure("billing down"),
                    failure("marketing down"),
                )
                self.assertFalse(result[0], result)
                self.assertEqual(calls, [])
                self.assertIn("billing down", result[1])
                self.assertIn("marketing down", result[1])

    def test_both_sources_fail_with_ledger_hit_is_neutral_success(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                first, _, _, _, _ = self.run_claim(
                    module,
                    success([]),
                    success([source_plan()]),
                )
                self.assertTrue(first[0], first)
                second, calls, _, _, _ = self.run_claim(
                    module,
                    failure("billing down"),
                    failure("marketing down"),
                )
                self.assertTrue(second[0], second)
                self.assertEqual(calls, [])
                self.assertIn("今日已领取", second[1])

    def test_future_window_does_not_claim_and_reports_beijing_time(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                now = int(module.beijing_now().timestamp())
                starts_at = now + 3600
                plan = source_plan(starts_at=starts_at, ends_at=starts_at + 3600)
                result, calls, _, _, _ = self.run_claim(
                    module, success([]), success([plan])
                )
                self.assertFalse(result[0], result)
                self.assertEqual(calls, [])
                self.assertIn("活动窗口未开启", result[1])
                self.assertIn(module.format_time(starts_at), result[1])

    def test_expired_window_does_not_claim(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                now = int(module.beijing_now().timestamp())
                ends_at = now - 1
                plan = source_plan(starts_at=ends_at - 3600, ends_at=ends_at)
                result, calls, _, _, _ = self.run_claim(
                    module, success([]), success([plan])
                )
                self.assertFalse(result[0], result)
                self.assertEqual(calls, [])
                self.assertIn("活动已结束", result[1])
                self.assertIn(module.format_time(ends_at), result[1])

    def test_window_boundaries_and_missing_fields(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                now = module.datetime(2026, 11, 4, 19, 0, tzinfo=module.BEIJING_TZ)
                now_ts = int(now.timestamp())
                self.assertEqual(
                    module.plan_window_state({"starts_at": now_ts, "ends_at": now_ts + 1}, now),
                    "active",
                )
                self.assertEqual(
                    module.plan_window_state({"starts_at": now_ts - 1, "ends_at": now_ts}, now),
                    "expired",
                )
                self.assertEqual(module.plan_window_state({}, now), "active")

    def test_confirm_request_body_and_headers(self):
        plan = source_plan(campaigns=["campaign-a", "campaign-b"])
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), \
                    mock.patch.dict(module.os.environ, {"ZCODE_APP_VERSION": "3.18.0"}, clear=True), \
                    mock.patch.object(
                        module,
                        "request",
                        return_value=FakeResponse({"code": 0, "success": True}),
                    ) as request_mock:
                confirmed, note = module.confirm_marketing_claim("jwt", "mid", plan)
                self.assertTrue(confirmed)
                self.assertIn("营销回执已确认", note)
                self.assertEqual(request_mock.call_count, 2)
                first_args, first_kwargs = request_mock.call_args_list[0]
                self.assertEqual(first_args[0], "POST")
                self.assertTrue(first_args[1].endswith("/api/v1/marketing/touch/action"))
                self.assertEqual(first_kwargs["body"], {
                    "campaign_id": "campaign-a",
                    "action_type": "confirm",
                })
                self.assertEqual(first_kwargs["headers"]["Authorization"], "Bearer jwt")
                self.assertEqual(first_kwargs["headers"]["X-Device-Mid"], "mid")

    def test_confirm_partial_failure_is_explicit(self):
        plan = source_plan(campaigns=["campaign-a", "campaign-b"])
        for module in (CN, INTL):
            responses = [
                FakeResponse({"code": 0, "success": True}),
                FakeResponse({"code": 500, "msg": "confirm failed"}, status_code=500),
            ]
            with self.subTest(region=module.REGION), \
                    mock.patch.dict(module.os.environ, {"ZCODE_APP_VERSION": "3.18.0"}, clear=True), \
                    mock.patch.object(module, "request", side_effect=responses):
                confirmed, note = module.confirm_marketing_claim("jwt", "mid", plan)
                self.assertFalse(confirmed)
                self.assertIn("部分成功", note)
                self.assertIn("campaign-b", note)
                self.assertIn("confirm failed", note)

    def test_confirm_failure_does_not_flip_claim_success(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                result, calls, _, _, _ = self.run_claim(
                    module,
                    success([]),
                    success([source_plan()]),
                    confirm_result=(False, "营销回执失败: HTTP 500"),
                    recheck_note="",
                )
                self.assertTrue(result[0], result)
                self.assertEqual(len(calls), 1)
                self.assertIn("营销回执失败", result[1])
                self.assertIn("不影响已确认领取", result[1])

    def test_1003_is_success_and_enters_ledger(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                result, calls, _, _, confirm_query = self.run_claim(
                    module,
                    success([]),
                    success([source_plan()]),
                    claim_payload={"code": 1003, "msg": "target already exists"},
                )
                self.assertTrue(result[0], result)
                self.assertEqual(len(calls), 1)
                confirm_query.assert_called_once()
                ledger = json.loads(self.claim_path(module).read_text(encoding="utf-8"))
                self.assertEqual(ledger["claims"][0]["plan_id"], "marketing-plan")

    def test_1003_without_expiry_does_not_repeat_request(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                plan = source_plan()
                plan["ends_at"] = None
                first, first_calls, _, _, _ = self.run_claim(
                    module,
                    success([]),
                    success([plan]),
                    claim_payload={"code": 1003, "msg": "target already exists"},
                )
                self.assertTrue(first[0], first)
                self.assertEqual(len(first_calls), 1)
                second, second_calls, _, _, _ = self.run_claim(
                    module,
                    success([]),
                    success([plan]),
                    claim_payload={"code": 1003, "msg": "target already exists"},
                )
                self.assertTrue(second[0], second)
                self.assertEqual(second_calls, [])

    def test_3007_captcha_hint_is_preserved(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                result, calls, _, _, _ = self.run_claim(
                    module,
                    success([]),
                    success([source_plan()]),
                    claim_payload={"code": 3007, "msg": "captcha verify failed"},
                )
                self.assertTrue(calls)
                self.assertFalse(result[0], result)
                self.assertIn("ZCODE_CAPTCHA_PARAM", result[1])

    def test_recursive_and_oversized_marketing_payload_do_not_crash(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                payload = marketing_payload()
                delivery = payload["data"]["deliveries"][0]
                delivery["loop"] = delivery
                plans, error = module.parse_marketing_plans(payload)
                self.assertEqual(error, "")
                self.assertEqual(len(plans), 1)

                deep = payload["data"]["deliveries"][0]
                for _ in range(module.MARKETING_MAX_DEPTH + 5):
                    deep = {"next": deep}
                module.parse_marketing_plans({"code": 0, "data": {"deliveries": [deep]}})

                oversized = {
                    "code": 0,
                    "data": {
                        "deliveries": [{} for _ in range(module.MARKETING_MAX_DELIVERIES + 1)]
                    },
                }
                plans, error = module.parse_marketing_plans(oversized)
                self.assertEqual(plans, [])
                self.assertIn("超过上限", error)

    def test_depth_and_node_limits_stop_traversal(self):
        action = {
            "action": {
                "type": "claim_zcode_plan",
                "args": {"plan_id": "bounded-plan"},
            }
        }
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                shallow = action
                for _ in range(6):
                    shallow = {"next": shallow}
                shallow_payload = {
                    "code": 0,
                    "data": {"deliveries": [{"campaign_id": "campaign-ok", "content": shallow}]},
                }
                plans, error = module.parse_marketing_plans(shallow_payload)
                self.assertEqual(error, "")
                self.assertEqual(plans[0]["plan_id"], "bounded-plan")

                deep = action
                for _ in range(module.MARKETING_MAX_DEPTH + 5):
                    deep = {"next": deep}
                deep_payload = {
                    "code": 0,
                    "data": {"deliveries": [{"campaign_id": "campaign-deep", "content": deep}]},
                }
                plans, error = module.parse_marketing_plans(deep_payload)
                self.assertEqual(error, "")
                self.assertEqual(plans, [])

                huge = {
                    "code": 0,
                    "data": {
                        "deliveries": [
                            {
                                "campaign_id": "campaign-huge",
                                "content": [{"value": index}
                                            for index in range(module.MARKETING_MAX_NODES + 10)],
                                "tail": action,
                            }
                        ]
                    },
                }
                plans, error = module.parse_marketing_plans(huge)
                self.assertEqual(error, "")
                self.assertEqual(plans, [])

    def test_oversized_marketing_http_response_is_rejected(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), \
                    mock.patch.dict(module.os.environ, {"ZCODE_APP_VERSION": "3.18.0"}, clear=True), \
                    mock.patch.object(
                        module,
                        "request",
                        return_value=FakeResponse(
                            {},
                            content=b"x" * (module.MARKETING_MAX_RESPONSE_BYTES + 1),
                        ),
                    ):
                result = module.query_marketing_plans("jwt", "mid")
                self.assertFalse(result["ok"])
                self.assertIn("大小上限", result["error"])

    def test_recheck_disappearance_is_positive_evidence(self):
        plan = source_plan()
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), \
                    mock.patch.dict(module.os.environ, {"ZCODE_MARKETING_RECHECK": "1"}, clear=True), \
                    mock.patch.object(
                        module,
                        "query_marketing_plans",
                        return_value=success([], delivery_count=0),
                    ):
                note = module.recheck_marketing_claim("jwt", "mid", plan)
                self.assertIn("正向证据", note)


if __name__ == "__main__":
    unittest.main()
