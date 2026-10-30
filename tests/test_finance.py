"""사업성·비용 모델 회귀 테스트 (Streamlit AppTest).

- 재생 열(증기) 비용이 LCOC에 들어가는지 (열 단가 0이면 LCOC가 낮아짐)
- 보조금 지급 기간: 45Q 12년 → 25년으로 늘리면 NPV가 커짐
- 손익계산서(EBITDA·감가상각·법인세)와 실측 검증 표가 나오는지
- 지역 '한국'을 고르면 전기 단가 기본값이 바뀌는지, 선박 수출 T&S가 계산되는지

실행 (CCUS_benchmark 폴더에서):
    PYTHONUTF8=1 python tests/test_finance.py
"""
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"


def _new_app():
    from streamlit.testing.v1 import AppTest

    os.chdir(APP_DIR)
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    at = AppTest.from_file(str(APP_PATH), default_timeout=300)
    at.run()
    assert not at.exception, [e.message[:200] for e in at.exception]
    return at


def _table(at, column):
    for d in at.dataframe:
        if column in d.value.columns:
            return d.value
    raise AssertionError(f"'{column}' 열이 있는 표가 없음")


def _musd(text):
    """'$-169.9M (-2,328억원)' → -169.9"""
    return float(re.search(r"\$(-?[\d,]+\.?\d*)M", text).group(1).replace(",", ""))


def _lcoc(at, tech="MEA 30 wt% (참고)"):
    t = _table(at, "LCOC")
    return float(t.loc[t["기술"] == tech, "LCOC"].iloc[0].replace(",", ""))


def test_heat_cost_in_lcoc():
    at = _new_app()
    base = _lcoc(at)
    key = next(w.key for w in at.number_input if w.key and w.key.startswith("heat_price_"))
    at.number_input(key=key).set_value(0.0).run()
    assert not at.exception
    # MEA SRD ≈ 3.6 GJ/t × 기본 가스 증기 단가 (미국 약 $5.8/GJ) ≈ $20/t
    assert 15 < base - _lcoc(at) < 30, (base, _lcoc(at))


def test_subsidy_duration_changes_npv():
    at = _new_app()
    npv12 = _musd(_table(at, "IRR [%]").iloc[0]["NPV"])
    at.number_input(key="sub_years_45Q-CCS").set_value(25).run()
    assert not at.exception
    npv25 = _musd(_table(at, "IRR [%]").iloc[0]["NPV"])
    assert npv25 > npv12, (npv12, npv25)


def test_pnl_and_validation_tables():
    at = _new_app()
    pnl = _table(at, "EBITDA")
    for col in ("감가상각", "영업이익 (EBIT)", "법인세", "당기순이익"):
        assert col in pnl.columns, col
    val = _table(at, "모델 ÷ 실측")
    assert len(val) == 4, len(val)


def test_region_and_ship_export():
    at = _new_app()
    at.selectbox(key="region").select("KR").run()
    assert not at.exception
    assert at.number_input(key="elec_price_KR").value == 133.0
    at.checkbox(key="ts_enabled").check().run()
    at.selectbox(key="ts_storage_type").select("ship_export").run()
    assert not at.exception, [e.message[:200] for e in at.exception]
    assert any("액화·선적" in str(c.value) for c in at.caption)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    failed = 0
    for fn in (test_heat_cost_in_lcoc, test_subsidy_duration_changes_npv,
               test_pnl_and_validation_tables, test_region_and_ship_export):
        try:
            fn()
            print(f"PASS  {fn.__name__}", flush=True)
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n{e}", flush=True)
    sys.exit(1 if failed else 0)
