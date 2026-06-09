"""Shared data loaders, constants, CSS, and the transcript highlight function."""

import json
import os
import re

import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SYMPTOM_NAMES = {
    "G01": "High fever",
    "G02": "Chills",
    "G03": "Excessive nausea and vomiting",
    "G04": "Extreme fatigue",
    "G05": "Severe headache or dizziness",
    "G06": "Facial or leg swelling",
    "G07": "Painful urination",
    "G08": "Abnormal vaginal discharge",
    "G09": "Blurred vision",
    "G10": "Epigastric pain",
    "G11": "Shortness of breath",
    "G12": "Jaundice",
    "G13": "Leg cramps or bone pain",
    "G14": "Prolonged sadness or anxiety",
    "G15": "Constipation or bloating",
}

SYMPTOM_KEYWORDS = {
    "G01": ["high fever", "fever", "body temperature"],
    "G02": ["chills", "shivering", "cold sweats"],
    "G03": ["vomits", "vomiting", "nausea", "nauseated"],
    "G04": ["weak and tired", "exhausted", "extreme fatigue", "weak", "tired"],
    "G05": ["pounding headache", "headache", "dizziness", "dizzy", "head hurts", "room sometimes spins"],
    "G06": ["swollen", "swelling"],
    "G07": ["burns and hurts whenever she urinates", "pain when passing urine", "urinates", "urination"],
    "G08": ["vaginal discharge", "whitish discharge", "discharge"],
    "G09": ["blurry", "blurred vision", "cannot see clearly", "hazy"],
    "G10": ["upper part of her stomach", "below her chest after meals", "burning pain"],
    "G11": ["short of breath", "shortness of breath", "struggles to breathe"],
    "G12": ["yellowish", "yellow", "jaundice"],
    "G13": ["leg cramps", "bones ache", "calves cramp"],
    "G14": ["sad and anxious", "hopeless", "worries constantly", "sadness or anxiety"],
    "G15": ["constipation", "bowel movement", "bloated"],
}

SYMPTOM_COLORS = {
    "G01": "#FFD180",
    "G02": "#80D8FF",
    "G03": "#B9F6CA",
    "G04": "#FF80AB",
    "G05": "#EA80FC",
    "G06": "#FFE57F",
    "G07": "#84FFFF",
    "G08": "#D7CCC8",
    "G09": "#CCFF90",
    "G10": "#FF8A80",
    "G11": "#82B1FF",
    "G12": "#FFFF8D",
    "G13": "#F8BBD0",
    "G14": "#CE93D8",
    "G15": "#B2DFDB",
}

FACTOR_LABELS = {
    "drug_category": "Drug category",
    "accessibility": "Accessibility",
    "stockout_history": "Stockout history",
    "days_of_stock": "Days of stock",
    "regional_mmr": "Regional MMR",
}

