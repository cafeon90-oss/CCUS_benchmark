"""건식 흡착제 교체비 회귀 테스트.

- calc_sorbent_replacement(): app.py를 import하지 않고 AST로 함수만 뽑아 계산식 확인
- 앱: 흡착 기술(TSA)이 기본 선택일 때 사이드바 단가·수명 입력이 뜨고, 수명을 바꾸면
  교체비 안내가 따라 바뀌며 예외가 없는지 (Streamlit AppTest)

실행 (CCUS_benchmark 폴더에서):
    PYTHONUTF8=1 python tests/test_sorbent.py
"""
import ast
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"


def _load_func(name: str):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns: dict = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec"), ns)
    return ns[name]


def test_replacement_formula():
    f = _load_func("calc_sorbent_replacement")
    loss, opex = f(1.0, 10.0, 3.0)
    assert abs(loss - 1.0 / 3.0) < 1e-9 and abs(opex - 10.0 / 3.0) < 1e-9
    assert f(1.0, 10.0, 0.0) == (0.0, 0.0)          # 수명 0은 0으로 방어
    assert f(2.0, 5.0, 1.0) == (2.0, 10.0)


def test_json_defaults_consistent():
    """JSON의 OPEX_solvent·loss가 sorbent 기본값으로 계산한 값과 맞는지 (CBAM은 OPEX만 읽음)."""
    t = json.loads((APP_DIR / "data" / "ccus_metrics.json").read_text(encoding="utf-8"))["technologies"]
    for key, v in t.items():
        sb = v.get("sorbent")
        if not sb:
            continue
        loss = sb["inventory_kg_per_tpy"] / sb["lifetime_yr"]
        assert abs(v["operations"]["loss_kg_per_tCO2"] - loss) < 0.01, key
        assert abs(v["economics"]["OPEX_solvent_USD_per_tCO2"] - loss * sb["price_USD_per_kg"]) < 0.05, key


def _sorbent_caption(at) -> str:
    return next((str(c.value) for c in at.sidebar.caption if "흡착제 교체비" in str(c.value)), "")


def test_app_sorbent_inputs():
    from streamlit.testing.v1 import AppTest

    os.chdir(APP_DIR)
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    at = AppTest.from_file(str(APP_PATH), default_timeout=240)
    at.run()
    assert not at.exception, [e.message[:200] for e in at.exception]
    assert "$3.3/tCO₂" in _sorbent_caption(at), _sorbent_caption(at)
    at.number_input(key="sorbent_life").set_value(1.0).run()
    assert not at.exception, [e.message[:200] for e in at.exception]
    assert "$10.0/tCO₂" in _sorbent_caption(at), _sorbent_caption(at)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    failed = 0
    for fn in (test_replacement_formula, test_json_defaults_consistent, test_app_sorbent_inputs):
        try:
            fn()
            print(f"PASS  {fn.__name__}", flush=True)
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n{e}", flush=True)
    sys.exit(1 if failed else 0)
