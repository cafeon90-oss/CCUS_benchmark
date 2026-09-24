"""PDF 리포트 생성 회귀 테스트 (Streamlit AppTest — 브라우저 없이 앱 실행).

앱의 "PDF 다운로드" 버튼을 실제로 눌러 reportlab(표·문단) 경로와
kaleido 1.x(차트 PNG) 경로를 확인한다. 차트 포함 테스트는 kaleido 1.x와
Chrome/Chromium이 있는 환경에서만 통과한다 (Streamlit Cloud는 packages.txt의 chromium).

실행 (CCUS_benchmark 폴더에서):
    PYTHONUTF8=1 python tests/test_pdf.py      # pytest 없이
    PYTHONUTF8=1 python -m pytest -q tests/    # pytest가 있으면
"""
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # OneDrive 폴더에 __pycache__ 남기지 않기
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"
PDF_OK = "PDF 생성 완료"
CHART_FAIL = ("차트 이미지 변환 실패", "차트 PNG 생성 중 오류")


def _texts(elements) -> list:
    return [str(e.value) for e in elements]


def _generate_pdf(include_charts: bool):
    from streamlit.testing.v1 import AppTest

    os.chdir(APP_DIR)  # app.py가 data/ccus_metrics.json을 상대경로로 읽음
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    at = AppTest.from_file(str(APP_PATH), default_timeout=300)
    at.run()
    assert not at.exception, [e.message[:200] for e in at.exception]
    if include_charts:
        at.checkbox(key="pdf_include_charts").check()
    t0 = time.time()
    at.button(key="btn_generate_pdf").click().run()
    return at, time.time() - t0


def _check(at, dt: float, include_charts: bool) -> str:
    assert not at.exception, [e.message[:200] for e in at.exception]
    failed = [e for e in _texts(at.error) if "PDF" in e]
    assert not failed, failed
    ok = [s for s in _texts(at.success) if PDF_OK in s]
    assert ok, f"PDF 성공 메시지 없음: {_texts(at.success)}"
    if include_charts:
        chart_fail = [w for w in _texts(at.warning) if any(k in w for k in CHART_FAIL)]
        assert not chart_fail, chart_fail
    return f"{ok[0]} · {dt:.1f}s"


def test_pdf_without_charts():
    at, dt = _generate_pdf(include_charts=False)
    print(f"    {_check(at, dt, include_charts=False)}")


def test_pdf_with_charts():
    at, dt = _generate_pdf(include_charts=True)
    print(f"    {_check(at, dt, include_charts=True)}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    failed = 0
    for fn in (test_pdf_without_charts, test_pdf_with_charts):
        try:
            fn()
            print(f"PASS  {fn.__name__}", flush=True)
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n{e}", flush=True)
    sys.exit(1 if failed else 0)
