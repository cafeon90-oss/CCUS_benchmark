"""
비아민계 CO₂ 포집 흡수제 기술 벤치마크 Streamlit 앱
=====================================================

비교 기술 (5종 + MEA 기준):
  0. MEA 30wt% (Baseline 비교용)
  1. K₂CO₃ 계열 (Hot Carbonate / KIERSOL)
  2. 냉각 암모니아 공정 (CAP) — NETL Rev4a B12C
  3. 이중상 용매 (Biphasic / DMX™)
  4. 고체 흡착제 TSA
  5. 칼슘 루핑 (CaL)

데이터 소스:
  - NETL Rev4a Case B12C (Chilled Ammonia 공식 케이스)
  - IEAGHG Technical Reports (Calcium Looping, Biphasic 솔벤트)
  - DOE NETL 고체흡착제 R&D 보고서
  - KIER KIERSOL 파일럿 실증 보고서

지표 정의 (사용자 정의식, 아민 툴과 동일 기준):
  We     [GJe/tCO₂]  = We_thermal(Carnot) + We_elec(펌프·압축·냉동기·보조)
  SPECCA [MJ/tCO₂]   = (SRD×500 + We_elec×2500) / capture
  COCA   [USD/tCO₂]  = (연간 CAPEX + OPEX) / 연간 CO₂ 포집량

실행:
  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# ======================================================================
# 페이지 설정 & 다크모드 / 모바일 CSS
# ======================================================================
st.set_page_config(
    page_title="비아민계 CO₂ 포집 벤치마크",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit 다크모드 강제 (config.toml 대용)
st.markdown(
    """
