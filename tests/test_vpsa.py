"""VPSA(H₂ 합성가스 전용) 회귀 테스트 (Streamlit AppTest).

- VPSA는 증기 재생 에너지(SRD)가 0 → 0으로 나누는 곳 없이 계산되는지
- H₂ SMR 업종에서는 경고 없음, 다른 업종에서는 '전용 기술' 경고가 뜨는지

실행 (CCUS_benchmark 폴더에서):
    PYTHONUTF8=1 python tests/test_vpsa.py
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"
WARN = "전용 기술입니다"


def _app_with_vpsa(sector: str):
    from streamlit.testing.v1 import AppTest

    os.chdir(APP_DIR)
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    at = AppTest.from_file(str(APP_PATH), default_timeout=240)
    at.run()
    at.selectbox(key="source_sector").select(sector).run()
    at.multiselect(key="selected_techs").set_value(["MEA_baseline", "VPSA_Syngas"]).run()
    return at


def _warnings(at) -> list:
    return [str(w.value) for w in at.warning if WARN in str(w.value)]


def test_json_vpsa_entry():
    t = json.loads((APP_DIR / "data" / "ccus_metrics.json").read_text(encoding="utf-8"))["technologies"]
    v = t["VPSA_Syngas"]
    assert v["performance"]["SRD_GJ_per_tCO2"] == 0.0
    assert v["applicable_sectors"] == ["h2_smr"]
    assert t["TSA_Solid"]["performance"]["SRD_GJ_per_tCO2"] == 2.70


def test_vpsa_in_h2_sector():
    at = _app_with_vpsa("h2_smr")
    assert not at.exception, [e.message[:200] for e in at.exception]
    assert list(at.multiselect(key="selected_techs").value) == ["MEA_baseline", "VPSA_Syngas"]
    assert not _warnings(at), _warnings(at)


def test_vpsa_in_other_sector_warns():
    at = _app_with_vpsa("cement")
    assert not at.exception, [e.message[:200] for e in at.exception]
    assert _warnings(at), "다른 업종인데 VPSA 경고가 없음"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    failed = 0
    for fn in (test_json_vpsa_entry, test_vpsa_in_h2_sector, test_vpsa_in_other_sector_warns):
        try:
            fn()
            print(f"PASS  {fn.__name__}", flush=True)
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n{e}", flush=True)
    sys.exit(1 if failed else 0)