FULLSCREEN_CSS = """
<style>
/* Hide all Streamlit chrome */
header, footer { visibility: hidden; height: 0; }
[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; }
section[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
#stDeployButton { display: none !important; }

/* Fullscreen white */
html, body, .stApp, [data-testid="stAppViewContainer"], .main {
    background-color: #ffffff !important;
}

/* No scroll */
html, body {
    overflow: hidden !important;
    height: 100vh;
}

/* Content fills viewport */
.block-container {
    padding: 2rem 3rem 1rem 3rem !important;
    max-width: 100% !important;
    height: calc(100vh - 40px);
}

/* Typography */
.step-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #999;
    margin-bottom: 2px;
}
.step-title {
    font-size: 18px;
    font-weight: 600;
    color: #111;
    padding-bottom: 8px;
    border-bottom: 1.5px solid #e0e0e0;
    margin-bottom: 16px;
}
.transcript-box {
    background: #f8f8f8;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 20px 24px;
    font-size: 15px;
    line-height: 1.8;
    color: #111;
}
.transcript-large {
    background: #f8f8f8;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 28px 32px;
    font-size: 17px;
    line-height: 1.85;
    color: #111;
    text-align: center;
}
.info-box {
    background: #f5f5f5;
    border-left: 3px solid #bbb;
    padding: 10px 14px;
    font-size: 13px;
    color: #333;
    border-radius: 0 4px 4px 0;
    margin: 8px 0;
}
.legend-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 12px;
    margin: 3px 4px;
    color: #111;
    border: 1px solid #ccc;
}
.stat-block {
    text-align: center;
    padding: 14px 8px;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
}
.stat-value {
    font-size: 26px;
    font-weight: 700;
    color: #111;
    line-height: 1.1;
}
.stat-label {
    font-size: 10px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}
.next-btn {
    position: fixed;
    bottom: 20px;
    right: 28px;
    z-index: 9999;
}
/* Button hover fix: white text on dark background */
.stButton > button:hover, .stButton > button:active, .stButton > button:focus {
    color: #ffffff !important;
}
.stButton > button {
    color: #111 !important;
    border: 1px solid #ccc !important;
    background-color: #ffffff !important;
}
.stButton > button:hover {
    background-color: #2E75B6 !important;
    border-color: #2E75B6 !important;
    color: #ffffff !important;
}
.stButton > button[kind="primary"] {
    background-color: #2E75B6 !important;
    color: #ffffff !important;
    border-color: #2E75B6 !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1a5a99 !important;
    color: #ffffff !important;
}
.progress-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    height: 3px;
    background: #2E75B6;
    transition: width 0.3s ease;
}
.facility-tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 11px;
    background: #e8e8e8;
    color: #333;
    margin: 2px;
}
</style>
"""


def apply_css():
    st.markdown(FULLSCREEN_CSS, unsafe_allow_html=True)


def transcript_to_first_person(text: str) -> str:
    """Convert narrator-perspective transcript to first-person patient speech.

    Strips prefixes like 'The patient says that', 'She complains that', etc.
    and converts third-person pronouns to first-person.
    """
    import re as _re

    prefixes = [
        "The patient says that ",
        "The mother reports that ",
        "During the visit she mentions that ",
        "She complains that ",
    ]
    connectors = [
        "She also mentions that ",
        "In addition, ",
        "She adds that ",
        "On top of that, ",
    ]

    sentences = text.split(". ")
    cleaned = []
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        matched_prefix = False
        for prefix in prefixes:
            if s.startswith(prefix):
                s = s[len(prefix):]
                matched_prefix = True
                break
        if not matched_prefix:
            for conn in connectors:
                if s.startswith(conn):
                    s = s[len(conn):]
                    break
        s = s.replace("she has", "I have")
        s = s.replace("she gets", "I get")
        s = s.replace("she feels", "I feel")
        s = s.replace("she vomits", "I vomit")
        s = s.replace("she keeps", "I keep")
        s = s.replace("she can ", "I can ")
        s = s.replace("she cannot ", "I cannot ")
        s = s.replace("she struggles", "I struggle")
        s = s.replace("she noticed", "I noticed")
        s = s.replace("her family noticed", "my family noticed")
        s = s.replace("her body", "my body")
        s = s.replace("her head", "my head")
        s = s.replace("her feet", "my feet")
        s = s.replace("her legs", "my legs")
        s = s.replace("her face", "my face")
        s = s.replace("her vision", "my vision")
        s = s.replace("her skin", "my skin")
        s = s.replace("her eyes", "my eyes")
        s = s.replace("her stomach", "my stomach")
        s = s.replace("her calves", "my calves")
        s = s.replace("her teeth", "my teeth")
        s = s.replace("her appetite", "my appetite")
        s = s.replace("her lower back", "my lower back")
        s = s.replace("her pregnancy", "my pregnancy")
        s = s.replace("her sandals", "my sandals")
        s = s.replace("she is", "I am")
        s = s.replace("she was", "I was")
        if not s.endswith("."):
            s += "."
        s = s[0].upper() + s[1:]
        cleaned.append(s)

    return " ".join(cleaned)


def step_header(label: str, title: str):
    st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="step-title">{title}</div>', unsafe_allow_html=True)


def info_box(text: str):
    st.markdown(f'<div class="info-box">{text}</div>', unsafe_allow_html=True)


