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
  streamlit run nonamine_co2_benchmark.py
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

# ======================================================================
# 기술 라이브러리 (LIT) — NETL Rev4a / IEAGHG / DOE / KIER 기반
# ======================================================================
LIT = {
    "MEA_baseline": {
        "name": "MEA 30 wt% (참고)",
        "category": "Amine (ref)",
        "source": "NETL B12B / IEAGHG 2014",
        "status": "commercial",
        "SRD": 3.60,           # GJ/tCO₂
        "T_regen": 120,         # °C
        "T_abs": 40,            # °C
        "p_regen_bar": 1.8,
        "We_pump": 0.012,       # GJe/tCO₂
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.05,
        "CAPEX_per_t": 950,     # USD/(t/yr) — annualized basis
        "OPEX_solvent": 1.5,    # USD/tCO₂
        "OPEX_other": 12.0,     # USD/tCO₂ (utility, labor, maintenance)
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
        "T_abs": 70,           # warm absorber 운전
        "p_regen_bar": 1.5,
        "We_pump": 0.025,      # 큰 L/G → 펌프 부하 ↑
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
        "T_abs": 5,            # 0~10 °C
        "p_regen_bar": 24.0,   # 가압 재생 → 압축 부하 ↓
        "We_pump": 0.018,
        "We_comp": 0.18,       # 24 → 152 bar (감소)
        "We_chill": 0.18,      # NETL B12C 평균값 (동적 보정 가능)
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
        "We_pump": 0.020,      # CO₂-rich phase만 펌핑
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
        "SRD": 2.20,           # equivalent thermal duty
        "T_regen": 110,
        "T_abs": 40,
        "p_regen_bar": 1.2,
        "We_pump": 0.005,      # 액체 순환 無
        "We_comp": 0.40,
        "We_chill": 0.00,
        "We_aux": 0.10,        # blower / fluidization
        "CAPEX_per_t": 1300,
        "OPEX_solvent": 2.5,   # sorbent attrition 비싸다
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
        "SRD": 3.20,           # 高 — 그러나 高溫 heat
        "T_regen": 900,        # calciner
        "T_abs": 650,          # carbonator
        "p_regen_bar": 1.0,
        "We_pump": 0.000,
        "We_comp": 0.36,
        "We_chill": 0.00,
        "We_aux": 0.15,        # 솔리드 핸들링 + ASU(oxy-calciner)
        "CAPEX_per_t": 850,
        "OPEX_solvent": 1.5,   # makeup limestone (싸지만 다량)
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
# - 각 LIT 수치, 모든 계산식, 경제성 가정의 출처
# - 탭 ⑦ 참고문헌에서 자동 렌더링
# ======================================================================
REFS = {
    # ────────────── 주요 보고서 (Reports) ──────────────
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

    # ────────────── 학술 논문 (Papers) ──────────────
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

    # ────────────── 방법론 / 교과서 ──────────────
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
}


def ref_link(ref_id: str, label: str = None) -> str:
    """REFS의 항목을 마크다운 링크로 변환 (인라인 인용용)"""
    if ref_id not in REFS:
        return f"[{ref_id}]"
    r = REFS[ref_id]
    text = label or ref_id
    if r["url"]:
        return f"[{text}]({r['url']})"
    return text


# ────────────── LIT 엔트리별 참조 매핑 ──────────────
LIT_REFS = {
    "MEA_baseline":    ["NETL_Rev4a", "Rochelle2009", "IEAGHG_Solvents_2014", "Lepaumier2009", "Bui2018"],
    "K2CO3_KIERSOL":   ["KIER_KIERSOL_2013", "Yoo2013", "Cullinane2004"],
    "CAP_B12C":        ["NETL_Rev4a", "Darde2010", "Telikapalli2011"],
    "Biphasic_DMX":    ["TotalEnergies_3D", "Raynal2011"],
    "TSA_Solid":       ["DOE_NETL_Sorbent_Program", "Bui2018"],
    "CaL":             ["IEAGHG_CaL_2013", "Abanades2002", "Grasa2006", "Romeo2008"],
}

# ────────────── 계산식 → REFS 매핑 ──────────────
FORMULA_REFS = {
    "Carnot 효율 η = (T_h - T_c) / T_h":              ["Bejan2016"],
    "Second-law factor 0.55":                          ["Bejan2016", "Kotas1985"],
    "역카르노 COP = T_c / (T_h - T_c) × 0.55":         ["ASHRAE_HVAC"],
    "압축 W ∝ log(p_out / p_in) (5단 + 중간냉각)":     ["Aspen_NETL", "Romeo2008"],
    "CRF = i(1+i)^n / [(1+i)^n - 1]":                 ["NETL_QGESS"],
    "할인율 8%, 수명 25년 (default)":                  ["NETL_QGESS"],
    "전기 가격 80 USD/MWh (default)":                  ["EIA_AEO_2024"],
    "SPECCA = (SRD×500 + We_elec×2500) / capture":    ["Manzolini2015"],
    "CAP 냉각부하 = SRD × 0.18 휴리스틱":               ["NETL_Rev4a", "Darde2010"],
}

# 차트용 짧은 이름 (글자 잘림 방지)
SHORT_NAMES = {
    "MEA_baseline":   "MEA",
    "K2CO3_KIERSOL":  "K₂CO₃†",
    "CAP_B12C":       "CAP",
    "Biphasic_DMX":   "DMX†",
    "TSA_Solid":      "TSA",
    "CaL":            "CaL",
}

# 기술별 흡수제·소재 (간단 표기)
MATERIALS = {
    "MEA_baseline":   "MEA 30 wt% 수용액 (HOCH₂CH₂NH₂)",
    "K2CO3_KIERSOL":  "K₂CO₃ + 활성화제 (Piperazine 등) 수용액",
    "CAP_B12C":       "NH₃ 28 wt% 수용액 (0~10 °C 냉각)",
    "Biphasic_DMX":   "3차 아민 혼합액 (DMX™, 상분리형)",
    "TSA_Solid":      "고체 흡착제 (아민 함침/제올라이트/MOF)",
    "CaL":            "CaO ⇌ CaCO₃ (석회석 기원, 고체)",
}

def short_name(key_or_name: str) -> str:
    """LIT 키 또는 풀네임 → 짧은 이름"""
    if key_or_name in SHORT_NAMES:
        return SHORT_NAMES[key_or_name]
    # name → key 역매핑
    for k, t in LIT.items():
        if t["name"] == key_or_name:
            return SHORT_NAMES.get(k, key_or_name)
    return key_or_name


# 차트 공통 마진 (한글 라벨 잘림 방지용 충분한 bottom)
CHART_MARGIN = dict(l=10, r=10, t=50, b=80)
CHART_MARGIN_STACK = dict(l=10, r=10, t=50, b=120)  # legend가 아래 있을 때

# ======================================================================
# 계산 함수
# ======================================================================
def carnot_efficiency(T_hot_C: float, T_cold_C: float) -> float:
    """Carnot 효율 (절대온도 기준)"""
    Th = T_hot_C + 273.15
    Tc = T_cold_C + 273.15
    if Th <= Tc:
        return 0.0
    return (Th - Tc) / Th


def chiller_We(Q_chill_GJ: float, T_abs_C: float, T_amb_C: float) -> float:
    """
    흡수탑 냉각 부하 → 냉동기 전기 일.
    역카르노 COP_max = T_cold / (T_hot - T_cold), 실효 COP = ETA_CARNOT_FRAC × COP_max.
    Q_chill_GJ : 단위 CO₂당 냉각열 [GJ/tCO₂]
    """
    Tc = T_abs_C + 273.15
    Th = T_amb_C + 273.15 + 10  # 응축기 ΔT 마진
    if Th <= Tc:
        return 0.0
    cop_carnot = Tc / (Th - Tc)
    cop_eff = max(cop_carnot * ETA_CARNOT_FRAC, 1.0)
    return Q_chill_GJ / cop_eff


def calc_We(tech: dict, T_cool_C: float, p_final_bar: float) -> dict:
    """
    총 전력등가 일 We [GJe/tCO₂] 분해.
    - We_thermal_eq : SRD를 Carnot로 전기등가 환산
    - We_elec       : 펌프 + 압축(목표압 보정) + 냉동기(동적) + 보조
    """
    # 1) 열의 전기등가 (참고용) — Carnot × second-law factor
    eta_c = carnot_efficiency(tech["T_regen"], T_cool_C) * ETA_CARNOT_FRAC
    We_thermal_eq = tech["SRD"] * eta_c  # GJe/tCO₂

    # 2) 압축 보정 (가압 재생이면 압축 부하 ↓ — 이미 LIT에 반영됨, 최종 압력 보정만)
    base_p = 152.0
    # log-pressure scaling (간단 모델)
    p_factor = np.log(p_final_bar / tech["p_regen_bar"]) / np.log(base_p / 1.8)
    p_factor = max(p_factor, 0.3)
    we_comp_eff = tech["We_comp"] * p_factor

    # 3) 냉동기 — CAP만 동적, 그 외 LIT 값 사용
    if tech["category"] == "Chilled NH₃":
        # 냉각 부하 ≈ SRD × 0.18 가정 (NETL B12C 평균)
        Q_chill = tech["SRD"] * 0.18
        we_chill_eff = chiller_We(Q_chill, tech["T_abs"], T_cool_C)
    else:
        we_chill_eff = tech.get("We_chill", 0.0)

    we_pump = tech["We_pump"]
    we_aux = tech["We_aux"]

    We_elec = we_pump + we_comp_eff + we_chill_eff + we_aux
    We_total = We_thermal_eq + We_elec

    return {
        "We_thermal_eq": We_thermal_eq,
        "We_pump": we_pump,
        "We_comp": we_comp_eff,
        "We_chill": we_chill_eff,
        "We_aux": we_aux,
        "We_elec": We_elec,
        "We_total": We_total,
    }


def calc_SPECCA(srd: float, we_elec: float, capture: float) -> float:
    """
    SPECCA [MJ/tCO₂] = (SRD×500 + We_elec×2500) / capture
    (사용자 정의식 — 아민 툴과 동일)
    """
    if capture <= 0:
        return float("nan")
    return (srd * SRD_TO_SPECCA + we_elec * WE_TO_SPECCA) / capture


def calc_COCA(
    capex_per_t: float,
    opex_solvent: float,
    opex_other: float,
    we_elec: float,
    capture_t_yr: float,
    lifetime_yr: int = 25,
    discount: float = 0.08,
    elec_price_usd_mwh: float = USD_PER_MWH_GRID,
) -> dict:
    """
    COCA [USD/tCO₂] = (연간 CAPEX + OPEX) / 연간 CO₂ 포집량
    - capex_per_t : USD/(t/yr) 기준
    - opex 항목 : USD/tCO₂
    - We_elec → 전기 비용 USD/tCO₂ 환산 (1 GJ = 277.78 kWh)
    """
    crf = (discount * (1 + discount) ** lifetime_yr) / ((1 + discount) ** lifetime_yr - 1)
    annual_capex_usd_per_t = capex_per_t * crf  # USD/tCO₂
    elec_cost = we_elec * 277.78 / 1000 * elec_price_usd_mwh  # GJ→MWh 환산
    opex_total = opex_solvent + opex_other + elec_cost
    coca = annual_capex_usd_per_t + opex_total
    return {
        "annual_capex": annual_capex_usd_per_t,
        "opex_solvent": opex_solvent,
        "opex_other": opex_other,
        "elec_cost": elec_cost,
        "opex_total": opex_total,
        "COCA": coca,
        "annual_total_usd": coca * capture_t_yr,
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
        help="NETL B12C 기준값 ≈ 3.7 Mt/yr · default: 3.7",
    )
    capture_t_yr = capture_mt_yr * 1e6

    capture_eff_pct = st.number_input(
        "포집율 [%]",
        min_value=50, max_value=99, value=90, step=1,
        help="default: 90",
    )
    capture_eff = capture_eff_pct / 100.0

    T_cool_C = st.number_input(
        "냉각수 온도 [°C]",
        min_value=0, max_value=50, value=25, step=1,
        help="콘덴서·냉각탑 공급 냉각수 · default: 25 (CAP 냉동기 부하에 직접 영향)",
    )

    p_final_bar = st.number_input(
        "CO₂ 최종 압력 [bar]",
        min_value=5, max_value=300, value=152, step=1,
        help=(
            "용도별 권장값:\n"
            "• 식품·음료 액화탄산: 15~20 bar\n"
            "• 산업용 액체 CO₂: 5~25 bar\n"
            "• 드라이아이스: 5~10 bar\n"
            "• 파이프라인 수송: 100~150 bar\n"
            "• EOR / 지중저장: 150~200 bar\n"
            "default: 152 (NETL 초임계 표준)"
        ),
    )

    # 압력대별 end-use 라벨 자동 표시
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

    lifetime = st.number_input(
        "플랜트 수명 [년]",
        min_value=10, max_value=50, value=25, step=1,
        help="default: 25",
    )
    discount_pct = st.number_input(
        "할인율 [%]",
        min_value=2.0, max_value=15.0, value=8.0, step=0.5,
        format="%.1f",
        help="default: 8.0",
    )
    discount = discount_pct / 100.0

    elec_price = st.number_input(
        "전기 가격 [USD/MWh]",
        min_value=20, max_value=300, value=80, step=5,
        help="default: 80 (US grid 평균)",
    )

    st.markdown("---")
    st.caption(
        "**†** 마크는 파일럿/실증 단계 데이터.<br>"
        "데이터 소스: NETL Rev4a, IEAGHG, DOE, KIER",
        unsafe_allow_html=True,
    )

# ======================================================================
# 헤더
# ======================================================================
st.title("🌫️ 비아민계 CO₂ 포집 흡수제 기술 벤치마크")
st.caption(
    "NETL Rev4a B12C · IEAGHG · DOE NETL · KIER KIERSOL 기반 | "
    "MEA 30 wt%(아민) 비교 기준선 포함"
)

if not selected:
    st.warning("⚠️ 사이드바에서 비교할 기술을 1개 이상 선택해주세요.")
    st.stop()

# 파일럿 경고 배너
pilot_techs = [LIT[k]["name"] for k in selected if LIT[k]["is_pilot"]]
if pilot_techs:
    st.markdown(
        f"<div class='pilot-warning'>⚠️ <strong>파일럿/실증 데이터 포함:</strong> "
        f"{', '.join(pilot_techs)} — 상용 스케일에서 수치가 변할 수 있습니다.</div>",
        unsafe_allow_html=True,
    )

# ======================================================================
# 결과 계산 (선택된 기술 전체)
# ======================================================================
results = []
for k in selected:
    t = LIT[k]
    we = calc_We(t, T_cool_C, p_final_bar)
    specca = calc_SPECCA(t["SRD"], we["We_elec"], capture_eff)
    cost = calc_COCA(
        t["CAPEX_per_t"], t["OPEX_solvent"], t["OPEX_other"],
        we["We_elec"], capture_t_yr, lifetime, discount, elec_price,
    )
    results.append({
        "key": k,
        "name": t["name"],
        "category": t["category"],
        "is_pilot": t["is_pilot"],
        "SRD": t["SRD"],
        **we,
        "SPECCA": specca,
        **cost,
        "loss_kg_per_tCO2": t["loss_kg_per_tCO2"],
        "loss_mech": t["loss_mech"],
        "T_regen": t["T_regen"],
        "T_abs": t["T_abs"],
        "source": t["source"],
        "notes": t["notes"],
    })

df = pd.DataFrame(results)

# ======================================================================
# 탭 구성
# ======================================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "① 종합 비교",
    "② 에너지 분해",
    "③ 경제성",
    "④ 흡수제/흡착제 손실",
    "⑤ 트렌드",
    "⑥ Custom 입력",
    "⑦ 참고문헌",
])

