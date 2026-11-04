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


CN = load_script("zcode_cn_daily_test", "zcode_cn_daily.py")
INTL = load_script("zcode_intl_daily_test", "zcode_intl_daily.py")


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def account(user_id="user-1", jwt="secret-jwt-value"):
    return {
        "note": "test",
        "jwt": jwt,
        "device_mid": "device-test",
        "captcha": "",
        "user_id": user_id,
    }


def plan_payload(plan_id="daily-plan", ends_at=None, starts_at=None):
    now = int(time.time())
    return plans_payload([
        {
            "plan_id": plan_id,
            "name": "Daily",
            "priority": 10,
            "starts_at": starts_at or now,
            "ends_at": ends_at or now + 3600,
        }
    ])


def plans_payload(plans):
    return {
        "code": 0,
        "data": {
            "plans": plans
        },
    }


def empty_preview():
    return {"code": 0, "data": {"plans": []}}


def claim_success(plan_id="daily-plan", ends_at=None, starts_at=None):
    now = int(time.time())
    return {
        "code": 0,
        "data": {
            "plan": {
                "plan_id": plan_id,
                "starts_at": starts_at or now,
                "ends_at": ends_at or now + 3600,
            }
        },
    }


def run_claim(module, account_data, preview_payload, claim_payload=None):
    claim_calls = []

    def fake_claim(*args, **kwargs):
        claim_calls.append((args, kwargs))
        return FakeResponse(claim_payload or claim_success())

    with mock.patch.dict(module.os.environ, {"ZCODE_PLAN_ID": "", "ZCODE_MARKETING_RECHECK": "0"}), \
            mock.patch.object(module, "report_activation", return_value=(False, "test")), \
            mock.patch.object(module, "preview", return_value=FakeResponse(preview_payload)), \
            mock.patch.object(
                module,
                "query_marketing_plans",
                return_value=module._source_result(True, plans=[]),
            ), \
            mock.patch.object(module, "claim", side_effect=fake_claim):
        result = module.do_claim(account_data)
    return result, claim_calls


class ClaimLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)

    def ledger_path(self, module):
        return self.base / Path(module.CLAIM_LEDGER_STORE).name

    def patch_ledger(self, module, path=None):
        return mock.patch.object(module, "CLAIM_LEDGER_STORE", str(path or self.ledger_path(module)))

    def test_default_paths_and_gitignore(self):
        self.assertEqual(Path(CN.CLAIM_LEDGER_STORE).parent, ROOT)
        self.assertEqual(Path(INTL.CLAIM_LEDGER_STORE).parent, ROOT)
        ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("zcode_cn_claim_ledger.json", ignore_text)
        self.assertIn("zcode_intl_claim_ledger.json", ignore_text)

    def test_first_claim_is_private_and_persisted(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                result, calls = run_claim(module, account(), plan_payload())
                self.assertTrue(result[0], result)
                self.assertIn("领取成功", result[1])
                self.assertEqual(len(calls), 1)

                raw = Path(module.CLAIM_LEDGER_STORE).read_text(encoding="utf-8")
                self.assertNotIn("secret-jwt-value", raw)
                self.assertNotIn("user-1", raw)
                data = json.loads(raw)
                self.assertEqual(data["version"], 1)
                self.assertEqual(len(data["claims"]), 1)
                self.assertEqual(
                    set(data["claims"][0]),
                    {"account", "region", "plan_id", "claimed_at", "expiry"},
                )
                self.assertEqual(data["claims"][0]["region"], module.REGION)

    def test_repeat_run_uses_ledger_and_survives_token_refresh(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                first, first_calls = run_claim(module, account(), plan_payload())
                self.assertTrue(first[0], first)
                self.assertEqual(len(first_calls), 1)

                refreshed = account(jwt="rotated-jwt-value")
                second, second_calls = run_claim(module, refreshed, plan_payload())
                self.assertTrue(second[0], second)
                self.assertIn("今日已领取", second[1])
                self.assertEqual(second_calls, [])

    def test_empty_preview_with_ledger_hit_is_neutral_success(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                first, _ = run_claim(module, account(), plan_payload())
                self.assertTrue(first[0], first)

                second, calls = run_claim(module, account(), empty_preview())
                self.assertTrue(second[0], second)
                self.assertIn("今日已领取", second[1])
                self.assertNotIn("现在没有可领取的套餐", second[1])
                self.assertEqual(calls, [])

    def test_empty_preview_without_ledger_does_not_fake_success(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                result, calls = run_claim(module, account(), empty_preview())
                self.assertFalse(result[0], result)
                self.assertIn("当前无新套餐", result[1])
                self.assertEqual(calls, [])
                self.assertFalse(Path(module.CLAIM_LEDGER_STORE).exists())

    def test_identity_change_is_isolated(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                first, _ = run_claim(module, account(user_id="user-a"), plan_payload())
                self.assertTrue(first[0], first)

                changed, calls = run_claim(module, account(user_id="user-b"), empty_preview())
                self.assertFalse(changed[0], changed)
                self.assertIn("本地台账无命中", changed[1])
                self.assertEqual(calls, [])

    def test_expired_previous_period_same_plan_does_not_match(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION):
                now = module.beijing_now()
                now_ts = int(now.timestamp())
                account_hash = module.stable_account_hash(account())
                ledger = {
                    "version": module.CLAIM_LEDGER_VERSION,
                    "claims": [
                        {
                            "account": account_hash,
                            "region": module.REGION,
                            "plan_id": "daily-plan",
                            "claimed_at": now_ts - 2 * 24 * 60 * 60,
                            "expiry": now_ts - 24 * 60 * 60,
                        }
                    ],
                }
                plan = module._normalize_plan(
                    {
                        "plan_id": "daily-plan",
                        "starts_at": now_ts - 60,
                        "ends_at": now_ts + 3600,
                    },
                    "billing",
                )
                self.assertIsNone(
                    module.find_claimed_plan(ledger, account_hash, plan, now)
                )

    def test_unclaimed_plan_after_higher_priority_claim_is_claimed(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                now = int(time.time())
                first, _ = run_claim(module, account(), plan_payload(plan_id="high-plan"))
                self.assertTrue(first[0], first)

                next_preview = plans_payload([
                    {
                        "plan_id": "high-plan",
                        "name": "High",
                        "priority": 20,
                        "starts_at": now,
                        "ends_at": now + 3600,
                    },
                    {
                        "plan_id": "new-plan",
                        "name": "New",
                        "priority": 10,
                        "starts_at": now,
                        "ends_at": now + 7200,
                    },
                ])
                second, calls = run_claim(
                    module,
                    account(jwt="rotated-jwt-value"),
                    next_preview,
                    claim_success("new-plan", ends_at=now + 7200),
                )
                self.assertTrue(second[0], second)
                self.assertIn("New", second[1])
                self.assertEqual(len(calls), 1)

    def test_retention_prunes_entries_older_than_90_days(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                now = module.beijing_now()
                now_ts = int(now.timestamp())
                account_hash = module.stable_account_hash(account())
                raw = {
                    "version": 1,
                    "claims": [
                        {
                            "account": account_hash,
                            "region": module.REGION,
                            "plan_id": "old-plan",
                            "claimed_at": now_ts - 91 * 24 * 60 * 60,
                            "expiry": now_ts + 3600,
                        },
                        {
                            "account": account_hash,
                            "region": module.REGION,
                            "plan_id": "recent-plan",
                            "claimed_at": now_ts - 60,
                            "expiry": now_ts + 3600,
                        },
                    ],
                }
                Path(module.CLAIM_LEDGER_STORE).write_text(
                    json.dumps(raw, ensure_ascii=False), encoding="utf-8"
                )

                ledger = module.load_claim_ledger()
                self.assertEqual([item["plan_id"] for item in ledger["claims"]], ["recent-plan"])
                saved = json.loads(Path(module.CLAIM_LEDGER_STORE).read_text(encoding="utf-8"))
                self.assertEqual([item["plan_id"] for item in saved["claims"]], ["recent-plan"])

    def test_bad_json_does_not_crash_and_service_state_continues(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                Path(module.CLAIM_LEDGER_STORE).write_text("{broken", encoding="utf-8")
                result, calls = run_claim(module, account(), plan_payload())
                self.assertTrue(result[0], result)
                self.assertEqual(len(calls), 1)
                recovered = json.loads(Path(module.CLAIM_LEDGER_STORE).read_text(encoding="utf-8"))
                self.assertEqual(len(recovered["claims"]), 1)

    def test_bad_json_with_empty_preview_is_neutral(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                Path(module.CLAIM_LEDGER_STORE).write_text("{broken", encoding="utf-8")
                result, calls = run_claim(module, account(), empty_preview())
                self.assertFalse(result[0], result)
                self.assertIn("当前无新套餐", result[1])
                self.assertEqual(calls, [])

    def test_unknown_ledger_version_is_not_overwritten_on_load(self):
        for module in (CN, INTL):
            with self.subTest(region=module.REGION), self.patch_ledger(module):
                original = '{"version": 2, "claims": []}'
                Path(module.CLAIM_LEDGER_STORE).write_text(original, encoding="utf-8")
                ledger = module.load_claim_ledger()
                self.assertEqual(ledger["claims"], [])
                self.assertEqual(
                    Path(module.CLAIM_LEDGER_STORE).read_text(encoding="utf-8"),
                    original,
                )

    def test_cn_and_intl_ledgers_are_isolated(self):
        cn_path = self.base / "zcode_cn_claim_ledger.json"
        intl_path = self.base / "zcode_intl_claim_ledger.json"
        with self.patch_ledger(CN, cn_path):
            first, _ = run_claim(CN, account(), plan_payload())
            self.assertTrue(first[0], first)

        with self.patch_ledger(INTL, intl_path):
            changed, calls = run_claim(INTL, account(), empty_preview())
            self.assertFalse(changed[0], changed)
            self.assertIn("本地台账无命中", changed[1])
            self.assertEqual(calls, [])

        self.assertTrue(cn_path.exists())
        self.assertFalse(intl_path.exists())
        self.assertNotEqual(CN.CLAIM_LEDGER_STORE, INTL.CLAIM_LEDGER_STORE)


if __name__ == "__main__":
    unittest.main()