def progress_bar(step: int, total: int = 7):
    pct = int(step / total * 100)
    st.markdown(
        f'<div class="progress-bar" style="width:{pct}%"></div>',
        unsafe_allow_html=True,
    )


def highlight_transcript(transcript: str, symptom_ids: list) -> str:
    """Return HTML with symptom keyword phrases highlighted by color."""
    matches = []
    for sid in symptom_ids:
        color = SYMPTOM_COLORS.get(sid, "#e0e0e0")
        name = SYMPTOM_NAMES.get(sid, sid)
        for phrase in SYMPTOM_KEYWORDS.get(sid, []):
            for m in re.finditer(re.escape(phrase), transcript, re.IGNORECASE):
                matches.append((m.start(), m.end(), sid, color, name, m.group(0)))

    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    non_overlapping = []
    last_end = 0
    for match in matches:
        if match[0] >= last_end:
            non_overlapping.append(match)
            last_end = match[1]

    parts = []
    pos = 0
    for start, end, sid, color, name, text_chunk in non_overlapping:
        parts.append(transcript[pos:start])
        parts.append(
            f'<mark style="background:{color};padding:1px 4px;border-radius:3px;" '
            f'title="{name}">{text_chunk}</mark>'
        )
        pos = end
    parts.append(transcript[pos:])
    return "".join(parts)


@st.cache_data
def load_facilities():
    return pd.read_csv(os.path.join(DATA_DIR, "master", "facilities.csv"))


@st.cache_data
def load_drugs():
    return pd.read_csv(os.path.join(DATA_DIR, "master", "drugs.csv"))


@st.cache_data
def load_conditions():
    return pd.read_csv(os.path.join(DATA_DIR, "master", "conditions.csv"))


@st.cache_data
def load_kb_symptom_condition():
    return pd.read_csv(os.path.join(DATA_DIR, "master", "kb_symptom_condition.csv"))


@st.cache_data
def load_kb_condition_drug():
    return pd.read_csv(os.path.join(DATA_DIR, "master", "kb_condition_drug.csv"))


@st.cache_data
def load_anamnesis_records():
    df = pd.read_csv(os.path.join(DATA_DIR, "transactional", "anamnesis_records.csv"))
    df["period"] = pd.to_datetime(df["period"])
    return df


@st.cache_data
def load_l0_extraction():
    df = pd.read_csv(os.path.join(DATA_DIR, "layer0_output", "l0_extraction_results.csv"))
    df["period"] = pd.to_datetime(df["period"])
    return df


@st.cache_data
def load_l0_posteriors():
    df = pd.read_csv(os.path.join(DATA_DIR, "layer0_output", "l0_condition_posteriors.csv"))
    df["period"] = pd.to_datetime(df["period"])
    return df


@st.cache_data
def load_l0_estimates():
    df = pd.read_csv(os.path.join(DATA_DIR, "layer0_output", "l0_condition_estimates.csv"))
    df["period"] = pd.to_datetime(df["period"])
    return df


@st.cache_data
def load_l1_forecast():
    df = pd.read_csv(os.path.join(DATA_DIR, "layer1_mock", "l1_forecast_mock.csv"))
    df["forecast_period"] = pd.to_datetime(df["forecast_period"])
    return df


@st.cache_data
def load_ifk_stock():
    return pd.read_csv(os.path.join(DATA_DIR, "layer1_mock", "ifk_stock_mock.csv"))


@st.cache_data
def load_l2_allocation():
    return pd.read_csv(os.path.join(DATA_DIR, "layer2_output", "l2_allocation.csv"))


@st.cache_data
def load_l2_redistribution():
    return pd.read_csv(os.path.join(DATA_DIR, "layer2_output", "l2_redistribution.csv"))


@st.cache_data
def load_l2_decision_factors():
    return pd.read_csv(os.path.join(DATA_DIR, "layer2_output", "l2_decision_factors.csv"))


@st.cache_data
def load_l2_justifications():
    return pd.read_csv(os.path.join(DATA_DIR, "layer2_output", "l2_justifications.csv"))
