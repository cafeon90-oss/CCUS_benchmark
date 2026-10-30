# 🌫️ CO₂ 포집·CCUS 기술·경제성 벤치마크

NETL Rev4a/2022 · IEAGHG · IRS 45Q · KIER 등 공식 자료 기반의 10종 CCUS 기술 통합 비교 시뮬레이터.
규모의 경제·포집율·프로젝트 시나리오·다중 인센티브 stacking을 모두 반영해 **사업 의사결정 수준**의 분석 가능.

> **🆕 v2.0 핵심 기능**
> - 🆚 **시나리오 A vs B 비교 모드** — 두 입력 세트를 한 화면에서 1:1 비교 (10개 KPI · 자동 인사이트 · CSV 다운로드)
> - 📥 **PDF 리포트 1-click 내보내기** — 이사회·EPC·정부 협상용 1~3페이지 보고서 자동 생성
> - 📦 **Single Source of Truth** — `data/ccus_metrics.json` 마스터 데이터를 자매 도구 [🛡️ CBAM 계산기]도 동시 참조

---

## 👤 작성자

**송봉관 / Song BK** — DAC & CCUS 기술사업화 전문가

| 항목 | 링크 |
|---|---|
| 🐙 GitHub | https://github.com/cafeon90-oss |
| 💼 LinkedIn | https://www.linkedin.com/in/bongkwan-song-95a0213ba/ |
| 📝 Blog | https://cdrmaster.tistory.com/ |
| 📧 Email | cafeon90@gmail.com |

---

## 🧪 비교 기술 (9종)

### Advanced Amine (4종, Tier A)
| 기술 | 흡수제 | SRD [GJ/tCO₂] | 대표 사례 |
|---|---|---|---|
| MEA 30 wt% (참고) | MEA + reclaimer | 3.60 | NETL B12B baseline |
| MHI KS-21™ | Hindered amine | 2.80 | Petra Nova, 일본 다수 |
| Cansolv DC-103 | Shell 2세대 amine | 2.50 | Boundary Dam, NETL 2022 |
| Aker S26 | Aker 솔벤트 | 2.80 | Norcem Brevik, Twence |

### 비아민계 (5종)
| 기술 | 흡수제/소재 | SRD | 단계 |
|---|---|---|---|
| K₂CO₃ / KIERSOL † | K₂CO₃ + 활성화제 | 2.95 | Pilot (Tier C) |
| Biphasic DMX™ † | 3차 아민 (상분리) | 2.30 | Pilot (Tier C) |
| Solid Sorbent TSA | 고체 흡착제 (Svante형) | 2.70 | Demo (Tier B) |
| VPSA (H₂ 합성가스) | 제올라이트·활성탄 (진공·압력 변동) | 0 (전기만) | 상용 — Port Arthur, H₂ SMR 전용 |
| Calcium Looping (CaL) | CaO ⇌ CaCO₃ | 3.20 | Pilot (TRL 6, Tier B) |

`†` = 파일럿/실증 데이터 (±25% 불확실성)

기본 화면은 상용·실증(TRL 7 이상) 기술만 보이고, 파일럿 단계(KIERSOL·DMX·CaL)는 사이드바 TRL 필터에서 켤 수 있습니다.
냉각 암모니아(CAP)는 2011년 상업 규모 계획 취소 후 상용 플랜트가 없어 2026-10 제외했습니다.

---

## ✨ 주요 기능

- **5개 탭**: ① 결과 요약 / ② 비용·에너지 (비용·에너지·소재 손실·직접 입력) / ③ 사업성 (손익·NPV·EBITDA·민감도·**🆚 시나리오 비교**) / ④ Net CO₂ (LCA) / ⑤ 근거·사용법 (사용법·방법론·참고문헌·문헌 트렌드·실측 검증)
- **사이드바 3단계**: 사업 지역·배출원·프로젝트 → 비교할 기술 → 규모·처분 경로 (인센티브·상세 가정·LCA 가정은 접어 둠)
- **사업 지역 기본값** (미국·한국·서유럽): 전기·연료 단가, 건설비 계수, 법인세율, 전력 배출계수
- **시나리오 프리셋 6종**: 미국 발전소·한국 시멘트·EU 블루수소·DAC+LCFS·식품급 LCO₂·반도체 LCO₂
- **자동 인사이트 박스** + 추천 메시지
- **5대 KPI**: 연 손익 (메인) + SRD · We · SPECCA · LCOC (균등화 포집 비용) + Net CO₂ 톤당 비용
- **CCS 특화 스케일링** (n=0.65, IEAGHG 기반) + 비용 자료 최대 규모를 넘으면 다계열(n^0.9)
- **포집율 효과** (90% baseline, 99%→+18% SRD)
- **프로젝트 시나리오** (Retrofit/Greenfield/산업 5종)
- **CCU 정제 등급별** 수율·CAPEX adder (식품/고순도/초고순도)
- **다중 인센티브 stacking** (45Q + 시장 + LCFS)
- **지역 색상 코딩** (🟦🟨🟪🟧 — stack 호환성 즉각 식별)
- **호버 툴팁** (계산식 + 출처 포함)
- **통화 toggle** (USD ↔ KRW ↔ Both)
- **80여 개 출처 audit trail** (NETL/IEAGHG/45Q/SDE++/UK CfD/EIA/Eurostat/KEPCO/AACE/IFRS 등)
- **사업성 현금흐름**: 건설 기간·첫해 가동률·보조금 지급 기간(45Q 12년 등)·법인세 → NPV·IRR·회수 기간, 손익계산서(EBITDA·IFRS IAS 16 정액 감가상각·EBIT·순이익)
- **재생 열(증기) 비용**: SRD × 열 단가 (가스 보일러·히트펌프·폐열 등)
- **민감도·Monte Carlo**: 모델 재계산 토네이도, AACE 견적 등급 × 기술 성숙도 로그정규 분포
- **실측 검증**: 포집 플랜트 4곳의 공개 CAPEX와 모델 비교
- **선박 수출 저장** (국내 저장소 없는 한국형 T&S)

