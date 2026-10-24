"""민감도(Tornado)·Monte Carlo 회귀 테스트 (Streamlit AppTest).

- Tornado: 기본 분석 기술 = 선택 기술 중 COCA 최저, 다른 기술로 바꿔도 예외 없음
- Monte Carlo: 선택 기술 전부가 표에 나오고, 같은 입력이면 같은 결과 (seed 고정)

실행 (CCUS_benchmark 폴더에서):
    PYTHONUTF8=1 python tests/test_sensitivity.py
"""
import os
import sys
import time
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


def _mc_table(at):
    for d in at.dataframe:
        if "Net COCA 최저일 확률" in d.value.columns:
            return d.value
    return None


def test_tornado_default_and_switch():
    at = _new_app()
    # 기본 선택 5종 중 COCA 최저는 TSA (2026-10 데이터 기준)
    assert at.selectbox(key="sens_tech").value == "TSA_Solid"
    assert any("가장 크게 흔듦" in str(c.value) for c in at.caption)
    at.selectbox(key="sens_tech").select("MEA_baseline").run()
    assert not at.exception, [e.message[:200] for e in at.exception]
    assert any("가장 크게 흔듦" in str(c.value) for c in at.caption)


def test_monte_carlo_all_techs():
    at = _new_app()
    n_techs = len(at.multiselect(key="selected_techs").value)
    t0 = time.time()
    at.checkbox(key="mc_run").check().run()
    elapsed = time.time() - t0
    assert not at.exception, [e.message[:200] for e in at.exception]
    table = _mc_table(at)
    assert table is not None, "Monte Carlo 표가 없음"
    assert len(table) == n_techs, (len(table), n_techs)
    first = table.to_csv()
    at.run()  # 같은 입력 → 같은 결과
    assert _mc_table(at).to_csv() == first
    print(f"    Monte Carlo {n_techs}개 기술 · {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    failed = 0
    for fn in (test_tornado_default_and_switch, test_monte_carlo_all_techs):
        try:
            fn()
            print(f"PASS  {fn.__name__}", flush=True)
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n{e}", flush=True)
    sys.exit(1 if failed else 0)