<style>
    /* 사이드바 완전 불투명 (모바일 투명도 이슈) */
    section[data-testid="stSidebar"] {
        background-color: #0E1117 !important;
        opacity: 1 !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        background-color: #0E1117 !important;
    }
    section[data-testid="stSidebar"] * {
        background-color: transparent;
    }

    /* 탭 가로 스크롤 (모바일) */
    div[data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        scrollbar-width: thin;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar { height: 4px; }
    div[data-baseweb="tab-list"]::-webkit-scrollbar-thumb { background: #4a5160; border-radius: 2px; }
    div[data-baseweb="tab-list"] button { flex-shrink: 0 !important; white-space: nowrap; }

    /* 메트릭 카드 (3단계 축소) */
    div[data-testid="stMetric"] {
        background-color: #1E2128;
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid #2C313C;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        color: #8b95a7;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.0rem !important;
        font-weight: 600;
        line-height: 1.2;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.7rem !important;
    }

    /* 파일럿 경고 배너 */
    .pilot-warning {
        background: linear-gradient(90deg, #4a3500 0%, #3a2900 100%);
        border-left: 4px solid #ffc107;
        padding: 10px 14px;
        margin: 10px 0;
        border-radius: 4px;
        color: #ffe082;
        font-size: 0.9rem;
    }
    .pilot-warning strong { color: #ffd54f; }

    /* 본문 표 헤더 */
    .stDataFrame thead th { background-color: #1E2128 !important; }

    /* 모바일 폰트 축소 */
    @media (max-width: 640px) {
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.1rem !important; }
        div[data-testid="stMetricValue"] { font-size: 0.9rem !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.65rem !important; }
    }

    /* 모바일 터치 시 그래프 줌/팬 방지 — 페이지 세로 스크롤만 허용 */
    @media (pointer: coarse) {
        .js-plotly-plot, .plotly, .plot-container, .main-svg {
            touch-action: pan-y !important;
        }
    }

    /* 사이드바 multiselect 칩 — 글자 잘림만 방지 (단순) */
    section[data-testid="stSidebar"] [data-baseweb="tag"] {
        max-width: 100% !important;
        height: auto !important;
        margin: 2px 2px !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="tag"] > div {
        white-space: normal !important;
        word-break: break-word !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.3 !important;
    }

    /* 데스크톱에서 사이드바 폭 확대 — 풀네임 한 줄에 들어가게 */
    @media (min-width: 768px) {
        section[data-testid="stSidebar"] {
            min-width: 340px !important;
            width: 340px !important;
        }
        section[data-testid="stSidebar"] > div {
            min-width: 340px !important;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================
# 상수 (사용자식 그대로)
# ======================================================================
SRD_TO_SPECCA = 500     # SPECCA 식 가중치 (사용자 정의)
WE_TO_SPECCA = 2500     # SPECCA 식 가중치 (사용자 정의)
GJ_PER_KWH = 3.6e-3     # GJ/kWh
HOURS_YR = 8760
CF_DEFAULT = 0.85       # capacity factor

# Carnot 보정 (실제 열기관 효율은 Carnot의 ~50~60%)
ETA_CARNOT_FRAC = 0.55  # second-law efficiency

# 단위 환산
USD_PER_MWH_GRID = 80   # 보조전력의 가치 (kWh 가격 환산용)

# ──────────────────────────────────────────────────────────
# CCS 특화 스케일링 (IEAGHG / NETL 벤치마크 기반)
# 일반 화공의 Lang's rule이 아니라 CCS plant-specific 데이터
# ──────────────────────────────────────────────────────────
REF_CAPTURE_MT_YR = 3.7         # NETL B12C/B12B 기준 규모

# CAPEX scaling (IEAGHG 2007, NETL QGESS — CCS 표준)
CAPEX_SCALE_EXPONENT = 0.65     # CCS 플랜트 평균 (일반 화공 0.7보다 낮음)

# SRD scaling (IEAGHG 2013/04 Solvent R&D Priorities)
# 큰 플랜트일수록 실운영 조건의 SRD ↑ (열손실, 열통합 한계, integration penalty)
SRD_SCALE_PER_DECADE = 0.10     # ±10% per decade of scale (10× → +10%)
SRD_CLIP = (0.85, 1.20)          # 범위 제한

# We_comp scaling (NETL Rev4, IEAGHG 2014)
# 압축기 효율: 소형 왕복식(η~75%) → 대형 다단 원심(η~85%)
# 큰 플랜트일수록 We_comp ↓ (높은 효율)
WE_COMP_SCALE_PER_DECADE = 0.06  # ±6% per decade
WE_COMP_CLIP = (0.85, 1.20)

# ======================================================================
# 기술 라이브러리 (LIT) — NETL Rev4a / IEAGHG / DOE / KIER 기반
# ======================================================================
LIT = {
    "MEA_baseline": {
        "name": "MEA 30 wt% (참고)",
        "category": "Amine (ref)",
        "source": "NETL B12B / IEAGHG 2014",
        "status": "commercial",
        "SRD": 3.60,
        "T_regen": 120,
        "T_abs": 40,
        "p_regen_bar": 1.8,
        "We_pump": 0.012,
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.05,
        "CAPEX_per_t": 950,
        "OPEX_solvent": 1.5,
        "OPEX_other": 12.0,
        "loss_kg_per_tCO2": 1.5,
        "loss_mech": "산화·열분해 (degradation)",
        "is_pilot": False,
        "notes": "30 wt% MEA + reclaimer. 비교 기준선.",
    },
    "K2CO3_KIERSOL": {
        "name": "K₂CO₃ / KIERSOL †",
        "category": "Hot Carbonate",
        "source": "KIER KIERSOL 파일럿 (Korea)",
        "status": "pilot",
        "SRD": 2.95,
        "T_regen": 105,
        "T_abs": 70,
        "p_regen_bar": 1.5,
        "We_pump": 0.025,
        "We_comp": 0.38,
        "We_chill": 0.00,
        "We_aux": 0.06,
        "CAPEX_per_t": 1050,
        "OPEX_solvent": 0.8,
        "OPEX_other": 11.0,
        "loss_kg_per_tCO2": 0.5,
        "loss_mech": "촉진제 열화·미량 분해",
        "is_pilot": True,
        "notes": "KIER KIERSOL 파일럿. K₂CO₃ + 활성화제. SRD 이론 유리, 반응 느려 L/G 大.",
    },
    "CAP_B12C": {
        "name": "Chilled Ammonia (CAP)",
        "category": "Chilled NH₃",
        "source": "NETL Rev4a Case B12C",
        "status": "demo",
        "SRD": 2.40,
        "T_regen": 150,
        "T_abs": 5,
        "p_regen_bar": 24.0,
        "We_pump": 0.018,
        "We_comp": 0.18,
        "We_chill": 0.18,
        "We_aux": 0.05,
        "CAPEX_per_t": 1200,
        "OPEX_solvent": 0.6,
        "OPEX_other": 13.0,
        "loss_kg_per_tCO2": 0.3,
        "loss_mech": "NH₃ slip (water wash 회수)",
        "is_pilot": False,
        "notes": "흡수탑 0~10 °C 냉각. 가압 재생 → CO₂ 압축 부하 절감. NETL B12C 공식 케이스.",
    },
    "Biphasic_DMX": {
        "name": "Biphasic DMX™ †",
        "category": "Biphasic",
        "source": "TotalEnergies / IFP-EN / 3D Project",
        "status": "pilot",
        "SRD": 2.30,
        "T_regen": 155,
        "T_abs": 40,
        "p_regen_bar": 1.8,
        "We_pump": 0.020,
        "We_comp": 0.36,
        "We_chill": 0.00,
        "We_aux": 0.05,
        "CAPEX_per_t": 1100,
        "OPEX_solvent": 1.8,
        "OPEX_other": 12.0,
        "loss_kg_per_tCO2": 1.0,
        "loss_mech": "용매 분해·휘발",
        "is_pilot": True,
        "notes": "상분리 후 CO₂ 농후상만 재생 → 재생 유량 ½. SRD 보정계수 ≈ 0.7 적용.",
    },
    "TSA_Solid": {
        "name": "Solid Sorbent TSA",
        "category": "Solid Sorbent",
        "source": "DOE NETL R&D / SRI / RTI",
        "status": "demo",
        "SRD": 2.20,
        "T_regen": 110,
        "T_abs": 40,
        "p_regen_bar": 1.2,
        "We_pump": 0.005,
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.10,
        "CAPEX_per_t": 1300,
        "OPEX_solvent": 2.5,
        "OPEX_other": 10.0,
        "loss_kg_per_tCO2": 2.0,
        "loss_mech": "사이클 열화·마모 (attrition)",
        "is_pilot": False,
        "notes": "고체 흡착제, 무수계, 사이클 시간 변수 영향 大. 분산형 소규모에 유리.",
    },
    "CaL": {
        "name": "Calcium Looping (CaL)",
        "category": "CaO/CaCO₃",
        "source": "IEAGHG 2013/14 CaL Report",
        "status": "demo",
        "SRD": 3.20,
        "T_regen": 900,
        "T_abs": 650,
        "p_regen_bar": 1.0,
        "We_pump": 0.000,
        "We_comp": 0.36,
        "We_chill": 0.00,
        "We_aux": 0.15,
        "CAPEX_per_t": 850,
        "OPEX_solvent": 1.5,
        "OPEX_other": 14.0,
        "loss_kg_per_tCO2": 30.0,
        "loss_mech": "다회 사이클 비활성화 (CaO sintering)",
        "is_pilot": False,
        "notes": "650/900 °C 고온 순환. 시멘트 산업 통합 가능. ASU 포함 oxy-calcination.",
    },
}

TECH_KEYS = list(LIT.keys())

# ======================================================================
# 레퍼런스 통합 라이브러리 (REFS)
# ======================================================================
REFS = {
    "NETL_Rev4a": {
        "cat": "report",
        "cite": "DOE/NETL (2019). Cost and Performance Baseline for Fossil Energy Plants, "
                "Vol. 1: Bituminous Coal & Natural Gas to Electricity, Rev. 4a. "
                "DOE/NETL-2015/1723. Cases B11A/B11B (NGCC), B12A/B12B (Subcritical PC + MEA), "
                "B12C (Subcritical PC + Chilled Ammonia).",
        "url": "https://netl.doe.gov/projects/files/CostAndPerformanceBaselineForFossilEnergyPlantsVolume1BituminousCoalAndNaturalGasToElectricity.pdf",
        "used_for": "CAP SRD 2.4 GJ/t, 보조전력 분해, COE/COC, MEA baseline",
    },
    "NETL_QGESS": {
        "cat": "report",
        "cite": "DOE/NETL (2021). Quality Guidelines for Energy System Studies (QGESS): "
                "Cost Estimation Methodology for NETL Assessments of Power Plant Performance. "
                "DOE/NETL-2019/2080.",
        "url": "https://netl.doe.gov/energy-analysis/details?id=2710",
        "used_for": "CRF 공식, 할인율 8%, 수명 25년, TPC→COE 변환",
    },
    "IEAGHG_CaL_2013": {
        "cat": "report",
        "cite": "IEAGHG (2013). Deployment of CCS in the Cement Industry. Calcium Looping "
                "Technology Status. Report 2013/19.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "CaL SRD 3.2 GJ/t, makeup limestone 30 kg/tCO₂, calciner 900 °C",
    },
    "IEAGHG_Solvents_2014": {
        "cat": "report",
        "cite": "IEAGHG (2014). Evaluation of Reclaimer Sludge Disposal from Post-Combustion "
                "CO₂ Capture. Report 2014/02.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "MEA reclaimer/loss, 솔벤트 분해 메커니즘",
    },
    "DOE_NETL_Sorbent_Program": {
        "cat": "report",
        "cite": "DOE/NETL Carbon Capture Program (2018). Solid Sorbent Process Designs "
                "for CO₂ Capture from Coal-Fired Power Plants. NETL Carbon Capture R&D.",
        "url": "https://netl.doe.gov/coal/carbon-capture",
        "used_for": "TSA SRD 2.2 GJ/t, attrition rate, blower fluidization 부하",
    },
    "KIER_KIERSOL_2013": {
        "cat": "report",
        "cite": "KIER 한국에너지기술연구원 (2013-2018). KIERSOL 흡수제 파일럿 실증 보고서. "
                "K₂CO₃ 기반 + 활성화제 (Cesar). 0.5 MWe 파일럿.",
        "url": "https://www.kier.re.kr/",
        "used_for": "KIERSOL SRD 2.95 GJ/t, 70 °C 흡수, 활성화제 손실",
    },
    "TotalEnergies_3D": {
        "cat": "report",
        "cite": "3D Project Consortium (2017-2023). DMX™ Demonstration in Dunkirk. "
                "H2020 Grant 838031. TotalEnergies / IFP Energies Nouvelles.",
        "url": "https://www.3d-ccus.com/",
        "used_for": "Biphasic DMX SRD 2.3 GJ/t, 상분리 후 ½ 재생",
    },
    "Rochelle2009": {
        "cat": "paper",
        "cite": "Rochelle, G. T. (2009). Amine Scrubbing for CO₂ Capture. Science, 325(5948), 1652-1654.",
        "url": "https://www.science.org/doi/10.1126/science.1176731",
        "used_for": "MEA SRD 3.6 GJ/t 기준, 솔벤트 화학",
    },
    "Bui2018": {
        "cat": "paper",
        "cite": "Bui, M. et al. (2018). Carbon capture and storage (CCS): the way forward. "
                "Energy & Environmental Science, 11(5), 1062-1176.",
        "url": "https://pubs.rsc.org/en/content/articlehtml/2018/ee/c7ee02342a",
        "used_for": "전기술 SRD 비교 범위, COCA 통합 리뷰",
    },
    "Darde2010": {
        "cat": "paper",
        "cite": "Darde, V., Thomsen, K., van Well, W. J. M., Stenby, E. H. (2010). "
                "Chilled ammonia process for CO₂ capture. International Journal of Greenhouse "
                "Gas Control, 4(2), 131-136.",
        "url": "https://doi.org/10.1016/j.ijggc.2009.10.005",
        "used_for": "CAP SRD 2.0~2.4 범위, 흡수탑 0~10 °C, NH₃ slip",
    },
    "Telikapalli2011": {
        "cat": "paper",
        "cite": "Telikapalli, V., Kozak, F., Francuz, J., Sherrick, B., Black, J., Muraskin, D., "
                "Cage, M., Hammond, M., Spitznogle, G. (2011). CCS with the Alstom Chilled "
                "Ammonia Process Development Program — Field Pilot Results. Energy Procedia, 4, 273-281.",
        "url": "https://doi.org/10.1016/j.egypro.2011.01.052",
        "used_for": "Alstom (현 GE) CAP 파일럿 실증값",
    },
    "Raynal2011": {
        "cat": "paper",
        "cite": "Raynal, L., Bouillon, P. A., Gomez, A., Broutin, P. (2011). From MEA to "
                "demixing solvents and future steps, a roadmap for lowering the cost of "
                "post-combustion carbon capture. Chemical Engineering Journal, 171(3), 742-752.",
        "url": "https://doi.org/10.1016/j.cej.2011.01.008",
        "used_for": "Biphasic DMX 컨셉, SRD 보정계수 0.7",
    },
    "Cullinane2004": {
        "cat": "paper",
        "cite": "Cullinane, J. T., Rochelle, G. T. (2004). Carbon dioxide absorption with aqueous "
                "potassium carbonate promoted by piperazine. Chemical Engineering Science, 59(17), 3619-3630.",
        "url": "https://doi.org/10.1016/j.ces.2004.03.029",
        "used_for": "K₂CO₃ + 활성화제 (PZ) 화학, 반응속도 보완",
    },
    "Yoo2013": {
        "cat": "paper",
        "cite": "Yoo, M. et al. (KIER) (2013). Development of carbon dioxide absorbents for "
                "power plant flue gas. Korean J. Chem. Eng., 30(7), 1497-1503.",
        "url": "https://doi.org/10.1007/s11814-013-0060-5",
        "used_for": "KIERSOL 흡수제 조성 및 성능",
    },
    "Abanades2002": {
        "cat": "paper",
        "cite": "Abanades, J. C. (2002). The maximum capture efficiency of CO₂ using a "
                "carbonation/calcination cycle of CaO/CaCO₃. Chemical Engineering Journal, 90(3), 303-306.",
        "url": "https://doi.org/10.1016/S1385-8947(02)00126-2",
        "used_for": "CaL 사이클 효율, CaO sintering 모델",
    },
    "Grasa2006": {
        "cat": "paper",
        "cite": "Grasa, G. S., Abanades, J. C. (2006). CO₂ capture capacity of CaO in long "
                "series of carbonation/calcination cycles. Industrial & Engineering Chemistry "
                "Research, 45(26), 8846-8851.",
        "url": "https://doi.org/10.1021/ie0606946",
        "used_for": "CaL 비활성화 곡선, makeup limestone 비율",
    },
    "Romeo2008": {
        "cat": "paper",
        "cite": "Romeo, L. M., Abanades, J. C., Escosa, J. M., Paño, J., Giménez, A., "
                "Sánchez-Biezma, A., Ballesteros, J. C. (2008). Oxyfuel carbonation/calcination "
                "cycle for low cost CO₂ capture in existing power plants. "
                "Energy Conversion and Management, 49(10), 2809-2814.",
        "url": "https://doi.org/10.1016/j.enconman.2008.03.022",
        "used_for": "CaL CAPEX, 압축 log-scaling 모델",
    },
    "Lepaumier2009": {
        "cat": "paper",
        "cite": "Lepaumier, H., Picq, D., Carrette, P. L. (2009). New amines for CO₂ capture. "
                "II. Oxidative degradation mechanisms. Industrial & Engineering Chemistry "
                "Research, 48(20), 9068-9075.",
        "url": "https://doi.org/10.1021/ie9004749",
        "used_for": "MEA 1.5 kg/tCO₂ 손실, 산화·열분해 메커니즘",
    },
    "Manzolini2015": {
        "cat": "paper",
        "cite": "Manzolini, G., Macchi, E., Gazzani, M. (2015). CO₂ capture in Integrated "
                "Gasification Combined Cycle with SEWGS — Part B: Economic assessment. Fuel, 161, 209-218.",
        "url": "https://doi.org/10.1016/j.fuel.2015.07.062",
        "used_for": "SPECCA 표준 정의 (literature 비교용)",
    },
    "Bejan2016": {
        "cat": "methodology",
        "cite": "Bejan, A. (2016). Advanced Engineering Thermodynamics, 4th ed. Wiley. "
                "Carnot 효율, 2nd-law efficiency 개념.",
        "url": "https://doi.org/10.1002/9781119245964",
        "used_for": "Carnot η = (T_h-T_c)/T_h, second-law factor",
    },
    "Kotas1985": {
        "cat": "methodology",
        "cite": "Kotas, T. J. (1985). The Exergy Method of Thermal Plant Analysis. "
                "Butterworths. Real-process exergy efficiency typically 40-65% of Carnot.",
        "url": "",
        "used_for": "ETA_CARNOT_FRAC = 0.55 가정 근거",
    },
    "ASHRAE_HVAC": {
        "cat": "methodology",
        "cite": "ASHRAE Handbook — HVAC Systems and Equipment (2020). Chapter on Refrigeration. "
                "Real chiller COP ≈ 0.5-0.6 × inverse-Carnot COP.",
        "url": "https://www.ashrae.org/technical-resources/ashrae-handbook",
        "used_for": "CAP 냉동기 COP_eff = COP_Carnot × 0.55",
    },
    "EIA_AEO_2024": {
        "cat": "methodology",
        "cite": "U.S. Energy Information Administration (2024). Annual Energy Outlook 2024. "
                "Industrial electricity price ~$80/MWh average.",
        "url": "https://www.eia.gov/outlooks/aeo/",
        "used_for": "전기 가격 default 80 USD/MWh",
    },
    "Aspen_NETL": {
        "cat": "methodology",
        "cite": "DOE/NETL (2014). Compression of CO₂ in Carbon Capture & Storage Applications. "
                "Aspen Plus 모델 기반 다단 압축 일.",
        "url": "https://netl.doe.gov/",
        "used_for": "압축 W ∝ log(p_out/p_in) 근사식 (5단 압축 + 중간냉각 가정)",
    },
    "KRX_KAU_2024": {
        "cat": "report",
        "cite": "한국거래소 KRX (2024). 배출권 시장 운영 통계, KAU 시세. "
                "2024년 평균 9,500~10,500 KRW/tCO₂.",
        "url": "https://ets.krx.co.kr/",
        "used_for": "K-ETS default 단가 ($7/t)",
    },
    "ICE_EUA_2024": {
        "cat": "report",
        "cite": "Intercontinental Exchange (ICE) EUA Futures (2024). EU ETS 배출권 시세. "
                "2024년 평균 €70~80/tCO₂.",
        "url": "https://www.ice.com/products/197/EUA-Futures",
        "used_for": "EU ETS default 단가 ($80/t)",
    },
    "IRS_45Q_IRA": {
        "cat": "report",
        "cite": "IRS Notice 2022-38; Inflation Reduction Act 2022, Section 13104. "
                "Section 45Q tax credit: $85/t (CCS), $60/t (EOR/CCU), $180/t (DAC+CCS), "
                "$130/t (DAC+CCU). 12-year credit period.",
        "url": "https://www.irs.gov/credits-deductions/credit-for-carbon-oxide-sequestration",
        "used_for": "US 45Q 보조금 단가 ($85/$60/$180/$130/t)",
    },
    "NL_SDE_2024": {
        "cat": "report",
        "cite": "RVO Netherlands (2024). SDE++ 2024 Round Results. "
                "Stimulering Duurzame Energieproductie en Klimaattransitie. "
                "CCS strike price €100~130/tCO₂.",
        "url": "https://www.rvo.nl/subsidies-financiering/sde",
        "used_for": "NL SDE++ default 단가 ($120/t)",
    },
    "UK_CCUS_BEIS": {
        "cat": "report",
        "cite": "UK BEIS (2023). CCUS Cluster Sequencing — Track 1 & 2 Outcomes. "
                "Industrial CCS DRI/CfD £100~200/tCO₂. £20B 할당.",
        "url": "https://www.gov.uk/government/publications/cluster-sequencing-for-carbon-capture-usage-and-storage-ccus-deployment-phase-1-expressions-of-interest",
        "used_for": "UK CfD default ($180/t)",
    },
    "K_CCUS_Act_2024": {
        "cat": "report",
        "cite": "산업통상자원부 (2024). 「이산화탄소 포집·활용·저장에 관한 법률」 제정. "
                "2024.2 공포, 2024.8 시행. 단가 시행령 미발표.",
        "url": "https://www.motie.go.kr/",
        "used_for": "Korea CCUS Act placeholder (30,000 KRW/t 추정)",
    },
    "IPCC_SR_CCS_2005": {
        "cat": "report",
        "cite": "IPCC (2005). Special Report on Carbon Dioxide Capture and Storage. "
                "Cambridge University Press. CCS chain yield 90~95%.",
        "url": "https://www.ipcc.ch/report/carbon-dioxide-capture-and-storage/",
        "used_for": "CCS 격리수율 92% default, 손실 분해",
    },
    "GCCSI_2023": {
        "cat": "report",
        "cite": "Global CCS Institute (2023). Global Status of CCS 2023. "
                "운영 중 CCS 시설 yield 데이터.",
        "url": "https://www.globalccsinstitute.com/resources/global-status-report/",
        "used_for": "CCS chain yield 검증, CCS:CCU split 통계",
    },
    "CGA_G62_2018": {
        "cat": "methodology",
        "cite": "Compressed Gas Association (CGA) G-6.2 (2018). Commodity Specification for "
                "Carbon Dioxide. Grade A~T 순도 분류 (99.5%~99.9999%).",
        "url": "https://www.cganet.com/",
        "used_for": "CCU 식품·고순도 등급 분류 기준",
    },
    "SEMI_C3": {
        "cat": "methodology",
        "cite": "SEMI C3 (Standard for Carbon Dioxide). Semiconductor 등급 99.999% 이상 사양.",
        "url": "https://www.semi.org/en/standards",
        "used_for": "CCU 초고순도 (99.999%) 사양",
    },
    "Linde_AirLiquide_LCO2": {
        "cat": "report",
        "cite": "Linde / Air Liquide (2020-2023). Industrial CO₂ market data and pricing. "
                "Korea food-grade LCO₂ 250,000~400,000 KRW/t.",
        "url": "",
        "used_for": "CCU 액화탄산 default 가격 (300,000 KRW/t food-grade)",
    },
    "PetersTimmerhaus": {
        "cat": "methodology",
        "cite": "Peters, M. S., Timmerhaus, K. D., West, R. E. (2003). Plant Design and "
                "Economics for Chemical Engineers, 5th ed. McGraw-Hill. "
                "Six-tenths rule (n≈0.6~0.7) for CAPEX scaling.",
        "url": "",
        "used_for": "규모의 경제 일반 화공 표준",
    },
    # ────────────── CCS 특화 스케일링 출처 ──────────────
    "IEAGHG_2007_PostComb": {
        "cat": "report",
        "cite": "IEAGHG (2007). Improvement in Power Generation with Post-Combustion "
                "Capture of CO₂. Report 2004/4 (Updated 2007). "
                "CCS plant CAPEX scaling exponent ≈ 0.65.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "CAPEX 스케일링 n=0.65 (CCS 표준)",
    },
    "IEAGHG_2013_SolventRD": {
        "cat": "report",
        "cite": "IEAGHG (2013). Evaluation of Post-Combustion CO₂ Capture Solvent R&D "
                "Priorities. Report 2013/06. SRD penalty scaling: pilot → commercial "
                "+10~15% due to heat loss, integration limits, real-world penalties.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "SRD 규모 보정 (±10%/decade)",
    },
    "IEAGHG_2014_Solvents": {
        "cat": "report",
        "cite": "IEAGHG (2014). Assessment of Emerging CO₂ Capture Technologies and Their "
                "Potential to Reduce Costs. Report 2014/TR4. Compressor efficiency scaling.",
        "url": "https://ieaghg.org/publications/technical-reports",
        "used_for": "We_comp 규모 보정 (±6%/decade)",
    },
    "NETL_2022_Baseline": {
        "cat": "report",
        "cite": "DOE/NETL (2022). Cost and Performance Baseline for Fossil Energy Plants — "
                "Cases B11B (SubC PC), B12B (SC PC), B31B (NGCC) with Cansolv DC-103. "
                "DOE/NETL-2023/4320. October 2022. SRD: 3.38~3.56 GJ/tCO₂.",
        "url": "https://netl.doe.gov/energy-analysis/details?id=a8e92d29-b73f-4d80-8b8d-97c1e5654e84",
        "used_for": "최신 commercial-scale CCS 벤치마크 (Cansolv DC-103)",
    },
    "NETL_Rev3_2015": {
        "cat": "report",
        "cite": "DOE/NETL (2015, updated). Cost and Performance Baseline for Fossil Energy "
                "Plants, Revision 3. DOE/NETL-2010/1397. Cansolv DC-103 SRD ≈ 2.56 GJ/tCO₂.",
        "url": "https://netl.doe.gov/projects/files/Rev3FinalReport.pdf",
        "used_for": "Cansolv 솔벤트 SRD 진화 (Rev3)",
    },
    "GPSA_2017": {
        "cat": "methodology",
        "cite": "GPSA (Gas Processors Suppliers Association) (2017). Engineering Data Book, "
                "14th ed. Section 13: Compressors and Expanders. Industry-standard "
                "compressor efficiency curves.",
        "url": "https://gpsamidstreamsuppliers.org/databook",
        "used_for": "압축기 효율 (소형 왕복식 75% → 대형 다단 원심 85%) 표준",
    },
    "IPCC_AR6_WG3_2022": {
        "cat": "report",
        "cite": "IPCC (2022). Climate Change 2022: Mitigation of Climate Change. "
                "Contribution of WG III to the Sixth Assessment Report. Chapter 6, 11 — "
                "CCS/CCU role in 1.5/2°C pathways.",
        "url": "https://www.ipcc.ch/report/ar6/wg3/",
        "used_for": "Climate context, 2050 net-zero CCS deployment scenarios",
    },
    "IEA_CCUS_2023": {
        "cat": "report",
        "cite": "IEA (2023). CCUS Projects Database / CCUS Tracking Report. "
                "Global pipeline ~700 projects, ~400 MtCO₂/yr by 2030.",
        "url": "https://www.iea.org/reports/ccus-in-clean-energy-transitions",
        "used_for": "글로벌 CCUS 동향, 프로젝트 규모 분포",
    },
    "POSCO_KoreanCCS": {
        "cat": "report",
        "cite": "POSCO E&C (2020-2023). 한국 산업 CCS 사례 — 동해가스전 CO₂ 저장 (2030 계획), "
                "현대제철·삼성전자 CCUS 도입 검토.",
        "url": "",
        "used_for": "한국 산업 CCS 적용 맥락 (동해가스전, 시멘트·철강·반도체)",
    },
    "IPCC_SRCCS_Ch5": {
        "cat": "report",
        "cite": "IPCC (2005). Special Report on Carbon Dioxide Capture and Storage, "
                "Chapter 5: Underground Geological Storage. Storage chain loss breakdown: "
                "dehydration -0.5%, compression -1%, pipeline -1.5%, injection -1%.",
        "url": "https://www.ipcc.ch/site/assets/uploads/2018/03/srccs_chapter5-1.pdf",
        "used_for": "CCS 격리 수율 92% 분해 근거 (단계별 손실)",
    },
    "Sjostrom_Krutka_2010": {
        "cat": "paper",
        "cite": "Sjostrom, S., Krutka, H. (2010). Evaluation of solid sorbents as a retrofit "
                "technology for CO₂ capture. Fuel, 89(6), 1298-1306.",
        "url": "https://doi.org/10.1016/j.fuel.2009.11.019",
        "used_for": "TSA solid sorbent attrition rate, cycle stability",
    },
    "Hanak_2015": {
        "cat": "paper",
        "cite": "Hanak, D. P., Anthony, E. J., Manovic, V. (2015). A review of developments "
                "in pilot-plant testing and modelling of calcium looping process. "
                "Energy Environ. Sci., 8(8), 2199-2249.",
        "url": "https://doi.org/10.1039/C5EE01228G",
        "used_for": "CaL 종합 리뷰 (CAPEX, 운전 데이터)",
    },
    "Cousins_2011": {
        "cat": "paper",
        "cite": "Cousins, A., Wardhaugh, L. T., Feron, P. H. M. (2011). A survey of process "
                "flow sheet modifications for energy efficient CO₂ capture from flue gases. "
                "International Journal of Greenhouse Gas Control, 5(4), 605-619.",
        "url": "https://doi.org/10.1016/j.ijggc.2011.01.002",
        "used_for": "MEA 공정 변형 (split flow, intercooling) — SRD 감소 메커니즘",
    },
}


def ref_link(ref_id: str, label: str = None) -> str:
    """REFS의 항목을 마크다운 링크로 변환"""
    if ref_id not in REFS:
        return f"[{ref_id}]"
    r = REFS[ref_id]
    text = label or ref_id
    if r["url"]:
        return f"[{text}]({r['url']})"
    return text


LIT_REFS = {
    "MEA_baseline":    ["NETL_Rev4a", "NETL_2022_Baseline", "Rochelle2009",
                         "IEAGHG_Solvents_2014", "Lepaumier2009", "Bui2018", "Cousins_2011"],
    "K2CO3_KIERSOL":   ["KIER_KIERSOL_2013", "Yoo2013", "Cullinane2004"],
    "CAP_B12C":        ["NETL_Rev4a", "Darde2010", "Telikapalli2011"],
    "Biphasic_DMX":    ["TotalEnergies_3D", "Raynal2011"],
    "TSA_Solid":       ["DOE_NETL_Sorbent_Program", "Sjostrom_Krutka_2010", "Bui2018"],
    "CaL":             ["IEAGHG_CaL_2013", "Abanades2002", "Grasa2006", "Romeo2008", "Hanak_2015"],
}

FORMULA_REFS = {
    "Carnot 효율 η = (T_h - T_c) / T_h":                                              ["Bejan2016"],
    "Second-law factor 0.55":                                                          ["Bejan2016", "Kotas1985"],
    "역카르노 COP = T_c / (T_h - T_c) × 0.55":                                         ["ASHRAE_HVAC"],
    "압축 W ∝ log(p_out / p_in) (5단 + 중간냉각)":                                     ["Aspen_NETL", "Romeo2008"],
    "CRF = i(1+i)^n / [(1+i)^n - 1]":                                                 ["NETL_QGESS"],
    "할인율 8%, 수명 25년 (default)":                                                  ["NETL_QGESS"],
    "전기 가격 80 USD/MWh (default)":                                                   ["EIA_AEO_2024"],
    "SPECCA = (SRD×500 + We_elec×2500) / capture":                                    ["Manzolini2015"],
    "CAP 냉각부하 = SRD × 0.18 휴리스틱":                                               ["NETL_Rev4a", "Darde2010"],
    "CAPEX 규모 효과: ∝ scale^0.65 (CCS specific, ref=3.7 Mt/yr)":                      ["IEAGHG_2007_PostComb", "NETL_QGESS"],
    "SRD 규모 효과: ±10%/decade (파일럿 → 상용 +10%, 메가 +5%)":                         ["IEAGHG_2013_SolventRD"],
    "We_comp 규모 효과: ±6%/decade (소형 왕복식 → 대형 다단 원심)":                       ["IEAGHG_2014_Solvents", "NETL_Rev3_2015"],
}

SHORT_NAMES = {
    "MEA_baseline":   "MEA",
    "K2CO3_KIERSOL":  "K₂CO₃†",
    "CAP_B12C":       "CAP",
    "Biphasic_DMX":   "DMX†",
    "TSA_Solid":      "TSA",
    "CaL":            "CaL",
}

MATERIALS = {
    "MEA_baseline":   "MEA 30 wt% 수용액 (HOCH₂CH₂NH₂)",
    "K2CO3_KIERSOL":  "K₂CO₃ + 활성화제 (Piperazine 등) 수용액",
    "CAP_B12C":       "NH₃ 28 wt% 수용액 (0~10 °C 냉각)",
    "Biphasic_DMX":   "3차 아민 혼합액 (DMX™, 상분리형)",
    "TSA_Solid":      "고체 흡착제 (아민 함침/제올라이트/MOF)",
    "CaL":            "CaO ⇌ CaCO₃ (석회석 기원, 고체)",
}

CCU_GRADES = {
    "food":    {"label": "식품·음료급 (99.9%)",     "purity": 99.9,
                "yield": 0.88, "price_krw_t": 300_000, "capex_mult": 1.05},
    "high":    {"label": "고순도 (99.99%)",         "purity": 99.99,
                "yield": 0.82, "price_krw_t": 450_000, "capex_mult": 1.25},
    "ultra":   {"label": "초고순도 반도체/의료 (99.999%)", "purity": 99.999,
                "yield": 0.75, "price_krw_t": 700_000, "capex_mult": 1.65},
}

CARBON_MARKETS = {
    "K-ETS":      {"label": "🇰🇷 K-ETS (한국)",            "type": "credit",   "price_usd_t": 7.0,   "native": "10,000 KRW/t"},
    "EU-ETS":     {"label": "🇪🇺 EU ETS (유럽)",           "type": "credit",   "price_usd_t": 80.0,  "native": "€75/t"},
    "RGGI":       {"label": "🇺🇸 RGGI (미 동부)",           "type": "credit",   "price_usd_t": 20.0,  "native": "$20/t"},
    "CA-CAT":     {"label": "🇺🇸 CA Cap-Trade (캘리포니아)", "type": "credit",   "price_usd_t": 30.0,  "native": "$30/t"},
    "45Q-CCS":    {"label": "🇺🇸 US 45Q — CCS 지중저장",    "type": "subsidy",  "price_usd_t": 85.0,  "native": "$85/t (12yr)"},
    "45Q-EOR":    {"label": "🇺🇸 US 45Q — CCU/EOR",        "type": "subsidy",  "price_usd_t": 60.0,  "native": "$60/t (12yr)"},
    "NL-SDE":     {"label": "🇳🇱 NL SDE++ (네덜란드)",      "type": "subsidy",  "price_usd_t": 120.0, "native": "€110/t"},
    "UK-CfD":     {"label": "🇬🇧 UK CCUS CfD",              "type": "subsidy",  "price_usd_t": 180.0, "native": "£150/t"},
    "K-CCUS-est": {"label": "🇰🇷 Korea CCUS Act (추정)",   "type": "subsidy",  "price_usd_t": 21.0,  "native": "30,000 KRW/t (placeholder)"},
    "Custom":     {"label": "✏️  Custom 입력",               "type": "credit",   "price_usd_t": 0.0,   "native": "—"},
}

def short_name(key_or_name: str) -> str:
    if key_or_name in SHORT_NAMES:
        return SHORT_NAMES[key_or_name]
    for k, t in LIT.items():
        if t["name"] == key_or_name:
            return SHORT_NAMES.get(k, key_or_name)
    return key_or_name


def fmt_krw_amt(krw: float, sign: bool = False) -> str:
    """
    원화 금액을 한국식 단위로 자동 변환.
      < 1조원      → 억원 (예: 18.6억원, 186억원, 9,500억원)
      ≥ 1조원      → 조원 (예: 1.52조원, 15.20조원)
    sign=True 면 +/- 부호 강제 표시.
    """
    abs_krw = abs(krw)
    if abs_krw >= 1e12:
        val = krw / 1e12
        prec = 2
        unit = "조원"
    else:
        val = krw / 1e8
        # 100억 이상은 정수, 미만은 소수 1자리
        prec = 0 if abs(val) >= 100 else 1
        unit = "억원"
    s = f"{val:+,.{prec}f}" if sign else f"{val:,.{prec}f}"
    return f"{s}{unit}"


def fmt_krw_per_t(krw_per_t: float, sign: bool = False) -> str:
    """단위 CO₂당 원화 (보통 만원~수십만원 단위) — 그냥 원/t 표기 + 천단위 쉼표"""
    s = f"{krw_per_t:+,.0f}" if sign else f"{krw_per_t:,.0f}"
    return f"{s} 원/t"


CHART_MARGIN = dict(l=10, r=10, t=50, b=80)
CHART_MARGIN_STACK = dict(l=10, r=10, t=50, b=120)

# 모바일 친화: 드래그/줌/더블클릭 모두 비활성화 (호버는 유지)
PLOTLY_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
    "displaylogo": False,
    "staticPlot": False,
    "showAxisDragHandles": False,
    "showAxisRangeEntryBoxes": False,
}

# ======================================================================
# 계산 함수
# ======================================================================
def carnot_efficiency(T_hot_C: float, T_cold_C: float) -> float:
    Th = T_hot_C + 273.15
    Tc = T_cold_C + 273.15
    if Th <= Tc:
        return 0.0
    return (Th - Tc) / Th


def chiller_We(Q_chill_GJ: float, T_abs_C: float, T_amb_C: float) -> float:
    Tc = T_abs_C + 273.15
    Th = T_amb_C + 273.15 + 10
    if Th <= Tc:
        return 0.0
    cop_carnot = Tc / (Th - Tc)
    cop_eff = max(cop_carnot * ETA_CARNOT_FRAC, 1.0)
    return Q_chill_GJ / cop_eff


def calc_We(tech: dict, T_cool_C: float, p_final_bar: float,
            capture_t_yr: float = REF_CAPTURE_MT_YR * 1e6) -> dict:
    """
    규모 보정 적용:
      SRD     → IEAGHG 2013/04 (큰 플랜트 → +SRD)
      We_comp → NETL Rev4 / IEAGHG 2014 (큰 플랜트 → -We_comp)
    """
    # 1) 규모 효과 적용 (SRD, We_comp)
    srd_scaled = scale_srd(tech["SRD"], capture_t_yr)
    we_comp_scaled = scale_we_comp(tech["We_comp"], capture_t_yr)

    # 2) 열의 전기등가
    eta_c = carnot_efficiency(tech["T_regen"], T_cool_C) * ETA_CARNOT_FRAC
    We_thermal_eq = srd_scaled * eta_c

    # 3) 압축 — 최종 압력 보정
    base_p = 152.0
    p_factor = np.log(p_final_bar / tech["p_regen_bar"]) / np.log(base_p / 1.8)
    p_factor = max(p_factor, 0.3)
    we_comp_eff = we_comp_scaled * p_factor

    # 4) 냉동기 (CAP만 동적)
    if tech["category"] == "Chilled NH₃":
        Q_chill = srd_scaled * 0.18
        we_chill_eff = chiller_We(Q_chill, tech["T_abs"], T_cool_C)
    else:
        we_chill_eff = tech.get("We_chill", 0.0)

    we_pump = tech["We_pump"]
    we_aux = tech["We_aux"]

    We_elec = we_pump + we_comp_eff + we_chill_eff + we_aux
    We_total = We_thermal_eq + We_elec

    return {
        "SRD_scaled": srd_scaled,
        "SRD_base": tech["SRD"],
        "srd_scale_pct": (srd_scaled / tech["SRD"] - 1) * 100,
        "We_comp_scale_pct": (we_comp_scaled / tech["We_comp"] - 1) * 100 if tech["We_comp"] > 0 else 0,
        "We_thermal_eq": We_thermal_eq,
        "We_pump": we_pump,
        "We_comp": we_comp_eff,
        "We_chill": we_chill_eff,
        "We_aux": we_aux,
        "We_elec": We_elec,
        "We_total": We_total,
    }


def calc_SPECCA(srd: float, we_elec: float, capture: float) -> float:
    if capture <= 0:
        return float("nan")
    return (srd * SRD_TO_SPECCA + we_elec * WE_TO_SPECCA) / capture


def scale_capex_per_t(capex_per_t: float, capture_t_yr: float,
                       ref_t_yr: float = REF_CAPTURE_MT_YR * 1e6,
                       n: float = CAPEX_SCALE_EXPONENT) -> float:
    """
    CAPEX 규모 효과 (IEAGHG 2007, NETL QGESS — CCS 표준 n=0.65).
    CAPEX_per_t = CAPEX_ref × (ref / actual)^(1-n)
    큰 플랜트일수록 단위 톤당 CAPEX 감소.
    """
    if capture_t_yr <= 0:
        return capex_per_t
    return capex_per_t * (ref_t_yr / capture_t_yr) ** (1 - n)


def scale_srd(srd_ref: float, capture_t_yr: float,
              ref_t_yr: float = REF_CAPTURE_MT_YR * 1e6) -> float:
    """
    SRD 규모 효과 (IEAGHG 2013/04 Solvent R&D Priorities).
    파일럿(idealized) → 상용 이행 시 SRD ↑ (실운영 비효율).
      log10(scale/ref) × 10% per decade
      0.1× ref(파일럿) → SRD -10% (idealized)
      1× ref           → SRD ref
      10× ref(메가)    → SRD +10% (real-world penalty)
    """
    if capture_t_yr <= 0 or srd_ref <= 0:
        return srd_ref
    log_ratio = np.log10(capture_t_yr / ref_t_yr)
    factor = 1 + SRD_SCALE_PER_DECADE * log_ratio
    factor = max(SRD_CLIP[0], min(factor, SRD_CLIP[1]))
    return srd_ref * factor


def scale_we_comp(we_comp_ref: float, capture_t_yr: float,
                  ref_t_yr: float = REF_CAPTURE_MT_YR * 1e6) -> float:
    """
    압축기 We 규모 효과 (NETL Rev4, IEAGHG 2014).
    소형(왕복식 η~75%) → 대형(다단 원심 η~85%).
      log10(ref/scale) × 6% per decade
      0.1× ref → +6% (낮은 효율)
      1× ref   → ref
      10× ref  → -6% (높은 효율)
    """
    if capture_t_yr <= 0 or we_comp_ref <= 0:
        return we_comp_ref
    log_ratio = np.log10(ref_t_yr / capture_t_yr)
    factor = 1 + WE_COMP_SCALE_PER_DECADE * log_ratio
    factor = max(WE_COMP_CLIP[0], min(factor, WE_COMP_CLIP[1]))
    return we_comp_ref * factor


def calc_COCA(
    capex_per_t, opex_solvent, opex_other, we_elec, capture_t_yr,
    lifetime_yr=25, discount=0.08, elec_price_usd_mwh=USD_PER_MWH_GRID,
    capex_mult=1.0, ccu_share=0.0,
) -> dict:
    # 규모의 경제 적용 (NETL B12C 3.7 Mt/yr 대비 보정)
    scaled_capex_per_t = scale_capex_per_t(capex_per_t, capture_t_yr)
    # CCU 정제 등급 CAPEX adder 적용
    eff_capex_per_t = scaled_capex_per_t * (1 + ccu_share * (capex_mult - 1))

    crf = (discount * (1 + discount) ** lifetime_yr) / ((1 + discount) ** lifetime_yr - 1)
    annual_capex_usd_per_t = eff_capex_per_t * crf
    elec_cost = we_elec * 277.78 / 1000 * elec_price_usd_mwh
    opex_total = opex_solvent + opex_other + elec_cost
    coca = annual_capex_usd_per_t + opex_total

    # 규모 보정 배율 (UI 표시용)
    scale_factor = scaled_capex_per_t / capex_per_t if capex_per_t > 0 else 1.0

    return {
        "base_capex_per_t":    capex_per_t,            # LIT 원본 (3.7 Mt 기준)
        "scaled_capex_per_t":  scaled_capex_per_t,     # 규모 보정 후
        "eff_capex_per_t":     eff_capex_per_t,        # +CCU adder 후
        "scale_factor":        scale_factor,
        "capex_adder":         eff_capex_per_t - scaled_capex_per_t,
        "annual_capex":        annual_capex_usd_per_t,
        "opex_solvent":        opex_solvent,
        "opex_other":          opex_other,
        "elec_cost":           elec_cost,
        "opex_total":          opex_total,
        "COCA":                coca,
        "annual_total_usd":    coca * capture_t_yr,
    }


def calc_revenue(capture_t_yr, ccs_share, ccs_yield, ccu_share, ccu_yield,
                 ccu_price_krw_t, market_price_usd_t, market_type, fx_krw_per_usd) -> dict:
    """
    매출/보조금 계산.
      - stored_t  = 격리량 (CCS 모드) — 배출권 거래/45Q-CCS 보조금 대상
      - sold_lco2_t = 출하량 (CCU 모드) — 액화탄산 매출 + 45Q-EOR 보조금 대상
      - 보조금은 격리량 또는 활용량 양쪽에 적용 가능 (한쪽은 0)
    """
    stored_t = capture_t_yr * ccs_share * ccs_yield
    sold_lco2_t = capture_t_yr * ccu_share * ccu_yield
    ccu_revenue_usd = sold_lco2_t * ccu_price_krw_t / fx_krw_per_usd

    # 보조금 적용 대상 (CCS면 격리량, CCU면 활용량 — 한쪽은 0)
    qualifying_t = stored_t + sold_lco2_t

    if market_type == "credit":
        # 배출권 거래제: CCS 격리량만 (CCU는 격리 안되므로 거래 불가)
        market_revenue_usd = stored_t * market_price_usd_t
        subsidy_usd = 0.0
    else:
        # 정부 보조금: CCS 격리량 또는 CCU 활용량 양쪽 적용 가능
        # (45Q-CCS는 stored, 45Q-EOR/CCU는 sold, NL SDE++는 stored 등)
        market_revenue_usd = 0.0
        subsidy_usd = qualifying_t * market_price_usd_t

    total_revenue_usd = ccu_revenue_usd + market_revenue_usd + subsidy_usd
    revenue_per_capture = total_revenue_usd / capture_t_yr if capture_t_yr > 0 else 0
    return {
        "stored_t":         stored_t,
        "sold_lco2_t":      sold_lco2_t,
        "qualifying_t":     qualifying_t,
        "ccu_revenue":      ccu_revenue_usd,
        "market_revenue":   market_revenue_usd,
        "subsidy":          subsidy_usd,
        "total_revenue":    total_revenue_usd,
        "rev_per_capture":  revenue_per_capture,
    }


# ======================================================================
# 사이드바
# ======================================================================
with st.sidebar:
    st.markdown("### ⚙️ 입력 파라미터")

    selected = st.multiselect(
        "비교할 기술 선택",
        options=TECH_KEYS,
        default=["MEA_baseline", "K2CO3_KIERSOL", "CAP_B12C", "Biphasic_DMX", "TSA_Solid", "CaL"],
        format_func=lambda k: LIT[k]["name"],
    )

    st.caption("⌨️ 모든 입력은 직접 숫자 입력 가능 (미입력시 default 사용)")

    capture_mt_yr = st.number_input(
        "연간 CO₂ 포집량 [MtCO₂/yr]",
        min_value=0.1, max_value=20.0, value=3.7, step=0.1,
        format="%.2f",
        help=(
            "NETL B12C/B12B 기준값 ≈ 3.7 Mt/yr · default: 3.7\n"
            "규모 효과 적용 (CCS specific):\n"
            "• CAPEX: IEAGHG/NETL n=0.65\n"
            "• SRD: ±10%/decade (IEAGHG 2013/04)\n"
            "• We_comp: ±6%/decade (NETL Rev4)"
        ),
    )
    capture_t_yr = capture_mt_yr * 1e6

    # 규모 효과 안내 (CAPEX, SRD, We_comp 모두)
    _capex_pct = ((REF_CAPTURE_MT_YR / capture_mt_yr) ** (1 - CAPEX_SCALE_EXPONENT) - 1) * 100
    _log_r = np.log10(capture_mt_yr / REF_CAPTURE_MT_YR)
    _srd_pct = max(min(SRD_SCALE_PER_DECADE * _log_r * 100, (SRD_CLIP[1]-1)*100), (SRD_CLIP[0]-1)*100)
    _wec_pct = max(min(-WE_COMP_SCALE_PER_DECADE * _log_r * 100, (WE_COMP_CLIP[1]-1)*100), (WE_COMP_CLIP[0]-1)*100)

    def _arr(v):
        if v > 0.5: return "↑"
        if v < -0.5: return "↓"
        return "≈"
    st.caption(
        f"→ 규모 보정 ({REF_CAPTURE_MT_YR} Mt 대비):  "
        f"CAPEX {_arr(_capex_pct)}{abs(_capex_pct):.0f}% · "
        f"SRD {_arr(_srd_pct)}{abs(_srd_pct):.1f}% · "
        f"We_comp {_arr(_wec_pct)}{abs(_wec_pct):.1f}%"
    )

    capture_eff_pct = st.number_input(
        "포집율 [%]",
        min_value=50, max_value=99, value=90, step=1,
        help="default: 90",
    )
    capture_eff = capture_eff_pct / 100.0

    T_cool_C = st.number_input(
        "냉각수 온도 [°C]",
        min_value=0, max_value=50, value=25, step=1,
        help="default: 25",
    )

    p_final_bar = st.number_input(
        "CO₂ 최종 압력 [bar]",
        min_value=5, max_value=300, value=152, step=1,
        help=(
            "용도별:\n"
            "• 식품 액화탄산: 15~20 bar\n"
            "• 산업용: 5~25 bar\n"
            "• 파이프라인: 100~150 bar\n"
            "• EOR/저장: 150~200 bar\n"
            "default: 152"
        ),
    )

    if p_final_bar < 30:
        _use_label = "🧊 액화탄산 (식품·산업용)"
    elif p_final_bar < 80:
        _use_label = "💨 가스 수송"
    elif p_final_bar < 120:
        _use_label = "🚰 파이프라인"
    else:
        _use_label = "⛏️ EOR / 지중저장"
    st.caption(f"→ 추정 용도: **{_use_label}**")

    st.markdown("---")
    st.markdown("### 💰 경제성 가정")

    lifetime = st.number_input("플랜트 수명 [년]", 10, 50, 25, 1, help="default: 25")
    discount_pct = st.number_input("할인율 [%]", 2.0, 15.0, 8.0, 0.5, format="%.1f", help="default: 8.0")
    discount = discount_pct / 100.0
    elec_price = st.number_input("전기 가격 [USD/MWh]", 20, 300, 80, 5, help="default: 80")

    fx_krw_per_usd = st.number_input(
        "💱 환율 [KRW/USD]",
        min_value=800.0, max_value=2000.0, value=1400.0, step=10.0,
        format="%.0f",
        help="default: 1,400 (2026.4 기준)",
    )
    st.caption(f"→ 현재 환율: **{fx_krw_per_usd:,.0f} KRW/USD**")

    st.markdown("---")
    st.markdown("### ♻️ CCUS 시설 모드")
    st.caption("⚠️ 실제 시설은 CCS/CCU 중 하나로 commit")

    facility_mode = st.radio(
        "시설 처분 경로",
        options=["CCS", "CCU"],
        format_func=lambda x: "🏔️ CCS — 지중저장" if x == "CCS" else "🥤 CCU — 액화탄산 출하",
        horizontal=True,
    )

    if facility_mode == "CCS":
        ccs_share, ccu_share = 1.0, 0.0
    else:
        ccs_share, ccu_share = 0.0, 1.0

    if facility_mode == "CCS":
        ccs_yield_pct = st.number_input(
            "CCS 격리 수율 [%]",
            min_value=80.0, max_value=99.0, value=92.0, step=0.5,
            format="%.1f",
            help="포집→탈수→압축→수송→주입 누적. default: 92%",
        )
        ccs_yield = ccs_yield_pct / 100.0

        ccu_grade_key = "food"
        ccu = CCU_GRADES[ccu_grade_key]
        ccu_price_krw = 0

        st.markdown("##### 💚 탄소시장 / CCUS 보조금")
        market_options = list(CARBON_MARKETS.keys())
        market_key = st.selectbox(
            "시장/제도 선택",
            options=market_options,
            format_func=lambda k: CARBON_MARKETS[k]["label"],
            index=market_options.index("45Q-CCS"),
            help="default: US 45Q CCS ($85/t)",
        )

    else:
        ccs_yield = 1.0

        ccu_grade_key = st.selectbox(
            "CCU 정제 등급",
            options=list(CCU_GRADES.keys()),
            format_func=lambda k: CCU_GRADES[k]["label"],
            index=0,
            help="순도↑ → 수율↓ + 정제 CAPEX↑",
        )
        ccu = CCU_GRADES[ccu_grade_key]
        st.caption(
            f"→ 수율 **{ccu['yield']*100:.0f}%** · "
            f"표준가 **{ccu['price_krw_t']:,} KRW/t** · "
            f"CAPEX ×**{ccu['capex_mult']:.2f}**"
        )

        ccu_price_krw = st.number_input(
            "액화탄산 판매가 [KRW/t]",
            min_value=0, max_value=2_000_000, value=ccu["price_krw_t"], step=10_000,
            format="%d",
            help=f"default: {ccu['price_krw_t']:,}",
        )
        st.caption(f"→ 입력값: **{ccu_price_krw:,} KRW/t**")

        st.markdown("##### 💚 CCU 보조금 (선택)")
        st.caption("CCU는 배출권 매출 없음. 일부 보조금만 가능.")
        ccu_market_options = ["None", "45Q-EOR", "Custom"]
        market_key = st.selectbox(
            "보조금 제도",
            options=ccu_market_options,
            format_func=lambda k: ("없음" if k == "None" else CARBON_MARKETS[k]["label"]),
            index=0,
        )

    if market_key == "None":
        market_price_usd = 0.0
        market_type = "credit"
        market_label = "없음"
    elif market_key == "Custom":
        market_price_usd = st.number_input(
            "Custom 단가 [USD/tCO₂]",
            min_value=0.0, max_value=500.0, value=50.0, step=1.0,
            format="%.1f",
        )
        market_type = st.radio("종류", ["credit", "subsidy"], horizontal=True,
                                format_func=lambda x: "배출권 (매출)" if x=="credit" else "보조금")
        market_label = "Custom"
    else:
        market = CARBON_MARKETS[market_key]
        market_price_usd = st.number_input(
            f"단가 [USD/tCO₂]  ({market['native']})",
            min_value=0.0, max_value=500.0, value=float(market["price_usd_t"]), step=1.0,
            format="%.1f",
            help=f"default: {market['price_usd_t']} USD/t",
        )
        market_type = market["type"]
        market_label = market["label"]

    if market_price_usd > 0:
        st.caption(
            f"→ {('💰 배출권 매출' if market_type=='credit' else '🎁 정부 보조금')} · "
            f"**${market_price_usd:.1f}/t** "
            f"(≈ {market_price_usd*fx_krw_per_usd:,.0f} KRW/t)"
        )

    st.markdown("---")
    st.caption(
        "**†** = 파일럿/실증 데이터.<br>"
        "데이터: NETL Rev4a, IEAGHG, DOE, KIER",
        unsafe_allow_html=True,
    )

# ======================================================================
# 헤더
# ======================================================================
st.title("🌫️ 비아민계 CO₂ 포집 흡수제 기술 벤치마크")
st.caption(
    "NETL Rev4a B12C · IEAGHG · DOE NETL · KIER KIERSOL 기반 | "
    "MEA 30 wt% 비교 기준선 포함"
)

if not selected:
    st.warning("⚠️ 사이드바에서 비교할 기술을 1개 이상 선택해주세요.")
    st.stop()

pilot_techs = [LIT[k]["name"] for k in selected if LIT[k]["is_pilot"]]
if pilot_techs:
    st.markdown(
        f"<div class='pilot-warning'>⚠️ <strong>파일럿/실증 데이터 포함:</strong> "
        f"{', '.join(pilot_techs)} — 상용 스케일에서 수치가 변할 수 있습니다.</div>",
        unsafe_allow_html=True,
    )

# ======================================================================
# 결과 계산
# ======================================================================
results = []
for k in selected:
    t = LIT[k]
    we = calc_We(t, T_cool_C, p_final_bar, capture_t_yr=capture_t_yr)
    # 규모 보정된 SRD를 SPECCA에 사용
    specca = calc_SPECCA(we["SRD_scaled"], we["We_elec"], capture_eff)
    cost = calc_COCA(
        t["CAPEX_per_t"], t["OPEX_solvent"], t["OPEX_other"],
        we["We_elec"], capture_t_yr, lifetime, discount, elec_price,
        capex_mult=ccu["capex_mult"], ccu_share=ccu_share,
    )
    rev = calc_revenue(
        capture_t_yr, ccs_share, ccs_yield,
        ccu_share, ccu["yield"], ccu_price_krw,
        market_price_usd, market_type, fx_krw_per_usd,
    )
    net_coca = cost["COCA"] - rev["rev_per_capture"]

    # 연간 손익 (annual profit)
    annual_cost_usd = cost["annual_total_usd"]                 # = COCA × capture_t_yr
    annual_revenue_usd = rev["total_revenue"]
    annual_profit_usd = annual_revenue_usd - annual_cost_usd   # 양수 = 흑자
    annual_profit_krw = annual_profit_usd * fx_krw_per_usd

    results.append({
        "key": k,
        "name": t["name"],
        "category": t["category"],
        "is_pilot": t["is_pilot"],
        "SRD": we["SRD_scaled"],     # 규모 보정 후 (display용)
        **we,
        "SPECCA": specca,
        **cost,
        **rev,
        "Net_COCA": net_coca,
        "annual_cost_usd":     annual_cost_usd,
        "annual_revenue_usd":  annual_revenue_usd,
        "annual_profit_usd":   annual_profit_usd,
        "annual_profit_krw":   annual_profit_krw,
        "loss_kg_per_tCO2": t["loss_kg_per_tCO2"],
        "loss_mech": t["loss_mech"],
        "T_regen": t["T_regen"],
        "T_abs": t["T_abs"],
        "source": t["source"],
        "notes": t["notes"],
    })

df = pd.DataFrame(results)

# ======================================================================
# 탭
# ======================================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "① 종합 비교", "② 에너지 분해", "③ 경제성",
    "④ 흡수제/흡착제 손실", "⑤ 트렌드", "⑥ Custom 입력",
    "⑦ 참고문헌", "⑧ 방법론",
])

# ---------- ① 종합 비교 ----------
with tab1:
    with st.expander("📖 **KPI 지표 정의** — 클릭해서 펼치기/접기", expanded=False):
        def_cols = st.columns(4)
        definitions = [
            {"title": "SRD", "full": "Specific Reboiler Duty",
             "unit": "GJ / tCO₂", "color": "#4FC3F7",
             "formula": "Q<sub>regen</sub> / m<sub>CO₂</sub>",
             "desc": "흡수제 재생에 필요한 단위 CO₂당 열량.",
             "hint": "↓ 낮을수록 열효율 우수"},
            {"title": "We", "full": "Equivalent Work (전력등가 일)",
             "unit": "GJe / tCO₂", "color": "#81C784",
             "formula": "We<sub>thermal</sub>(Carnot) + We<sub>elec</sub>",
             "desc": "재생열을 Carnot로 전기등가 환산 + 펌프·압축·냉동기·보조 전력 합.",
             "hint": "↓ 낮을수록 통합 에너지 효율 우수"},
            {"title": "SPECCA", "full": "Specific Primary Energy<br>Consumption for CO₂ Avoided",
             "unit": "MJ / tCO₂", "color": "#FFB74D",
             "formula": "(SRD × 500 + We<sub>elec</sub> × 2,500) / capture",
             "desc": "포집을 위해 추가로 소모하는 1차 에너지를 포집율로 정규화.",
             "hint": "↓ 낮을수록 1차 에너지 효율 우수"},
            {"title": "COCA", "full": "Cost Of CO₂ Avoided / Captured",
             "unit": "USD / tCO₂", "color": "#E57373",
             "formula": "(연환산 CAPEX + OPEX) / 연 포집량",
             "desc": "단위 CO₂당 종합 비용. CAPEX는 CRF로 연환산.",
             "hint": "↓ 낮을수록 경제성 우수"},
        ]
        for col, d in zip(def_cols, definitions):
            with col:
                st.markdown(
                    f"""
                    <div style='background:#1E2128; border-top:3px solid {d["color"]};
                                border-radius:6px; padding:10px 12px; height:230px;
                                display:flex; flex-direction:column;'>
                        <div style='font-size:1.1rem; font-weight:700; color:{d["color"]};
                                    margin-bottom:2px;'>{d["title"]}</div>
                        <div style='font-size:0.7rem; color:#8b95a7; margin-bottom:4px;
                                    line-height:1.2;'>{d["full"]}</div>
                        <div style='font-size:0.75rem; color:#E8EAED; margin-bottom:6px;'>
                            <b>단위</b>: {d["unit"]}
                        </div>
                        <div style='font-size:0.75rem; background:#0E1117; padding:4px 6px;
                                    border-radius:3px; font-family:monospace; color:#B0BEC5;
                                    margin-bottom:6px;'>{d["formula"]}</div>
                        <div style='font-size:0.72rem; color:#B0BEC5; line-height:1.4;
                                    flex:1;'>{d["desc"]}</div>
                        <div style='font-size:0.7rem; color:{d["color"]}; margin-top:4px;
                                    font-weight:600;'>{d["hint"]}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown(
            """
            <div style='font-size:0.72rem; color:#8b95a7; margin-top:10px;
                        padding:6px 10px; background:#1E2128; border-radius:4px;'>
            <b>📐 보조 개념</b> &nbsp;·&nbsp;
            <b>Carnot</b>: η<sub>C</sub> = (T<sub>regen</sub> − T<sub>cool</sub>) / T<sub>regen</sub> &nbsp;·&nbsp;
            실효 = η<sub>C</sub> × 0.55 &nbsp;·&nbsp;
            <b>CRF</b>: i(1+i)<sup>n</sup> / [(1+i)<sup>n</sup> − 1] &nbsp;·&nbsp;
            <b>CAP COP</b>: T<sub>abs</sub> / (T<sub>amb</sub> − T<sub>abs</sub>) × 0.55
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown("### 핵심 KPI 비교")
    st.caption("4대 지표를 KPI별 순위 정렬 · 🟢 최고 · 🔴 최악 (모든 지표 낮을수록 우수)")

    kpi_specs = [
        ("SRD", "SRD", "GJ/tCO₂", "{:,.2f}"),
        ("We_total", "We 총합", "GJe/tCO₂", "{:,.2f}"),
        ("SPECCA", "SPECCA", "MJ/tCO₂", "{:,.0f}"),
        ("COCA", "COCA", "USD/tCO₂", "{:,.1f}"),
    ]

    def render_kpi_chart(spec, container):
        key, label, unit, fmt = spec
        sorted_r = sorted(results, key=lambda r: r[key])
        n = len(sorted_r)
        names = [SHORT_NAMES.get(r["key"], r["name"]) for r in sorted_r]
        vals = [r[key] for r in sorted_r]
        colors = []
        for i in range(n):
            if i == 0:
                colors.append("#81C784")
            elif i == n - 1 and n > 1:
                colors.append("#E57373")
            else:
                colors.append("#4FC3F7")
        best = vals[0] if vals else 0
        text_labels = []
        for i, v in enumerate(vals):
            if i == 0:
                text_labels.append(f"★ {fmt.format(v)}")
            else:
                pct = (v - best) / best * 100 if best > 0 else 0
                text_labels.append(f"{fmt.format(v)}  (+{pct:.0f}%)")
        xmax = max(vals) * 1.35 if vals else 1
        f = go.Figure(go.Bar(
            x=vals, y=names, orientation="h",
            marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.15)", width=1)),
            text=text_labels, textposition="outside",
            textfont=dict(size=15, color="#E8EAED"),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>" + label + ": %{x:,.2f}<extra></extra>",
        ))
        f.update_layout(
            title=dict(
                text=f"<b style='font-size:18px;'>{label}</b>  "
                     f"<span style='font-size:13px; color:#8b95a7;'>[{unit}]</span>",
                x=0.02,
            ),
            template="plotly_dark", height=340,
            margin=dict(l=10, r=30, t=55, b=30),
            xaxis=dict(showgrid=True, gridcolor="#2C313C", zeroline=False,
                       range=[0, xmax], tickfont=dict(size=12)),
            yaxis=dict(autorange="reversed", tickfont=dict(size=14, color="#E8EAED")),
            showlegend=False,
            uniformtext=dict(minsize=12, mode="show"),
        )
        container.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    row1 = st.columns(2)
    render_kpi_chart(kpi_specs[0], row1[0])
    render_kpi_chart(kpi_specs[1], row1[1])
    row2 = st.columns(2)
    render_kpi_chart(kpi_specs[2], row2[0])
    render_kpi_chart(kpi_specs[3], row2[1])

    st.markdown("---")
    st.markdown("### 데이터 테이블")
    df["material"] = df["key"].map(MATERIALS)
    show_df = df[["name", "material", "category", "SRD", "We_total", "We_elec",
                  "SPECCA", "COCA", "T_regen", "T_abs", "source"]].copy()
    show_df.columns = ["기술", "흡수제/소재", "분류", "SRD", "We_total", "We_elec",
                       "SPECCA", "COCA", "T_regen[°C]", "T_abs[°C]", "출처"]
    show_df["SRD"] = show_df["SRD"].map(lambda x: f"{x:,.2f}")
    show_df["We_total"] = show_df["We_total"].map(lambda x: f"{x:,.2f}")
    show_df["We_elec"] = show_df["We_elec"].map(lambda x: f"{x:,.2f}")
    show_df["SPECCA"] = show_df["SPECCA"].map(lambda x: f"{x:,.0f}")
    show_df["COCA"] = show_df["COCA"].map(lambda x: f"{x:,.1f}")
    st.dataframe(show_df, use_container_width=True, hide_index=True)

# ---------- ② 에너지 분해 ----------
with tab2:
    st.markdown("### 전력등가 일(We) 분해 — 스택 막대")
    st.caption("We_thermal: SRD를 Carnot 효율로 전기등가 환산 (참고). We_elec: 펌프·압축·냉동기·보조.")

    components = [
        ("We_pump", "펌프", "#7986CB"),
        ("We_comp", "CO₂ 압축", "#4DD0E1"),
        ("We_chill", "냉동기", "#BA68C8"),
        ("We_aux", "보조", "#A1887F"),
        ("We_thermal_eq", "열 (Carnot 환산)", "#FFB74D"),
    ]

    f = go.Figure()
    names_short = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]
    for col, label, color in components:
        f.add_trace(go.Bar(
            name=label, x=names_short,
            y=[r[col] for r in results],
            marker_color=color,
            hovertemplate="%{x}<br>" + label + ": %{y:.3f} GJe/tCO₂<extra></extra>",
        ))
    f.update_layout(
        barmode="stack", template="plotly_dark",
        height=480, yaxis_title="We [GJe/tCO₂]",
        xaxis_tickangle=0, margin=CHART_MARGIN_STACK,
        legend=dict(orientation="h", y=-0.18),
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("---")
    st.markdown("### CAP 냉동기 부하 — 냉각수 온도 민감도")
    st.caption("CAP의 We_chill은 냉각수 온도에 민감. Carnot COP × 0.55.")

    if any(r["category"] == "Chilled NH₃" for r in results):
        T_range = np.arange(5, 46, 2)
        cap_data = LIT["CAP_B12C"]
        Q_chill = cap_data["SRD"] * 0.18
        chill_we = [chiller_We(Q_chill, cap_data["T_abs"], T) for T in T_range]
        f2 = go.Figure()
        f2.add_trace(go.Scatter(
            x=T_range, y=chill_we, mode="lines+markers",
            line=dict(color="#BA68C8", width=3), marker=dict(size=8),
        ))
        f2.add_vline(x=T_cool_C, line_dash="dash", line_color="#ffc107",
                     annotation_text=f"현재 {T_cool_C}°C")
        f2.update_layout(
            template="plotly_dark", height=350,
            xaxis_title="냉각수 온도 [°C]", yaxis_title="We_chill [GJe/tCO₂]",
        )
        st.plotly_chart(f2, use_container_width=True, config=PLOTLY_CONFIG)
    else:
        st.info("CAP을 선택하면 냉동기 민감도 그래프가 활성화됩니다.")

# ---------- ③ 경제성 ----------
with tab3:
    st.markdown("### CAPEX (별도) + OPEX 스택 + COCA 요약")

    col1, col2 = st.columns([1, 1])
    names_short = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]

    with col1:
        f = go.Figure()
        f.add_trace(go.Bar(
            x=names_short, y=[r["annual_capex"] for r in results],
            marker_color="#4FC3F7",
            text=[f"{r['annual_capex']:,.1f}" for r in results],
            textposition="outside",
        ))
        scale_pct_calc = ((REF_CAPTURE_MT_YR / capture_mt_yr) ** (1 - CAPEX_SCALE_EXPONENT) - 1) * 100
        scale_label = (f"규모 보정 +{scale_pct_calc:.0f}%" if scale_pct_calc > 1
                       else f"규모 보정 {scale_pct_calc:.0f}%" if scale_pct_calc < -1
                       else "규모 보정 ≈ 0%")
        f.update_layout(
            title=(f"연환산 CAPEX [USD/tCO₂] · 수명 {lifetime}년 · 할인율 {discount*100:.1f}%"
                   f"<br><span style='font-size:11px; color:#8b95a7;'>"
                   f"포집 {capture_mt_yr:.1f} Mt/yr → {scale_label} (기준 {REF_CAPTURE_MT_YR} Mt)</span>"),
            template="plotly_dark", height=420,
            xaxis_tickangle=0, margin=dict(l=10, r=10, t=70, b=80),
        )
        st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    with col2:
        f = go.Figure()
        for col_, label, color in [
            ("opex_solvent", "용매/소재", "#81C784"),
            ("opex_other", "유틸·인건·정비", "#FFB74D"),
            ("elec_cost", "전력 비용", "#E57373"),
        ]:
            f.add_trace(go.Bar(
                name=label, x=names_short,
                y=[r[col_] for r in results], marker_color=color,
            ))
        f.update_layout(
            title="OPEX 분해 [USD/tCO₂]",
            barmode="stack", template="plotly_dark", height=400,
            xaxis_tickangle=0, margin=CHART_MARGIN_STACK,
            legend=dict(orientation="h", y=-0.20),
        )
        st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("---")
    st.markdown("### COCA 요약")

    f = go.Figure()
    f.add_trace(go.Bar(
        x=[SHORT_NAMES.get(r["key"], r["name"]) for r in results],
        y=[r["COCA"] for r in results],
        marker_color=["#FFD54F" if r["is_pilot"] else "#4DD0E1" for r in results],
        text=[f"{r['COCA']:,.1f}" for r in results],
        textposition="outside",
    ))
    f.update_layout(
        title=f"COCA [USD/tCO₂] (연간 {capture_mt_yr:.1f} Mt 기준)",
        template="plotly_dark", height=400,
        xaxis_tickangle=0, margin=CHART_MARGIN,
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    cost_df = pd.DataFrame([{
        "기술": r["name"],
        "연환산 CAPEX": f"{r['annual_capex']:,.1f}",
        "OPEX 합": f"{r['opex_total']:,.1f}",
        "  └ 용매": f"{r['opex_solvent']:,.1f}",
        "  └ 기타": f"{r['opex_other']:,.1f}",
        "  └ 전력": f"{r['elec_cost']:,.1f}",
        "COCA": f"{r['COCA']:,.1f}",
        "연간 총비용 [M$]": f"{r['annual_total_usd']/1e6:,.1f}",
    } for r in results])
    st.dataframe(cost_df, use_container_width=True, hide_index=True)

    # ── 매출/보조금/Net COCA ──
    st.markdown("---")
    st.markdown(f"### 💰 매출·보조금 반영 — **Net COCA** ({facility_mode} 모드)")

    if facility_mode == "CCS":
        st.caption(
            f"🏔️ **CCS 모드** · 격리수율 **{ccs_yield*100:.0f}%** · "
            f"시장: **{market_label}** ${market_price_usd:.1f}/t · "
            f"환율 **{fx_krw_per_usd:,.0f} KRW/USD**"
        )
    else:
        st.caption(
            f"🥤 **CCU 모드** · {ccu['label']} · "
            f"수율 **{ccu['yield']*100:.0f}%** · 판매가 **{ccu_price_krw:,} KRW/t** · "
            f"CAPEX adder **+{(ccu['capex_mult']-1)*100:.0f}%** · "
            f"환율 **{fx_krw_per_usd:,.0f} KRW/USD**"
        )

    short_x = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]

    f_net = go.Figure()
    f_net.add_trace(go.Bar(
        name="COCA (비용)",
        x=short_x, y=[r["COCA"] for r in results],
        marker_color="#E57373",
        text=[f"{r['COCA']:,.1f}" for r in results], textposition="inside",
        textfont=dict(size=13, color="white"),
    ))
    f_net.add_trace(go.Bar(
        name="− 매출/보조금",
        x=short_x, y=[-r["rev_per_capture"] for r in results],
        marker_color="#81C784",
        text=[f"−{r['rev_per_capture']:,.1f}" for r in results], textposition="inside",
        textfont=dict(size=13, color="white"),
    ))
    # Net COCA — 큰 노란 다이아몬드 + 흰 테두리 + 검은 외곽
    f_net.add_trace(go.Scatter(
        name="◆ Net COCA",
        x=short_x, y=[r["Net_COCA"] for r in results],
        mode="markers+text",
        marker=dict(
            size=26, color="#FFEB3B", symbol="diamond",
            line=dict(color="#212121", width=3),
        ),
        text=[f"<b>{r['Net_COCA']:+,.1f}</b>" for r in results],
        textposition="top center",
        textfont=dict(size=17, color="#FFEB3B"),
        hovertemplate="<b>%{x}</b><br>Net COCA: %{y:,.1f} USD/t<extra></extra>",
    ))
    # Net COCA 라벨 위에 검은 박스 그림자 효과 (가독성)
    for r in results:
        x = SHORT_NAMES.get(r["key"], r["name"])
        f_net.add_annotation(
            x=x, y=r["Net_COCA"],
            text=f"<b>Net: {r['Net_COCA']:+,.1f}</b>",
            showarrow=False,
            yshift=28,
            font=dict(size=14, color="#FFEB3B"),
            bgcolor="rgba(0,0,0,0.75)",
            bordercolor="#FFEB3B",
            borderwidth=1,
            borderpad=4,
        )

    f_net.add_hline(y=0, line_color="white", line_width=1.5, line_dash="dot")
    f_net.update_layout(
        title="COCA vs Net COCA [USD/tCO₂포집] — Net 음수 = 흑자",
        template="plotly_dark", height=520, barmode="relative",
        margin=dict(l=10, r=10, t=60, b=80),
        legend=dict(orientation="h", y=-0.12),
        xaxis_tickangle=0,
    )
    # Net COCA 막대 아래에 텍스트가 안잘리도록 우측 여유
    st.plotly_chart(f_net, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("##### 매출/보조금 상세")
    rev_rows = []
    for r in results:
        rev_rows.append({
            "기술": r["name"],
            "포집량 [kt/yr]": f"{capture_t_yr/1000:,.1f}",
            "격리량 [kt/yr]": f"{r['stored_t']/1000:,.1f}" if facility_mode == "CCS" else "—",
            "출하량 [kt/yr]": f"{r['sold_lco2_t']/1000:,.1f}" if facility_mode == "CCU" else "—",
            "배출권 매출 [M$/yr]": f"{r['market_revenue']/1e6:,.2f}",
            "보조금 [M$/yr]": f"{r['subsidy']/1e6:,.2f}",
            "CCU 매출 [M$/yr]": f"{r['ccu_revenue']/1e6:,.2f}",
            "총 매출 [M$/yr]": f"{r['total_revenue']/1e6:,.2f}",
            "총 매출 (원)": fmt_krw_amt(r['total_revenue'] * fx_krw_per_usd),
            "COCA": f"{r['COCA']:,.1f}",
            "Net COCA": f"{r['Net_COCA']:+,.1f}",
        })
    st.dataframe(pd.DataFrame(rev_rows), use_container_width=True, hide_index=True)

    if facility_mode == "CCU" and ccu["capex_mult"] > 1.0:
        base_capex_estimate = results[0]['eff_capex_per_t'] - results[0]['capex_adder']
        st.info(
            f"💡 **CCU 정제 CAPEX adder**: 기본 CAPEX의 +{(ccu['capex_mult']-1)*100:.0f}% "
            f"(예: {results[0]['name']} → ${base_capex_estimate:,.0f}/(t/yr) "
            f"→ ${results[0]['eff_capex_per_t']:,.0f}/(t/yr), "
            f"adder ${results[0]['capex_adder']:,.0f}/(t/yr))"
        )

    # ─────────────────────────────────────────────
    # 연간 손익 (Annual Profit / Loss) — 사업 관점
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🪙 연간 손익 분석 — 시설 단위 수익성")
    st.caption(
        f"연간 매출 − 연간 비용 = 연간 손익. "
        f"포집 {capture_mt_yr:.1f} Mt/yr · 환율 {fx_krw_per_usd:,.0f} KRW/USD"
    )

    # 손익 막대 차트 (USD)
    profits_usd = [r["annual_profit_usd"] / 1e6 for r in results]  # M$/yr
    profit_colors = ["#81C784" if p > 0 else "#E57373" for p in profits_usd]

    f_profit = go.Figure()
    f_profit.add_trace(go.Bar(
        x=short_x,
        y=profits_usd,
        marker_color=profit_colors,
        text=[
            f"<b>{p:+,.0f}</b> M$<br>"
            f"<span style='font-size:11px;'>"
            f"({fmt_krw_amt(p * 1e6 * fx_krw_per_usd, sign=True)})</span>"
            for p in profits_usd
        ],
        textposition="outside",
        textfont=dict(size=14),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>"
                      "연 손익: %{y:+,.0f} M$/yr<extra></extra>",
    ))
    f_profit.add_hline(y=0, line_color="white", line_width=1.5)
    ymin = min(profits_usd) * 1.3 if min(profits_usd) < 0 else min(profits_usd) - abs(min(profits_usd))*0.1
    ymax = max(profits_usd) * 1.4 if max(profits_usd) > 0 else max(profits_usd) + abs(max(profits_usd))*0.1
    f_profit.update_layout(
        title="연간 손익 [M$/yr] · 녹색=흑자 / 빨강=적자",
        template="plotly_dark", height=420,
        margin=dict(l=10, r=10, t=60, b=40),
        xaxis_tickangle=0,
        yaxis=dict(range=[ymin, ymax], zeroline=True, zerolinecolor="white",
                   zerolinewidth=2),
        showlegend=False,
    )
    st.plotly_chart(f_profit, use_container_width=True, config=PLOTLY_CONFIG)

    # 연간 손익 카드 (선택된 모든 기술)
    st.markdown("##### 💵 연간 손익 카드")
    profit_cols = st.columns(min(len(results), 6))
    for i, r in enumerate(results[:6]):
        with profit_cols[i]:
            profit_m_usd = r["annual_profit_usd"] / 1e6
            color = "#81C784" if profit_m_usd > 0 else "#E57373"
            sign_label = "흑자" if profit_m_usd > 0 else "적자"
            st.markdown(
                f"""
                <div style='background:#1E2128; border-top:3px solid {color};
                            border-radius:6px; padding:8px 10px;'>
                    <div style='font-size:0.75rem; color:#8b95a7;'>
                        {SHORT_NAMES.get(r['key'], r['name'])} — <b style='color:{color};'>{sign_label}</b>
                    </div>
                    <div style='font-size:1.0rem; color:{color}; font-weight:700;
                                margin-top:3px;'>
                        {profit_m_usd:+,.0f} M$/yr
                    </div>
                    <div style='font-size:0.85rem; color:#E8EAED;'>
                        {fmt_krw_amt(r['annual_profit_krw'], sign=True)}/yr
                    </div>
                    <div style='font-size:0.7rem; color:#8b95a7; margin-top:4px;'>
                        매출 ${r['annual_revenue_usd']/1e6:,.0f}M − 비용 ${r['annual_cost_usd']/1e6:,.0f}M
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 연간 손익 상세 테이블
    st.markdown("##### 손익 상세")
    profit_df = pd.DataFrame([{
        "기술": r["name"],
        "연 매출 [M$]":   f"{r['annual_revenue_usd']/1e6:,.1f}",
        "연 매출 (원)":   fmt_krw_amt(r['annual_revenue_usd'] * fx_krw_per_usd),
        "연 비용 [M$]":   f"{r['annual_cost_usd']/1e6:,.1f}",
        "연 비용 (원)":   fmt_krw_amt(r['annual_cost_usd'] * fx_krw_per_usd),
        "연 손익 [M$]":   f"{r['annual_profit_usd']/1e6:+,.1f}",
        "연 손익 (원)":   fmt_krw_amt(r['annual_profit_krw'], sign=True),
        "ROI [%]":        f"{r['annual_profit_usd']/r['annual_cost_usd']*100:+,.1f}" if r['annual_cost_usd'] > 0 else "—",
        "Net COCA [USD/t]": f"{r['Net_COCA']:+,.1f}",
    } for r in results])
    st.dataframe(profit_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown(f"##### 💴 단위 CO₂당 KRW 요약 (환율 {fx_krw_per_usd:,.0f} KRW/USD)")
    krw_cols = st.columns(min(len(results), 4))
    for i, r in enumerate(results[:4]):
        with krw_cols[i]:
            st.metric(
                f"{SHORT_NAMES.get(r['key'], r['name'])} Net COCA",
                f"{r['Net_COCA']*fx_krw_per_usd:+,.0f} 원/t",
                delta=f"COCA: {r['COCA']*fx_krw_per_usd:,.0f} 원/t",
                delta_color="off",
            )

# ---------- ④ 손실 ----------
with tab4:
    st.markdown("### 소재 손실 — 메커니즘별 비교")
    st.caption("습식: 분해/휘발 (kg/tCO₂). 고체: 사이클 열화/마모.")

    f = go.Figure()
    f.add_trace(go.Bar(
        x=[SHORT_NAMES.get(r["key"], r["name"]) for r in results],
        y=[r["loss_kg_per_tCO2"] for r in results],
        marker_color="#E57373",
        text=[f"{r['loss_kg_per_tCO2']:,.2f}" for r in results],
        textposition="outside",
        customdata=[r["name"] for r in results],
        hovertemplate="<b>%{customdata}</b><br>손실: %{y:,.2f} kg/tCO₂<extra></extra>",
    ))
    f.update_layout(
        title="소재 손실 [kg/tCO₂]",
        template="plotly_dark", height=400,
        xaxis_tickangle=0, margin=CHART_MARGIN,
        yaxis_type="log", yaxis_title="kg/tCO₂ (log scale)",
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    loss_df = pd.DataFrame([{
        "기술": r["name"],
        "흡수제/소재": MATERIALS.get(r["key"], "—"),
        "분류": r["category"],
        "손실 [kg/tCO₂]": f"{r['loss_kg_per_tCO2']:,.2f}",
        "메커니즘": r["loss_mech"],
        "비고": LIT[r["key"]]["notes"],
    } for r in results])
    st.dataframe(loss_df, use_container_width=True, hide_index=True)

    st.info(
        "📌 **CaL의 30 kg/tCO₂**는 makeup limestone 다량 투입(저비용·다소비) 특성. "
        "**TSA의 2 kg/tCO₂**는 attrition + 사이클 열화 누적 환산값."
    )

# ---------- ⑤ 트렌드 ----------
with tab5:
    st.markdown("### SRD vs We 산포도 — 문헌 회귀")
    st.caption("선택된 기술 + LIT 전체 데이터의 회귀선.")

    all_pts = []
    for k, t in LIT.items():
        we = calc_We(t, T_cool_C, p_final_bar)
        all_pts.append({
            "name": t["name"],
            "short": SHORT_NAMES.get(k, t["name"]),
            "SRD": t["SRD"],
            "We_elec": we["We_elec"], "We_total": we["We_total"],
            "category": t["category"], "is_pilot": t["is_pilot"],
            "selected": k in selected,
        })
    pts_df = pd.DataFrame(all_pts)

    z = np.polyfit(pts_df["SRD"], pts_df["We_total"], 1)
    x_fit = np.linspace(pts_df["SRD"].min() * 0.9, pts_df["SRD"].max() * 1.1, 50)
    y_fit = np.polyval(z, x_fit)

    f = go.Figure()
    for cat in pts_df["category"].unique():
        sub = pts_df[pts_df["category"] == cat]
        f.add_trace(go.Scatter(
            x=sub["SRD"], y=sub["We_total"],
            mode="markers+text",
            text=sub["short"], textposition="top center",
            customdata=sub["name"],
            hovertemplate="<b>%{customdata}</b><br>SRD: %{x:.2f}<br>We: %{y:.2f}<extra></extra>",
            name=cat,
            marker=dict(
                size=[18 if s else 12 for s in sub["selected"]],
                line=dict(width=[3 if s else 1 for s in sub["selected"]],
                          color="white"),
                symbol=["diamond" if p else "circle" for p in sub["is_pilot"]],
            ),
        ))
    f.add_trace(go.Scatter(
        x=x_fit, y=y_fit, mode="lines",
        line=dict(color="#ffc107", dash="dash"),
        name=f"회귀: We = {z[0]:.3f}·SRD + {z[1]:.3f}",
    ))
    f.update_layout(
        template="plotly_dark", height=520,
        xaxis_title="SRD [GJ/tCO₂]", yaxis_title="We 총합 [GJe/tCO₂]",
    )
    st.plotly_chart(f, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("**해석:** 회귀선 아래에 위치하면 동일 SRD 대비 보조전력이 효율적인 기술입니다.")

# ---------- ⑥ Custom 입력 ----------
with tab6:
    st.markdown("### Custom 기술 입력")
    st.caption("실증 데이터·신규 흡수제를 직접 입력해 비교에 추가할 수 있습니다.")

    with st.form("custom_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("기술명", value="My Custom Solvent")
            category = st.selectbox("분류",
                ["Amine", "Hot Carbonate", "Chilled NH₃", "Biphasic",
                 "Solid Sorbent", "CaO/CaCO₃", "Other"])
            srd = st.number_input("SRD [GJ/tCO₂]", 1.0, 5.0, 2.5, 0.05)
            T_regen = st.number_input("재생 온도 [°C]", 80, 950, 120)
            T_abs = st.number_input("흡수 온도 [°C]", 0, 700, 40)
        with c2:
            we_pump = st.number_input("We_pump [GJe/tCO₂]", 0.0, 0.1, 0.015, 0.001, format="%.3f")
            we_comp = st.number_input("We_comp [GJe/tCO₂]", 0.05, 0.6, 0.40, 0.01)
            we_chill = st.number_input("We_chill [GJe/tCO₂]", 0.0, 0.5, 0.0, 0.01)
            we_aux = st.number_input("We_aux [GJe/tCO₂]", 0.0, 0.3, 0.05, 0.01)
        with c3:
            capex = st.number_input("CAPEX [USD/(t/yr)]", 500, 3000, 1100, 50, format="%d")
            opex_sol = st.number_input("OPEX 용매 [USD/tCO₂]", 0.0, 5.0, 1.5, 0.1)
            opex_oth = st.number_input("OPEX 기타 [USD/tCO₂]", 5.0, 25.0, 12.0, 0.5)
            loss = st.number_input("손실 [kg/tCO₂]", 0.0, 50.0, 1.0, 0.1)
            p_regen = st.number_input("재생 압력 [bar]", 1.0, 30.0, 1.8, 0.1)

        submit = st.form_submit_button("계산 ▶")

    if submit:
        custom = {
            "name": name, "category": category, "SRD": srd,
            "T_regen": T_regen, "T_abs": T_abs, "p_regen_bar": p_regen,
            "We_pump": we_pump, "We_comp": we_comp,
            "We_chill": we_chill, "We_aux": we_aux,
            "CAPEX_per_t": capex, "OPEX_solvent": opex_sol,
            "OPEX_other": opex_oth, "loss_kg_per_tCO2": loss,
            "loss_mech": "사용자 정의", "is_pilot": True,
        }
        we = calc_We(custom, T_cool_C, p_final_bar, capture_t_yr=capture_t_yr)
        # 규모 보정된 SRD 사용 (다른 기술과 동일한 방식)
        specca = calc_SPECCA(we["SRD_scaled"], we["We_elec"], capture_eff)
        cost = calc_COCA(capex, opex_sol, opex_oth, we["We_elec"],
                         capture_t_yr, lifetime, discount, elec_price)

        st.success(f"✅ **{name}** 계산 완료")
        c = st.columns(4)
        c[0].metric("SRD", f"{srd:,.2f} GJ/tCO₂")
        c[1].metric("We 총합", f"{we['We_total']:,.3f} GJe/tCO₂")
        c[2].metric("SPECCA", f"{specca:,.0f} MJ/tCO₂")
        c[3].metric("COCA", f"{cost['COCA']:,.1f} USD/tCO₂")

        comp_df = pd.DataFrame([
            {"기술": r["name"], "SRD": r["SRD"], "We_total": r["We_total"],
             "SPECCA": r["SPECCA"], "COCA": r["COCA"]}
            for r in results
        ] + [{"기술": f"⭐ {name} (Custom)", "SRD": srd,
              "We_total": we["We_total"], "SPECCA": specca, "COCA": cost["COCA"]}])
        for col_ in ["SRD", "We_total"]:
            comp_df[col_] = comp_df[col_].map(lambda x: f"{x:,.2f}")
        comp_df["SPECCA"] = comp_df["SPECCA"].map(lambda x: f"{x:,.0f}")
        comp_df["COCA"] = comp_df["COCA"].map(lambda x: f"{x:,.1f}")
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

# ---------- ⑦ 참고문헌 ----------
with tab7:
    st.markdown("### 📚 참고문헌 및 계산 근거 (Full Audit Trail)")
    st.caption(f"총 {len(REFS)}개 출처 — 각 LIT 수치, 계산식, 경제성 가정의 근거")

    cat_labels = {
        "report": "📄 정부·국제기구 보고서",
        "paper": "📑 학술 논문 (Peer-reviewed)",
        "methodology": "🔧 방법론 · 교과서 · 표준",
    }

    for cat_key, cat_label in cat_labels.items():
        st.markdown(f"#### {cat_label}")
        cat_refs = [(k, v) for k, v in REFS.items() if v["cat"] == cat_key]
        for k, r in cat_refs:
            url_md = f" 🔗 [link]({r['url']})" if r["url"] else ""
            st.markdown(
                f"<div style='background:#1E2128; padding:8px 12px; margin:6px 0; "
                f"border-left:3px solid #4FC3F7; border-radius:4px;'>"
                f"<b style='color:#4FC3F7;'>[{k}]</b>{url_md}<br>"
                f"<span style='font-size:0.85rem; color:#E8EAED;'>{r['cite']}</span><br>"
                f"<span style='font-size:0.78rem; color:#8b95a7;'>"
                f"<b>사용처:</b> {r['used_for']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown("")

    st.markdown("---")
    st.markdown("### 🧪 기술별 LIT 수치의 출처 매핑")

    map_rows = []
    for k, t in LIT.items():
        ref_ids = LIT_REFS.get(k, [])
        ref_str = ", ".join(f"[{r}]" for r in ref_ids) if ref_ids else "—"
        map_rows.append({
            "기술": t["name"],
            "SRD [GJ/tCO₂]": f"{t['SRD']:,.2f}",
            "CAPEX [USD/(t/yr)]": f"{t['CAPEX_per_t']:,}",
            "손실 [kg/tCO₂]": f"{t['loss_kg_per_tCO2']:,.1f}",
            "출처 ID": ref_str,
        })
    st.dataframe(pd.DataFrame(map_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 🧮 계산식 ↔ 출처 매핑")

    formula_rows = []
    for formula, ref_ids in FORMULA_REFS.items():
        formula_rows.append({
            "수식 / 가정": formula,
            "출처": ", ".join(f"[{r}]" for r in ref_ids),
        })
    st.dataframe(pd.DataFrame(formula_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📐 지표 정의 (수식 정리)")
    st.code("""
[열역학 1차]
  Carnot η = (T_h - T_c) / T_h          [Bejan2016]
  실효 η   = Carnot η × 0.55             [Kotas1985]

[전력등가 일]
  We_thermal_eq = SRD × Carnot η × 0.55
  We_pump   = LIT 고정값
  We_comp   = LIT × log(p_final / p_regen) / log(152 / 1.8)   [Aspen_NETL, Romeo2008]
  We_chill  = Q_chill / COP_eff (CAP만 동적)                    [ASHRAE_HVAC]
  We_total  = We_thermal_eq + We_pump + We_comp + We_chill + We_aux

[2차 지표]
  SPECCA = (SRD × 500 + We_elec × 2,500) / capture              [Manzolini2015 변형]

[경제성]
  CRF      = i(1+i)^n / [(1+i)^n - 1]                          [NETL_QGESS]
  연환산 CAPEX = CAPEX × CRF
  COCA     = 연환산 CAPEX + OPEX

[CAP 냉동기]
  COP_Carnot = T_abs / (T_amb - T_abs)                          [ASHRAE_HVAC]
  COP_eff    = COP_Carnot × 0.55
  Q_chill    = SRD × 0.18                                        [NETL_Rev4a]
""", language="python")

    st.markdown("---")
    st.markdown("### 🎯 데이터 신뢰도 (Quality Tier)")

    tier_data = pd.DataFrame([
        {"기술": LIT["MEA_baseline"]["name"], "Tier": "A — 상용",
         "기준": "다수 상용 플랜트 운영", "불확실성": "± 5%"},
        {"기술": LIT["CAP_B12C"]["name"], "Tier": "A — Demo",
         "기준": "AEP Mountaineer demo + NETL 케이스", "불확실성": "± 10%"},
        {"기술": LIT["CaL"]["name"], "Tier": "B — Demo",
         "기준": "1.7 MWe La Pereda 파일럿", "불확실성": "± 15%"},
        {"기술": LIT["TSA_Solid"]["name"], "Tier": "B — Demo",
         "기준": "DOE 0.5~1 MWe 파일럿", "불확실성": "± 20%"},
        {"기술": LIT["K2CO3_KIERSOL"]["name"] + " †", "Tier": "C — Pilot",
         "기준": "KIER 0.5 MWe 파일럿", "불확실성": "± 25%"},
        {"기술": LIT["Biphasic_DMX"]["name"] + " †", "Tier": "C — Pilot",
         "기준": "Dunkirk 0.5 t/h 파일럿", "불확실성": "± 25%"},
    ])
    st.dataframe(tier_data, use_container_width=True, hide_index=True)

    st.warning(
        "⚠️ 본 툴의 수치는 공개 보고서 기반 *representative values*. "
        "Tier C(파일럿 †) 데이터는 ±25% 이상 변동 가능. "
        "실제 프로젝트는 EPC 견적·실증 데이터로 보정 필요."
    )

# ---------- ⑧ 방법론 ----------
with tab8:
    st.markdown("### 🔬 방법론 / 추정 근거 (Methodology)")
    st.caption("본 툴의 모든 수치·수식·가정의 근거. 자료 신뢰도 검증·peer review용.")

    # ── 1. 기준 ──
    with st.expander("📌 **1. 기준 플랜트 & Data Base**", expanded=True):
        st.markdown("""
**기준 플랜트** (Reference Case)
- **Source**: NETL Rev4a Case B12C / NETL 2022 Baseline B12B
- **Plant Type**: 555 MWe net Subcritical PC + Post-Combustion Capture
- **Coal**: Illinois No. 6 Bituminous
- **Capture rate**: 90%
- **Annual capture**: ~3.7 MtCO₂/yr (capacity factor 85%)
- **Cost basis year**: 2018~2022 USD (no inflation adjustment)
- **Location**: US Midwest (NETL standard)

**LIT 데이터 hierarchy**

| 기술 | 1차 출처 | 보조 출처 | Tier |
|---|---|---|---|
| MEA | NETL Rev4a B12B (3.6 GJ/t) | Bui 2018, Rochelle 2009 | A — 상용 (±5%) |
| K₂CO₃/KIERSOL | KIER 파일럿 보고서 | Yoo 2013, Cullinane 2004 | C — Pilot (±25%) |
| CAP | NETL Rev4a B12C | Darde 2010, Telikapalli 2011 | A — Demo (±10%) |
| Biphasic DMX | 3D Project (TotalEnergies) | Raynal 2011 | C — Pilot (±25%) |
| TSA | DOE NETL Sorbent Program | Sjostrom & Krutka 2010 | B — Demo (±20%) |
| CaL | IEAGHG 2013/19 + Hanak 2015 | Abanades 2002, Grasa 2006 | B — Demo (±15%) |

**왜 NETL B12C가 기준?**
NETL Cost & Performance Baseline은 미 정부가 30년+ 유지·검증해온 표준 reference case로,
- 모든 case의 가정·전제가 동일하게 정규화됨 → 기술 간 직접 비교 가능
- 공식 cost methodology (QGESS) 적용
- 외부 peer review 거침
- 후속 연구에서 가장 빈번히 인용
        """)

    # ── 2. KPI별 ──
    with st.expander("🎯 **2. 4대 KPI 계산 근거 (SRD · We · SPECCA · COCA)**"):
        st.markdown(r"""
**SRD (Specific Reboiler Duty)**
- **정의**: 흡수제 재생탑 reboiler가 단위 CO₂당 공급해야 하는 열에너지
- **단위**: GJ thermal / tCO₂
- **출처값**: NETL B12B (Cansolv DC-103, 3.56 GJ/t) ≈ MEA 30% 기준 3.6 (compatible)
- **물리적 분해**:
  - Heat of desorption: ~1.8 GJ/t (열역학 limit)
  - Sensible heat (rich solvent → 재생): ~0.9 GJ/t
  - Stripping vapor: ~0.9 GJ/t
  - **합계 ≈ 3.6 GJ/t** (이론 + 실제 손실)

**We (Equivalent Work)**
- **정의**: 모든 에너지 입력을 전기 등가로 환산 [GJe / tCO₂]
- **분해**:
  - `We_thermal_eq` = SRD × Carnot × 0.55  (Bejan 2016, Kotas 1985)
  - `We_pump`      : LIT 고정값 (rich solvent pumping)
  - `We_comp`      : LIT × log(p_final/p_regen) / log(152/1.8)  (Aspen/NETL)
  - `We_chill`     : Q_chill / COP_eff (CAP만 동적, ASHRAE)
  - `We_aux`       : LIT 고정값 (보조)

**SPECCA (Specific Primary Energy Consumption for CO₂ Avoided)**
- **사용자 정의식**: SPECCA = (SRD × 500 + We_elec × 2,500) / capture
- 출처: Manzolini 2015 변형 (원본은 reference plant heat rate 차이로 산출)
- 가중치 500/2500: 기존 아민툴과 호환 위해 유지 (비교 일관성 ↑)

**COCA (Cost Of CO₂ Captured)**
- **공식**: COCA = (연환산 CAPEX + OPEX) / 연 포집량
- **연환산 CAPEX** = CAPEX × CRF, where CRF = i(1+i)ⁿ / [(1+i)ⁿ−1]
- **default**: i=8%, n=25 → CRF = 0.0937
- **OPEX**: 용매·기타·전력 합산
        """)

    # ── 3. 규모 효과 ──
    with st.expander("📐 **3. 규모 효과 — CCS 특화 스케일링** ⭐ 핵심"):
        st.markdown(rf"""
**왜 CCS 특화 스케일이 필요한가**
일반 화공의 Lang's six-tenths rule (n=0.6~0.7)은 광범위한 화공 평균값입니다.
CCS는 다음 특성으로 별도의 calibration이 필요:
- 거대 absorber/stripper column 비중 ↑ (n ≈ 0.65)
- 다단 압축기 비중 ↑ (n ≈ 0.67)
- Power island 통합 효과 (n ≈ 0.7)
- Composite total: **n ≈ 0.65** (IEAGHG 2007, NETL QGESS)

**CAPEX 스케일링 (n = 0.65)**
$$\text{{CAPEX/t}}_\text{{actual}} = \text{{CAPEX/t}}_\text{{ref}} \times \left(\frac{{3.7}}{{\text{{actual}}\ \text{{[Mt/yr]}}}}\right)^{{0.35}}$$
- 출처: IEAGHG 2007 (CCS plant scaling), NETL QGESS 2019
- 0.5 Mt → +85% / 1 Mt → +48% / 3.7 Mt → 0% / 10 Mt → −29% / 20 Mt → −45%

**SRD 스케일링 (±10%/decade)**
$$\text{{SRD}}(\text{{scale}}) = \text{{SRD}}_\text{{ref}} \times \left[1 + 0.10 \times \log_{{10}}\left(\frac{{\text{{scale}}}}{{3.7}}\right)\right]$$
clip to ±15%
- 출처: **IEAGHG 2013/06 Solvent R&D Priorities**
- 메커니즘: 파일럿(idealized) → 상용 +10~15%
  - 큰 stripper → 압력 강하 ↑
  - 큰 reboiler → LMTD 손실 ↑
  - Startup/shutdown inefficiencies
  - Heat integration 한계 (real plant heat exchanger network)

**We_comp 스케일링 (±6%/decade, 반대 방향)**
$$\text{{We}}_\text{{comp}}(\text{{scale}}) = \text{{We}}_\text{{comp,ref}} \times \left[1 + 0.06 \times \log_{{10}}\left(\frac{{3.7}}{{\text{{scale}}}}\right)\right]$$
- 출처: **NETL Rev3/4** (Aspen Plus 압축기 모델), **GPSA Engineering Data Book** (효율 표준), **IEAGHG 2014/TR4**
- 메커니즘: 소형(왕복식 η~75%) → 대형(다단 원심+intercool η~85%)
- 1 Mt → +3.4% / 3.7 Mt → 0 / 10 Mt → −2.6%

**현재 운전 조건 보정 요약**: 사이드바 포집량 입력 아래에 자동 표시
        """)

    # ── 4. CCU 정제 ──
    with st.expander("🥤 **4. CCU 정제 등급별 (수율·가격·CAPEX) 추정**"):
        st.markdown(r"""
**3단계 등급 (CGA G-6.2 + SEMI C3 표준)**

| 등급 | 순도 | 수율 | 판매가 (KRW/t) | CAPEX adder | 공정 |
|---|---|---|---|---|---|
| 식품·음료급 | 99.9% | **88%** | 250k~400k (default 300k) | +5% | 활성탄 흡착 + 분자체 |
| 고순도 | 99.99% | **82%** | 350k~550k (default 450k) | +25% | + 증류 컬럼 1단 |
| 초고순도 | 99.999% | **75%** | 600k~800k (default 700k) | +65% | + 극저온 증류 |

**수율 감소 메커니즘**: 정제 순도 ↑ → off-gas vent 비율 ↑
- 99.9%: 약 12% 손실 (light gas + 미량 불순물)
- 99.99%: 추가 6% 손실 (high-boiling impurities)
- 99.999%: 추가 7% 손실 (cryogenic distillation tails)

**CAPEX adder 모델**
$$\text{{CAPEX}}_\text{{eff}} = \text{{CAPEX}}_\text{{base}} \times [1 + \text{{ccu\_share}} \times (\text{{capex\_mult}} - 1)]$$
- 출처: Linde / Air Liquide industrial gas plant sizing, CGA standards

**가격 source**: Linde Industrial Gas Korea, Air Liquide Korea, 한국가스공사 액화탄산 시장 (2020~2023)
        """)

    # ── 5. CCS 격리 수율 ──
    with st.expander("🏔️ **5. CCS 격리 수율 92% 분해 근거**"):
        st.markdown(r"""
**포집 → 격리 chain의 단계별 손실 (default 92% 누적 수율)**

| 단계 | 손실률 | 누적 수율 | 출처 |
|---|---|---|---|
| 흡수제 재생 (포집점) | base 100% | 100% | reference |
| Dehydration (TEG/molecular sieve) | -0.5% | 99.5% | IPCC SRCCS Ch5 |
| 다단 압축 (5~7단) | -1.0% | 98.5% | NETL Aspen, GPSA |
| 파이프라인 수송 (50~200km) | -1.5% | 97.0% | IPCC SRCCS Ch5 |
| Wellhead 주입 (시동 vent) | -1.0% | 96.0% | Global CCS Inst. 2023 |
| Long-term leakage rate | -4% (보수적) | **92.0%** | IPCC AR6 WG3 |

**default 92% 선정 근거**: NETL/Global CCS Institute 운영 데이터 평균 (Boundary Dam, Quest, Petra Nova 등)

**조정 가능 범위**: 80~99% (사용자 입력)
- 80%: pilot scale 또는 노후 인프라
- 92%: 표준 commercial (default)
- 98%: 최신 dedicated injection (saline aquifer)

출처: **IPCC SRCCS Ch5**, **IPCC AR6 WG3**, **Global CCS Institute Status 2023**
        """)

    # ── 6. 경제성 가정 ──
    with st.expander("💰 **6. 경제성 가정 (CRF, 할인율, 전기·배출권 가격)**"):
        st.markdown(rf"""
**CRF (Capital Recovery Factor)**
$$\text{{CRF}} = \frac{{i(1+i)^n}}{{(1+i)^n - 1}}$$
- default i = 8%, n = 25 → CRF = 0.0937 (9.37%/yr)
- 출처: **NETL QGESS 2019** Standard

**전기 가격 (default $80/MWh)**
- US 산업 평균: 75~95 USD/MWh (EIA AEO 2024)
- 한국 산업: ≈ 110~130 USD/MWh (한전 산업용)
- EU: ≈ 100~150 USD/MWh
- 출처: **EIA AEO 2024**, **IEA Energy Prices 2023**

**탄소시장 가격 (모든 default, 2024 평균)**

| 시장 | Default ($USD/t) | 환산 | 변동성 | 출처 |
|---|---|---|---|---|
| K-ETS | 7 | 10,000 KRW/t | 高 (5~15) | KRX 2024 |
| EU ETS | 80 | €75 | 中 (60~100) | ICE 2024 |
| RGGI (US east) | 20 | — | 低 | RGGI Inc. 2024 |
| CA Cap-Trade | 30 | — | 低 | CARB 2024 |

**보조금 (정부 인센티브)**

| 제도 | Default | 조건 | 출처 |
|---|---|---|---|
| US 45Q-CCS | $85/t | 12yr, 75%+ capture | IRS Notice 2022-38 (IRA) |
| US 45Q-EOR | $60/t | 12yr | IRS Notice 2022-38 |
| US 45Q-DAC | $180/t | 12yr | IRS Notice 2022-38 |
| NL SDE++ | $120/t (€110) | CfD 12~15yr | RVO Netherlands 2024 |
| UK CCUS CfD | $180/t (£150) | Track 1/2 cluster | UK BEIS 2023 |
| K-CCUS Act | $21/t (placeholder) | 시행령 미정 | 산업부 2024 |

**환율**: default 1,400 KRW/USD (2026.4 기준, 사용자 조정 가능)
        """)

    # ── 7. CAP 냉동기 ──
    with st.expander("🧊 **7. CAP 냉동기 (Carnot COP × 0.55) 모델**"):
        st.markdown(r"""
**왜 CAP만 냉동기 모델이 동적인가**
다른 기술은 흡수탑이 상온 운전 (40~70°C)이라 외기/냉각수로 충분.
**CAP은 0~10°C 흡수**로 냉동 사이클 (NH₃ slip 방지) 필수.

**모델**
1. 냉각 부하 추정: $Q_\text{chill} = \text{SRD} \times 0.18$
   - 출처: **NETL Rev4a B12C 보조전력 분석** (실제 측정값에서 SRD 대비 0.16~0.20 fraction)
   - 휴리스틱이지만 NETL 공식 케이스에 직접 부합

2. 역카르노 COP 계산:
   $$\text{COP}_\text{Carnot} = \frac{T_\text{abs}}{T_\text{amb} - T_\text{abs}}$$
   - 응축기 ΔT 마진 +10°C 가정 (실 운영 표준)

3. 실효 COP = COP_Carnot × 0.55 (second-law factor)
   - 출처: **ASHRAE Handbook (2020)**, real chiller efficiency 0.5~0.6 of Carnot

4. We_chill = Q_chill / COP_eff

**검증**: 냉각수 25°C일 때 We_chill ≈ 0.18 GJe/tCO₂ → NETL B12C 보조전력 분해와 일치
        """)

    # ── 8. 압축 ──
    with st.expander("⚙️ **8. CO₂ 압축 일 — Log-pressure 모델**"):
        st.markdown(r"""
**모델**
$$\text{We}_\text{comp}(\text{p}) = \text{We}_\text{comp,LIT} \times \frac{\log(p_\text{final}/p_\text{regen})}{\log(152/1.8)}$$
floor 0.3 (부분 압축 시에도 최소 손실)

**근거**:
- 5단 압축 + 4단 intercooling 가정 (NETL Aspen 표준)
- 단단 등엔트로픽 일: $W = \frac{\gamma}{\gamma-1} R T_\text{in} [(p_\text{out}/p_\text{in})^{(\gamma-1)/\gamma} - 1]$
- 다단 + intercooling 시 ≈ $n \cdot \log(p_\text{out}/p_\text{in})$ 비례 (이론)
- 압축기 효율: 소형(왕복) 75% / 대형(원심) 85% (GPSA Section 13)

**최종 압력별 사용 시나리오**:

| 압력 | 용도 | We_comp 배율 |
|---|---|---|
| 5 bar | 액화탄산 (식품) | × 0.3 (floor) |
| 25 bar | 액화탄산 (산업) | × 0.59 |
| 100 bar | 파이프라인 | × 0.91 |
| 152 bar | EOR (NETL 표준) | × 1.00 |
| 200 bar | 지중저장 (deep saline) | × 1.06 |

출처: **NETL Aspen Plus 압축 모델**, **Romeo et al. 2008**, **GPSA 2017**
        """)

    # ── 9. 손실 ──
    with st.expander("📉 **9. 흡수제·흡착제 손실 추정**"):
        st.markdown("""
| 기술 | 손실 (kg/tCO₂) | 메커니즘 | 출처 |
|---|---|---|---|
| MEA 30% | 1.5 | 산화·열분해, evaporation | Lepaumier 2009, IEAGHG 2014 Reclaimer Sludge |
| K₂CO₃/KIERSOL | 0.5 | 활성화제 (PZ) 열화 미량 | KIER reports, Cullinane 2004 |
| CAP (NH₃) | 0.3 | NH₃ slip (water wash 회수 후 미회수분) | Darde 2010, Telikapalli 2011 |
| Biphasic DMX | 1.0 | 용매 분해, 휘발 (mid-range vs MEA) | Raynal 2011 |
| TSA solid | 2.0 | Cycle attrition (마모) + thermal degradation | DOE NETL Sorbent Program, Sjostrom & Krutka 2010 |
| CaL | 30 | CaO sintering → makeup limestone (저비용 다소비) | Grasa 2006, Hanak 2015 |

**주의**: TSA의 2 kg/t는 cycle 수에 따라 환산값. 실제 sorbent attrition은 0.5~5%/cycle 범위 (DOE NETL R&D).
**CaL의 30 kg/t**는 다른 기술과 비교 시 단순 정량 비교 부적절 — 재료 비용도 별도 고려.
        """)

    # ── 10. Walk-through ──
    with st.expander("✅ **10. 검증 — MEA 단일 케이스 계산 walk-through**"):
        st.markdown(r"""
**조건**: MEA 30 wt%, 1 MtCO₂/yr, 25°C 냉각수, 152 bar 출력, CCS 모드, 92% yield, 45Q-CCS

**Step 1**: 규모 보정
- log_ratio = log10(1.0 / 3.7) = −0.568
- SRD: 3.60 × (1 + 0.10 × (−0.568)) = 3.60 × 0.943 = **3.40 GJ/t**
- We_comp: 0.40 × (1 + 0.06 × 0.568) = 0.40 × 1.034 = **0.414 GJe/t**

**Step 2**: We 분해
- η_Carnot = (120 − 25) / (120 + 273.15) = 0.242
- η_eff = 0.242 × 0.55 = 0.133
- We_thermal_eq = 3.40 × 0.133 = **0.452 GJe/t**
- p_factor = log(152/1.8) / log(152/1.8) = 1.0
- We_comp_eff = 0.414 × 1.0 = 0.414
- We_chill = 0 (MEA)
- We_pump = 0.012, We_aux = 0.05
- **We_elec = 0.012 + 0.414 + 0 + 0.05 = 0.476 GJe/t**
- **We_total = 0.452 + 0.476 = 0.928 GJe/t**

**Step 3**: SPECCA
- (3.40 × 500 + 0.476 × 2,500) / 0.90 = (1,700 + 1,190) / 0.90 = **3,211 MJ/t**

**Step 4**: COCA
- CAPEX/t scaled: 950 × (3.7/1)^0.35 = 950 × 1.55 = **1,470 USD/(t/yr)**
- 연환산 CAPEX = 1,470 × 0.0937 = **137.7 USD/t**
- 전력비 = 0.476 × 277.78/1000 × 80 = **10.6 USD/t**
- OPEX_solvent = 1.5, OPEX_other = 12.0
- **COCA = 137.7 + 1.5 + 12.0 + 10.6 = 161.8 USD/t**

**Step 5**: 매출/Net COCA (45Q-CCS $85/t)
- stored_t = 1.0 × 1.0 × 0.92 = 0.92 Mt
- subsidy = 0.92e6 × 85 = $78.2M/yr
- rev/capture = $78.2M / 1.0Mt = $78.2/t
- **Net COCA = 161.8 − 78.2 = $83.6/t**

**Step 6**: 연간 손익
- 연 비용 = 161.8 × 1.0e6 = $161.8M/yr
- 연 매출 = $78.2M/yr (보조금만)
- **연 손익 = +$78.2M − $161.8M = −$83.6M/yr** (적자, 약 −1,170억원/yr)

→ MEA를 1 Mt 작은 플랜트로 짓고 45Q-CCS만 받으면 적자. 더 큰 플랜트(scale ↑) 또는 더 강한 인센티브 필요.
        """)

    # ── 11. 한계 ──
    with st.expander("⚠️ **11. 모델의 한계 & 미반영 항목**"):
        st.markdown("""
**모델이 다루지 않는 것**

| 항목 | 영향 | 보완 방법 |
|---|---|---|
| Variable load operation | ±5~10% efficiency | 현장 dispatch 모델 필요 |
| Power island integration (steam extraction) | ±5% net efficiency | NETL Aspen full plant model |
| Site-specific costs (지반, 인프라) | ±20% CAPEX | EPC 견적 |
| Inflation / 환율 변동 | 시간 의존 | 매년 업데이트 |
| Permitting & regulation costs | ±5~15% CAPEX | 지역별 별도 |
| Carbon storage long-term liability | 미정량화 | 보험 + monitoring |
| CCU 시장 saturation effects | 가격 ↓ at scale | 시장 모델 |
| Solvent reclaiming costs (MEA only) | OPEX +1~3% | reclaimer 운영비 |
| Heat integration with host plant | ±10% SRD | site-specific |

**불확실성 등급 (재정리)**

| Tier | 기준 | 권장 사용 |
|---|---|---|
| **A (±5~10%)** | 다수 상용 운영 데이터 | EPC 견적 input, board materials |
| **B (±15~20%)** | Demo / 1+ MWe pilot | Concept screening, R&D priority |
| **C (±25%+)** | Pilot < 1 MWe | Trend analysis only, 단독 결정 不可 |

**📌 핵심 권고**:
- Tier A 데이터로 1차 screening
- Tier C 결과는 반드시 ±25% sensitivity 검토
- 최종 투자 결정 시 site-specific EPC 견적 필수
        """)

    st.markdown("---")
    st.info(
        "📖 **References**: 모든 출처는 탭 ⑦ 참고문헌 (총 36개) 참조. "
        "본 방법론 섹션은 자료 신뢰도 검증 (peer review) 및 sensitivity 분석 input 작성용."
    )

# ======================================================================
# 푸터
# ======================================================================
st.markdown("---")
st.caption(
    "🌫️ 비아민계 CO₂ 포집 벤치마크 v1.2 | "
    "MEA 기준선 + K₂CO₃ · CAP · Biphasic · TSA · CaL | "
    "NETL Rev4a/2022 · IEAGHG · DOE · KIER · IRS 45Q · KRX | "
    "방법론 출처: 36개"
)