### 🆕 신규 기능 (Phase 2)

- **🆚 시나리오 A vs B 비교 모드** — 두 입력 세트를 슬롯에 저장하고 핵심 KPI 10개(연 손익·LCOC·Net LCOC·SRD·We·NPV·IRR·Payback·CRCF·LCA)를 1:1 그룹 막대로 비교. Δ 표(B−A) + 자동 인사이트 + CSV 다운로드.
- **📥 PDF 리포트 내보내기** — KPI 배너 / 시나리오 메타 / 결과 표 / 차트 / LCA 분해 / 방법론 요약을 1~3페이지 PDF로 한 번에 생성 (ReportLab + Plotly Kaleido). 이사회·EPC 견적·정부 협상 input용.
- **📦 Single Source of Truth (SSOT)** — `data/ccus_metrics.json` (schema v1.0) 한 파일이 본 도구 + 자매 도구 [🛡️ CBAM 계산기]의 LIT 데이터 마스터. 한 곳 수정 → 양쪽 자동 동기화 (1h / 24h 캐시).
- **🌱 ④ Net CO₂ (LCA) 탭** — Scope 1+2+3 lifecycle 배출 차감 후 net removed CO₂ + CRCF/ICVCM 등급(A/B/C/D). EU CRCF 2024 의무 대응.
- **🇰🇷 K-ETS CCU 차감 분석** — 한국 할당대상업체 보고용 (직접 매출 아님 — 할당 부족/균형/잉여별 조건부 가치 시나리오 표시).

---

## 🚀 실행 방법

### 로컬 실행
```bash
pip install -r requirements.txt   # streamlit, plotly, pandas, numpy, reportlab, kaleido
streamlit run app.py
```
브라우저에서 `http://localhost:8501` 접속.

> **PDF 리포트 의존성** — `reportlab`(필수, 텍스트/표 PDF) + `kaleido==0.2.1`(선택, 차트 PNG 임베드).
> 둘 다 미설치라도 앱은 정상 작동 (PDF 섹션만 안내 메시지로 표시). Streamlit Cloud는 `requirements.txt`로 자동 설치.

### Streamlit Cloud 배포
1. 본 repo를 GitHub에 push (`data/ccus_metrics.json`, `pdf_report.py`, `requirements.txt` 모두 포함)
2. https://share.streamlit.io 접속, GitHub 연동
3. New app → repo 선택 → Main file path: `app.py`
4. Deploy → 헤더 인디케이터 `📦 LIT data: data/ccus_metrics.json v1.0` 확인 (SSOT 정상 로드)

---

## 📐 지표 정의

```
We     [GJe/tCO₂] = We_thermal(Carnot×0.55) + 펌프 + 압축 + 냉동기 + 보조
SPECCA [MJ/tCO₂]  = (SRD × 500 + We_elec × 2,500) / capture_rate
LCOC   [USD/tCO₂] = (연환산 CAPEX + OPEX) / 연 포집량      ← 포집 기준 (업계 COCA = 회피 기준과 다름)
OPEX              = 용매 + 기타 + 전력 + 재생 열(SRD × 열 단가) + T&S
Net LCOC          = LCOC − 균등화 매출/t (보조금 지급 기간 반영)
Net CO₂ 톤당 비용  = LCOC ÷ (포집 1 t당 실제 감축량, LCA 차감 후)

CAPEX 적용 순서:
  LIT base × CPI × 업종 × 지역 건설비 계수 × project type × 포집율 × 규모(0.65, 계열당) × CCU adder

Carnot η = (T_regen − T_cool) / T_regen × 0.55  (second-law factor, Bejan/Kotas)
CRF      = i(1+i)ⁿ / [(1+i)ⁿ − 1]                (NETL QGESS)
```