# ---------- ① 종합 비교 ----------
with tab1:
    # ── KPI 정의 카드 ──────────────────────────────────────
    with st.expander("📖 **KPI 지표 정의** — 클릭해서 펼치기/접기", expanded=True):
        def_cols = st.columns(4)

        definitions = [
            {
                "title": "SRD",
                "full": "Specific Reboiler Duty",
                "unit": "GJ / tCO₂",
                "color": "#4FC3F7",
                "formula": "Q<sub>regen</sub> / m<sub>CO₂</sub>",
                "desc": "흡수제(또는 흡착제) 재생에 필요한 단위 CO₂당 열량. "
                        "재생탑 reboiler의 열부하를 의미.",
                "hint": "↓ 낮을수록 열효율 우수",
            },
            {
                "title": "We",
                "full": "Equivalent Work (전력등가 일)",
                "unit": "GJe / tCO₂",
                "color": "#81C784",
                "formula": "We<sub>thermal</sub>(Carnot) + We<sub>elec</sub>",
                "desc": "재생열을 Carnot 효율로 전기로 환산한 값 + 펌프·압축·냉동기·보조 전력 합. "
                        "에너지 페널티의 통합 척도.",
                "hint": "↓ 낮을수록 통합 에너지 효율 우수",
            },
            {
                "title": "SPECCA",
                "full": "Specific Primary Energy<br>Consumption for CO₂ Avoided",
                "unit": "MJ / tCO₂",
                "color": "#FFB74D",
                "formula": "(SRD × 500 + We<sub>elec</sub> × 2,500) / capture",
                "desc": "포집을 위해 추가로 소모하는 1차 에너지를 포집율로 정규화. "
                        "포집율 차이를 보정한 페널티 지표.",
                "hint": "↓ 낮을수록 1차 에너지 효율 우수",
            },
            {
                "title": "COCA",
                "full": "Cost Of CO₂ Avoided / Captured",
                "unit": "USD / tCO₂",
                "color": "#E57373",
                "formula": "(연환산 CAPEX + OPEX) / 연 포집량",
                "desc": "단위 CO₂당 종합 비용. CAPEX는 CRF로 연환산 "
                        "(수명·할인율 적용), OPEX는 용매·전력·유틸·인건·정비 합.",
                "hint": "↓ 낮을수록 경제성 우수",
            },
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
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown(
            """
            <div style='font-size:0.72rem; color:#8b95a7; margin-top:10px;
                        padding:6px 10px; background:#1E2128; border-radius:4px;'>
            <b>📐 보조 개념</b> &nbsp;·&nbsp;
            <b>Carnot 효율</b>: η<sub>C</sub> = (T<sub>regen</sub> − T<sub>cool</sub>) / T<sub>regen</sub> (절대온도 K) — 열을 일로 바꿀 때 이론 한계.
            실효 효율은 η<sub>C</sub> × 0.55 가정 (second-law factor) &nbsp;·&nbsp;
            <b>CRF</b> (Capital Recovery Factor): i(1+i)<sup>n</sup> / [(1+i)<sup>n</sup> − 1] &nbsp;·&nbsp;
            <b>CAP 냉동기 COP</b>: T<sub>abs</sub> / (T<sub>amb</sub> − T<sub>abs</sub>) × 0.55
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")  # 약간의 간격
    st.markdown("### 핵심 KPI 비교")
    st.caption("4대 지표를 KPI별 순위 정렬 · 🟢 최고 · 🔴 최악 (모든 지표 낮을수록 우수)")

    # 4대 KPI 정의: (key, 라벨, 단위, 포맷)
    kpi_specs = [
        ("SRD",      "SRD",      "GJ/tCO₂",  "{:,.2f}"),
        ("We_total", "We 총합",  "GJe/tCO₂", "{:,.2f}"),
        ("SPECCA",   "SPECCA",   "MJ/tCO₂",  "{:,.0f}"),
        ("COCA",     "COCA",     "USD/tCO₂", "{:,.1f}"),
    ]

    def render_kpi_chart(spec, container):
        key, label, unit, fmt = spec
        sorted_r = sorted(results, key=lambda r: r[key])
        n = len(sorted_r)
        names = [SHORT_NAMES.get(r["key"], r["name"]) for r in sorted_r]
        vals = [r[key] for r in sorted_r]

        # 순위별 색상
        colors = []
        for i in range(n):
            if i == 0:
                colors.append("#81C784")        # 최고 (녹색)
            elif i == n - 1 and n > 1:
                colors.append("#E57373")        # 최악 (빨강)
            else:
                colors.append("#4FC3F7")        # 중간 (시안)

        # 최고 대비 % 차이 텍스트
        best = vals[0] if vals else 0
        text_labels = []
        for i, v in enumerate(vals):
            if i == 0:
                text_labels.append(f"★ {fmt.format(v)}")
            else:
                pct = (v - best) / best * 100 if best > 0 else 0
                text_labels.append(f"{fmt.format(v)}  (+{pct:.0f}%)")

        # 우측 여유: x축 최대값의 35% padding
        xmax = max(vals) * 1.35 if vals else 1

        f = go.Figure(go.Bar(
            x=vals,
            y=names,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(color="rgba(255,255,255,0.15)", width=1),
            ),
            text=text_labels,
            textposition="outside",
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
            template="plotly_dark",
            height=340,
            margin=dict(l=10, r=30, t=55, b=30),
            xaxis=dict(
                showgrid=True, gridcolor="#2C313C", zeroline=False,
                range=[0, xmax],
                tickfont=dict(size=12),
            ),
            yaxis=dict(
                autorange="reversed",   # 최고가 맨 위
                tickfont=dict(size=14, color="#E8EAED"),
            ),
            showlegend=False,
            uniformtext=dict(minsize=12, mode="show"),
        )
        container.plotly_chart(f, use_container_width=True)

    # 2 × 2 그리드 (각 차트 가로폭 2배 → 글자 잘림 해결)
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
    st.caption(
        "We_thermal: SRD를 Carnot 효율로 전기등가 환산 (참고). "
        "We_elec: 펌프·압축·냉동기·보조 전력. CAP만 냉동기 항목 활성."
    )

    components = [
        ("We_pump",        "펌프",       "#7986CB"),
        ("We_comp",        "CO₂ 압축",   "#4DD0E1"),
        ("We_chill",       "냉동기",     "#BA68C8"),
        ("We_aux",         "보조",       "#A1887F"),
        ("We_thermal_eq",  "열 (Carnot 환산)", "#FFB74D"),
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
        xaxis_tickangle=0,
        margin=CHART_MARGIN_STACK,
        legend=dict(orientation="h", y=-0.18),
    )
    st.plotly_chart(f, use_container_width=True)

    st.markdown("---")
    st.markdown("### CAP 냉동기 부하 — 냉각수 온도 민감도")
    st.caption("CAP의 We_chill은 냉각수 온도(응축기 측)에 민감. Carnot COP × 0.55 가정.")

    if any(r["category"] == "Chilled NH₃" for r in results):
        T_range = np.arange(5, 46, 2)
        cap_data = LIT["CAP_B12C"]
        Q_chill = cap_data["SRD"] * 0.18
        chill_we = [chiller_We(Q_chill, cap_data["T_abs"], T) for T in T_range]
        f2 = go.Figure()
        f2.add_trace(go.Scatter(
            x=T_range, y=chill_we, mode="lines+markers",
            line=dict(color="#BA68C8", width=3),
            marker=dict(size=8),
        ))
        f2.add_vline(x=T_cool_C, line_dash="dash", line_color="#ffc107",
                     annotation_text=f"현재 {T_cool_C}°C")
        f2.update_layout(
            template="plotly_dark", height=350,
            xaxis_title="냉각수 온도 [°C]",
            yaxis_title="We_chill [GJe/tCO₂]",
        )
        st.plotly_chart(f2, use_container_width=True)
    else:
        st.info("CAP을 선택하면 냉동기 민감도 그래프가 활성화됩니다.")

# ---------- ③ 경제성 ----------
with tab3:
    st.markdown("### CAPEX (별도) + OPEX 스택 + COCA 요약")

    col1, col2 = st.columns([1, 1])

    names_short = [SHORT_NAMES.get(r["key"], r["name"]) for r in results]

    # CAPEX (annualized) 별도 막대
    with col1:
        f = go.Figure()
        f.add_trace(go.Bar(
            x=names_short,
            y=[r["annual_capex"] for r in results],
            marker_color="#4FC3F7",
            text=[f"{r['annual_capex']:,.1f}" for r in results],
            textposition="outside",
        ))
        f.update_layout(
            title=f"연환산 CAPEX (수명 {lifetime}년, 할인율 {discount*100:.1f}%) [USD/tCO₂]",
            template="plotly_dark", height=400,
            xaxis_tickangle=0, margin=CHART_MARGIN,
        )
        st.plotly_chart(f, use_container_width=True)

    # OPEX 스택
    with col2:
        f = go.Figure()
        for col_, label, color in [
            ("opex_solvent", "용매/소재", "#81C784"),
            ("opex_other",   "유틸·인건·정비", "#FFB74D"),
            ("elec_cost",    "전력 비용", "#E57373"),
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
        st.plotly_chart(f, use_container_width=True)

    st.markdown("---")
    st.markdown("### COCA 요약")

    # COCA 막대 + 연간 총 비용
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
    st.plotly_chart(f, use_container_width=True)

    # 요약 테이블
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

# ---------- ④ 흡수제/흡착제 손실 ----------
with tab4:
    st.markdown("### 소재 손실 — 메커니즘별 비교")
    st.caption("습식: 분해/휘발 (kg/tCO₂). 고체: 사이클 열화/마모 (kg/tCO₂ 환산).")

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
    st.plotly_chart(f, use_container_width=True)

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

    # 전체 LIT
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

    # 회귀
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
        xaxis_title="SRD [GJ/tCO₂]",
        yaxis_title="We 총합 [GJe/tCO₂]",
    )
    st.plotly_chart(f, use_container_width=True)

    st.markdown("**해석:** 회귀선은 SRD↑ 시 We↑ 경향(열등가 항 지배). "
                "회귀선 아래에 위치하면 동일 SRD 대비 보조전력이 효율적인 기술입니다.")

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
            capex = st.number_input("CAPEX [USD/(t/yr)]", 500, 3000, 1100, 50)
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
        we = calc_We(custom, T_cool_C, p_final_bar)
        specca = calc_SPECCA(srd, we["We_elec"], capture_eff)
        cost = calc_COCA(capex, opex_sol, opex_oth, we["We_elec"],
                         capture_t_yr, lifetime, discount, elec_price)

        st.success(f"✅ **{name}** 계산 완료")
        c = st.columns(4)
        c[0].metric("SRD", f"{srd:,.2f} GJ/tCO₂")
        c[1].metric("We 총합", f"{we['We_total']:,.3f} GJe/tCO₂")
        c[2].metric("SPECCA", f"{specca:,.0f} MJ/tCO₂")
        c[3].metric("COCA", f"{cost['COCA']:,.1f} USD/tCO₂")

        # 선택된 기술과의 비교
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
    st.caption(f"총 {len(REFS)}개 출처 — 각 LIT 수치, 계산식, 경제성 가정의 근거를 전부 추적")

    # ── 카테고리별 분류 ──────────────────────────
    cat_labels = {
        "report":      "📄 정부·국제기구 보고서",
        "paper":       "📑 학술 논문 (Peer-reviewed)",
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

    # ── 기술별 LIT 수치 ↔ 출처 매핑 ──────────────────────────
    st.markdown("---")
    st.markdown("### 🧪 기술별 LIT 수치의 출처 매핑")
    st.caption("각 기술의 SRD/We/CAPEX/손실값이 어느 문헌에서 왔는지")

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

    # ── 계산식 ↔ 출처 매핑 ──────────────────────────
    st.markdown("---")
    st.markdown("### 🧮 계산식 ↔ 출처 매핑")
    st.caption("코드의 모든 수식과 가정에 대한 근거")

    formula_rows = []
    for formula, ref_ids in FORMULA_REFS.items():
        formula_rows.append({
            "수식 / 가정": formula,
            "출처": ", ".join(f"[{r}]" for r in ref_ids),
        })
    st.dataframe(pd.DataFrame(formula_rows), use_container_width=True, hide_index=True)

    # ── 통합 지표 정의 ──────────────────────────
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
              (하한 floor = 0.3)
  We_chill  = Q_chill / COP_eff (CAP만 동적)                    [ASHRAE_HVAC]
  We_aux    = LIT 고정값
  We_total  = We_thermal_eq + We_pump + We_comp + We_chill + We_aux

[2차 지표]
  SPECCA = (SRD × 500 + We_elec × 2,500) / capture              [Manzolini2015 변형]

[경제성]
  CRF      = i(1+i)^n / [(1+i)^n - 1]                          [NETL_QGESS]
  연환산 CAPEX = CAPEX × CRF
  전력비   = We_elec × 277.78 kWh/GJ × $80/MWh                  [EIA_AEO_2024]
  COCA     = 연환산 CAPEX + OPEX_solvent + OPEX_other + 전력비

[CAP 냉동기 (동적)]
  COP_Carnot = T_abs / (T_amb - T_abs)                          [ASHRAE_HVAC]
  COP_eff    = COP_Carnot × 0.55
  Q_chill    = SRD × 0.18      (NETL B12C 휴리스틱)              [NETL_Rev4a, Darde2010]
  We_chill   = Q_chill / COP_eff
""", language="python")

    # ── 데이터 신뢰도 등급 ──────────────────────────
    st.markdown("---")
    st.markdown("### 🎯 데이터 신뢰도 (Quality Tier)")

    tier_data = pd.DataFrame([
        {"기술": LIT["MEA_baseline"]["name"], "Tier": "A — 상용",
         "기준": "다수 상용 플랜트 운영 (Petra Nova, Boundary Dam)", "불확실성": "± 5%"},
        {"기술": LIT["CAP_B12C"]["name"], "Tier": "A — Demo",
         "기준": "AEP Mountaineer demo + NETL 공식 케이스", "불확실성": "± 10%"},
        {"기술": LIT["CaL"]["name"], "Tier": "B — Demo",
         "기준": "1.7 MWe La Pereda 파일럿 + IEAGHG 모델링", "불확실성": "± 15%"},
        {"기술": LIT["TSA_Solid"]["name"], "Tier": "B — Demo",
         "기준": "DOE 0.5~1 MWe 파일럿 (RTI, SRI)", "불확실성": "± 20%"},
        {"기술": LIT["K2CO3_KIERSOL"]["name"] + " †", "Tier": "C — Pilot",
         "기준": "KIER 0.5 MWe 파일럿", "불확실성": "± 25%"},
        {"기술": LIT["Biphasic_DMX"]["name"] + " †", "Tier": "C — Pilot",
         "기준": "Dunkirk 0.5 t/h 파일럿 (3D project)", "불확실성": "± 25%"},
    ])
    st.dataframe(tier_data, use_container_width=True, hide_index=True)

    st.warning(
        "⚠️ **주의**: 본 툴의 수치는 공개 보고서 기반 *representative values*입니다. "
        "Tier C(파일럿 †) 데이터는 상용 스케일에서 ±25% 이상 변동 가능. "
        "실제 프로젝트는 EPC 견적·사이트별 실증 데이터로 반드시 보정 필요."
    )

    st.caption(
        "💡 **인용 표기 예시**: 본 결과는 NETL Rev4a B12C [NETL_Rev4a] · "
        "Darde et al. 2010 [Darde2010] · IEAGHG 2013/19 [IEAGHG_CaL_2013] · "
        "KIER KIERSOL [KIER_KIERSOL_2013] 등을 기반으로 산출됨."
    )

# ======================================================================
# 푸터
# ======================================================================
st.markdown("---")
st.caption(
    "🌫️ 비아민계 CO₂ 포집 벤치마크 v1.0 | "
    "MEA(아민) 기준선 + K₂CO₃ · CAP · Biphasic · TSA · CaL | "
    "NETL Rev4a · IEAGHG · DOE · KIER"
)
