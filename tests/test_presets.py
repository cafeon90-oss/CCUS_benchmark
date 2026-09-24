"""프리셋 × TRL 필터 회귀 테스트 (Streamlit AppTest — 브라우저 없이 앱 실행).

배경: apply_preset()은 st.session_state에 값을 직접 써서 위젯의 min/max·options 검증을
건너뛴다. 이때 Streamlit(1.5x)은 에러를 내지 않고, 범위 밖 숫자는 기본값으로 되돌리고
옵션 밖 값은 빼 버린다 → 크래시가 아니라 '조용히 틀린 입력'. 그래서 예외 여부뿐 아니라
프리셋 값이 실제 위젯 값으로 그대로 들어갔는지를 검사한다.

실행 (CCUS_benchmark 폴더에서):
    PYTHONUTF8=1 python tests/test_presets.py      # pytest 없이
    PYTHONUTF8=1 python -m pytest -q tests/        # pytest가 있으면
"""
import ast
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # OneDrive 폴더에 __pycache__ 남기지 않기
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")  # deprecation 로그 억제

APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"


def _load_presets() -> dict:
    """app.py를 import하지 않고 PRESETS 리터럴만 AST로 추출."""
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PRESETS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("PRESETS not found in app.py")


def _load_trl() -> dict:
    data = json.loads((APP_DIR / "data" / "ccus_metrics.json").read_text(encoding="utf-8"))
    return {k: v.get("TRL", 7) for k, v in data["technologies"].items()}


PRESETS = _load_presets()
TRL = _load_trl()


def _new_app():
    from streamlit.testing.v1 import AppTest

    os.chdir(APP_DIR)  # app.py가 data/ccus_metrics.json을 상대경로로 읽음
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    at = AppTest.from_file(str(APP_PATH), default_timeout=240)
    at.run()
    assert not at.exception, f"초기 실행 실패: {[e.message for e in at.exception]}"
    return at


def _check_preset(preset_key: str, drop_le6: bool) -> list:
    """프리셋 적용 후 문제 목록을 돌려준다 (비어 있으면 통과)."""
    preset = PRESETS[preset_key]
    tag = f"{preset_key} [{'TRL<=6 off' if drop_le6 else 'default filter'}]"
    at = _new_app()
    le6 = next(v for v in at.multiselect(key="trl_filter").value if "≤6" in v)
    if drop_le6:
        at.multiselect(key="trl_filter").unselect(le6).run()
    at.selectbox(key="preset_select").select(preset_key).run()

    if at.exception:
        return [f"{tag}: exception {[e.message[:200] for e in at.exception]}"]
    problems = []
    for k, v in preset["settings"].items():
        got = at.session_state[k] if k in at.session_state else "<missing>"
        if got != v:
            problems.append(f"{tag}: {k} = {got!r} (프리셋 값 {v!r})")
    got_techs = list(at.multiselect(key="selected_techs").value)
    if got_techs != list(preset["techs"]):
        problems.append(f"{tag}: selected_techs = {got_techs} (프리셋 값 {preset['techs']})")
    if drop_le6 and any(TRL.get(t, 7) <= 6 for t in preset["techs"]):
        if le6 not in at.multiselect(key="trl_filter").value:
            problems.append(f"{tag}: TRL ≤6 필터가 다시 켜지지 않음")
        if not any("≤6" in str(c.value) for c in at.caption):
            problems.append(f"{tag}: TRL 필터 자동 추가 안내가 표시되지 않음")
    return problems


def test_presets_default_filter():
    problems = [p for k in PRESETS for p in _check_preset(k, drop_le6=False)]
    assert not problems, "\n".join(problems)


def test_presets_with_trl_le6_unchecked():
    problems = [p for k in PRESETS for p in _check_preset(k, drop_le6=True)]
    assert not problems, "\n".join(problems)


def test_min_capture_renders():
    """포집량 하한(0.01 Mt/yr)에서 앱 전체가 예외 없이 그려지는지."""
    at = _new_app()
    at.number_input(key="capture_mt_yr").set_value(0.01).run()
    assert not at.exception, [e.message[:200] for e in at.exception]
    assert at.session_state["capture_mt_yr"] == 0.01


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    failed = 0
    for fn in (test_presets_default_filter, test_presets_with_trl_le6_unchecked, test_min_capture_renders):
        try:
            fn()
            print(f"PASS  {fn.__name__}", flush=True)
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n{e}", flush=True)
    sys.exit(1 if failed else 0)