---

## 📚 데이터 출처 (요약)

- **NETL** Rev4a, 2022 Baseline B11B/B12B/B31B, QGESS Methodology
- **IEAGHG** 2007 Post-Comb, 2011 Retrofit, 2013 Solvent R&D, 2013 Cement, 2014 Solvents, 2019 Beyond 90%
- **IRS** Section 45Q (IRA 2022 · OBBBA 2025): $85/t 포인트소스(저장·EOR·활용 동일), $180/t DAC, 12년
- **EIA** STEO · **Eurostat** · **KEPCO** · **KOGAS** (지역별 전기·가스 단가) · **AACE** 18R-97 · **IFRS** IAS 16
- **KRX** K-ETS 거래 데이터 / **ICE** EU ETS Futures
- **NL RVO** SDE++ / **UK BEIS** CCUS CfD
- **KIER** KIERSOL Pilot / **TotalEnergies** 3D Project DMX
- **MHI** KS-21 / **Shell** Cansolv DC-103 / **Aker CC** S26
- **POSCO/한국** 산업 CCS / **Norcem Brevik** 시멘트 CCS
- **IPCC** SR CCS 2005, AR6 WG3 / **Global CCS Institute** Status 2023
- 학술 논문 (Rochelle, Bui, Raynal, Cullinane, Yoo, Abanades, Grasa, Romeo, Lepaumier, Manzolini, Cousins, Sjostrom & Krutka, Hanak, Rubin/CMU)
- 방법론 (Bejan, Kotas, GPSA, Peters & Timmerhaus, EIA AEO, CGA G-6.2, SEMI C3)

전체 70여 개 출처는 앱 내 **⑤ 근거·사용법 › 참고문헌**에서 카테고리별로 확인 가능.

---

## 📦 데이터 아키텍처 (Single Source of Truth)

LIT 수치 (SRD·CAPEX·OPEX·손실 등)는 **`data/ccus_metrics.json`** (schema v1.0) 한 파일에서 마스터 관리.
본 도구와 자매 도구 ([🛡️ EU CBAM 계산기](#-related-links))가 동일 JSON을 참조 → 한 곳만 수정해도 양쪽 자동 동기화.

```
ccus_benchmark repo (master)
└── data/ccus_metrics.json     ← 9 technologies, schema v1.0
    │
    ├── ccus_benchmark/app.py        loads (1h cache)
    └── cbam_calculator/app.py       fetches via raw GitHub URL (24h cache)
                                      → ccus_metrics_loader.py
```

**갱신 시 체크리스트**
1. `data/ccus_metrics.json` 한 곳만 수정
2. `last_updated` 날짜, 필요시 `schema_version` bump
3. commit → push → 24시간 내 자매 도구도 자동 반영
4. 두 도구 헤더의 `📦 LIT data: data/ccus_metrics.json v{schema}` 인디케이터로 동기화 확인

---

## ⚠️ 주의사항

- 본 툴의 수치는 공개 보고서 기반 *representative values*. 실제 프로젝트는 EPC 견적·실증 데이터로 보정 필요.
- Tier C(†) 데이터는 상용 스케일에서 ±25% 이상 변동 가능.
- 실측 검증상 모델 CAPEX는 실제 아민 플랜트의 약 1.4~1.7배, 소규모 시멘트 retrofit은 수 배 높게 나옴 — 소규모·산업 retrofit 결과는 특히 보수적으로 해석.
- 정책/시장 단가는 변동성 高. 의사결정 시 최신 데이터로 갱신 필수.

---

## 📜 License

MIT License — 자유롭게 사용·수정·배포 가능, 단 **저작자 표기 필수**.
인용 시: `Song, B. K. (2026). CO₂ 포집·CCUS 기술·경제성 벤치마크. https://github.com/cafeon90-oss`

자세한 내용: [LICENSE](./LICENSE) 파일 참조.

---

## 🔗 Related Links

### 자매 프로젝트 (Single Source of Truth 연계)
- 🛡️ **EU CBAM 계산기** — 한국 산업의 CBAM 영향 분석 (시멘트·철강·알루미늄·H₂·전력)
  - 동일한 10개 CCUS 기술 데이터를 본 도구의 `data/ccus_metrics.json`에서 fetch
  - 별도 repo: `github.com/cafeon90-oss/cbam_calculator` (자매 코드)
  - Loader 모듈: `ccus_metrics_loader.py` (24h GitHub raw URL 캐시)

### 저자
- 작성자 블로그 (CDR/CCUS 분석): https://cdrmaster.tistory.com/
- 작성자 LinkedIn: https://www.linkedin.com/in/bongkwan-song-95a0213ba/
- GitHub: https://github.com/cafeon90-oss

작성자에게 직접 문의·협업 제안: cafeon90@gmail.com
