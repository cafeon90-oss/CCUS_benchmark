# 비아민계 CO₂ 포집 흡수제 기술 벤치마크

NETL Rev4a · IEAGHG · DOE NETL · KIER 보고서 기반 비아민계 CO₂ 포집 기술 비교 Streamlit 앱.

## 비교 기술

| 기술 | 흡수제/소재 | SRD [GJ/tCO₂] |
|---|---|---|
| MEA (참고) | MEA 30 wt% 수용액 | 3.60 |
| K₂CO₃ / KIERSOL † | K₂CO₃ + 활성화제 | 2.95 |
| Chilled Ammonia (CAP) | NH₃ 28 wt% 수용액 (저온) | 2.40 |
| Biphasic DMX™ † | 3차 아민 (상분리형) | 2.30 |
| Solid Sorbent TSA | 고체 흡착제 | 2.20 |
| Calcium Looping (CaL) | CaO ⇌ CaCO₃ | 3.20 |

`†` = 파일럿/실증 데이터 (Tier C, ±25% 불확실성)

## 주요 기능

- 7개 탭 구성: 종합 비교 / 에너지 분해 / 경제성 / 손실 / 트렌드 / Custom 입력 / 참고문헌
- 4대 KPI 비교: SRD · We · SPECCA · COCA (정렬·델타·색상 코드)
- CAP 냉동기 부하 동적 계산 (냉각수 온도 민감도)
- 24개 출처 audit trail (NETL Rev4a, IEAGHG, KIER, peer-reviewed)
- 다크모드 + 모바일 대응
- 액화탄산~EOR 전 압력대 (5~300 bar) 지원

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run nonamine_co2_benchmark.py
```

브라우저에서 `http://localhost:8501` 접속.

## Streamlit Community Cloud 배포

1. 본 repo를 fork 또는 직접 push
2. https://share.streamlit.io 에서 GitHub 로그인
3. New app → 본 repo 선택
4. Main file path: `nonamine_co2_benchmark.py`
5. Deploy

## 데이터 출처 (요약)

- **NETL Rev4a** — Case B12C (Chilled Ammonia 공식 케이스)
- **IEAGHG TR2013/19** — Calcium Looping
- **DOE NETL** — Solid Sorbent R&D Program
- **KIER** — KIERSOL 파일럿 실증
- **3D Project (H2020)** — TotalEnergies DMX™ 파일럿
- 학술 논문 12편 + 방법론·표준 5건 (앱 내 탭 ⑦ 참고)

## 지표 정의

```
We     [GJe/tCO₂] = We_thermal(Carnot) + We_elec(펌프 + 압축 + 냉동기 + 보조)
SPECCA [MJ/tCO₂]  = (SRD × 500 + We_elec × 2,500) / capture
COCA   [USD/tCO₂] = (연환산 CAPEX + OPEX) / 연 포집량

Carnot η = (T_hot - T_cold) / T_hot
실효 η   = Carnot η × 0.55  (second-law factor, Bejan 2016 / Kotas 1985)
```

## 주의사항

본 툴의 수치는 공개 보고서 기반 representative values. 실제 프로젝트는 EPC 견적·실증 데이터로 보정 필요. Tier C(†) 데이터는 상용 스케일에서 ±25% 이상 변동 가능.

## License

MIT
