"""MaternaLink single-page animated demo. Step-by-step presentation of the AI pipeline."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    SYMPTOM_COLORS,
    SYMPTOM_NAMES,
    apply_css,
    highlight_transcript,
    info_box,
    load_anamnesis_records,
    load_conditions,
    load_drugs,
    load_facilities,
    load_ifk_stock,
    load_kb_condition_drug,
    load_l0_estimates,
    load_l0_extraction,
    load_l0_posteriors,
    load_l1_forecast,
    load_l2_allocation,
    load_l2_justifications,
    progress_bar,
    step_header,
    transcript_to_first_person,
)

TOTAL_STEPS = 7

st.set_page_config(
    page_title="MaternaLink",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_css()

if "step" not in st.session_state:
    st.session_state["step"] = 1

if "carousel_idx" not in st.session_state:
    st.session_state["carousel_idx"] = 0

if "carousel_started" not in st.session_state:
    st.session_state["carousel_started"] = False

step = st.session_state["step"]

progress_bar(step, TOTAL_STEPS)

anamnesis_df = load_anamnesis_records()
extraction_df = load_l0_extraction()
posteriors_df = load_l0_posteriors()
estimates_df = load_l0_estimates()
conditions_df = load_conditions()
drugs_df = load_drugs()
facilities_df = load_facilities()
l1_df = load_l1_forecast()
ifk_df = load_ifk_stock()
l2_alloc = load_l2_allocation()
l2_just = load_l2_justifications()

fac_names = facilities_df.set_index("facility_id")["name"].to_dict()
cond_names = conditions_df.set_index("condition_id")["condition_name"].to_dict()
drug_names = drugs_df.set_index("drug_id")["drug_name"].to_dict()

SAMPLE_IDS = ["ANM-000001", "ANM-000248", "ANM-000590", "ANM-000228", "ANM-000292"]
FOCUS_ID = "ANM-000001"


def get_focus_data():
    """Get extraction and posterior data for the focus patient."""
    anamnesis_row = anamnesis_df[anamnesis_df["anamnesis_id"] == FOCUS_ID].iloc[0]
    ext_row = extraction_df[extraction_df["anamnesis_id"] == FOCUS_ID]
    posteriors = posteriors_df[posteriors_df["anamnesis_id"] == FOCUS_ID]
    return anamnesis_row, ext_row, posteriors


def get_focus_facility():
    anamnesis_row = anamnesis_df[anamnesis_df["anamnesis_id"] == FOCUS_ID].iloc[0]
    return anamnesis_row["facility_id"]


def render_step_1():
    """Patient complaints carousel."""
    step_header("Layer 0", "Patient Complaints from the Field")
    info_box(
        "Healthcare workers at puskesmas record patient complaints as free text. "
        "Below are real anamnesis transcripts from different facilities."
    )
    st.markdown("<br>", unsafe_allow_html=True)

    idx = st.session_state["carousel_idx"]
    sample_id = SAMPLE_IDS[idx]
    row = anamnesis_df[anamnesis_df["anamnesis_id"] == sample_id].iloc[0]
    fac_name = fac_names.get(row["facility_id"], row["facility_id"])
    period_str = row["period"].strftime("%B %Y")

    st.markdown(
        f'<div style="text-align:center;font-size:12px;color:#666;margin-bottom:8px;">'
        f'{sample_id}  |  {fac_name}  |  {period_str}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="transcript-large">{transcript_to_first_person(row["transcript"])}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    dots = "  ".join(
        f'<span style="font-size:18px;color:{"#2E75B6" if i == idx else "#ccc"};">&#9679;</span>'
        for i in range(len(SAMPLE_IDS))
    )
    st.markdown(f'<div style="text-align:center;">{dots}</div>', unsafe_allow_html=True)

    if not st.session_state["carousel_started"]:
        st.session_state["carousel_started"] = True

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("Next patient", key="carousel_next", use_container_width=True):
            if idx < len(SAMPLE_IDS) - 1:
                st.session_state["carousel_idx"] = idx + 1
                st.rerun()
            else:
                st.session_state["step"] = 2
                st.rerun()


def render_step_2():
    """Focus on one patient."""
    step_header("Layer 0 / Step 1", "Selecting a Patient for Analysis")
    info_box(
        "We focus on one patient complaint and prepare it for AI-based symptom extraction. "
        "The system will scan the transcript for clinical symptom keywords."
    )
    st.markdown("<br>", unsafe_allow_html=True)

    anamnesis_row, ext_row, _ = get_focus_data()
    fac_name = fac_names.get(anamnesis_row["facility_id"], anamnesis_row["facility_id"])
    period_str = anamnesis_row["period"].strftime("%B %Y")

    st.markdown(
        f'<div style="text-align:center;font-size:12px;color:#666;margin-bottom:8px;">'
        f'{FOCUS_ID}  |  {fac_name}  |  {period_str}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="transcript-large">{transcript_to_first_person(anamnesis_row["transcript"])}</div>',
        unsafe_allow_html=True,
    )


def render_step_3():
    """Symptom extraction with highlights."""
    step_header("Layer 0 / Step 2", "AI Symptom Extraction")
    info_box(
        "The keyword extraction model scans the transcript. "
        "Highlighted phrases indicate detected clinical symptoms from the G01-G15 vocabulary."
    )
    st.markdown("<br>", unsafe_allow_html=True)

    anamnesis_row, ext_row, _ = get_focus_data()

    if ext_row.empty:
        st.markdown("No extraction data found for this record.")
        return

    ext = ext_row.iloc[0]
    raw_symptoms = json.loads(ext["extracted_symptoms"])
    symptom_ids = [s["symptom_id"] for s in raw_symptoms]
    confidences = {s["symptom_id"]: s["confidence"] for s in raw_symptoms}

    highlighted = highlight_transcript(anamnesis_row["transcript"], symptom_ids)
    st.markdown(
        f'<div class="transcript-box">{highlighted}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    legend_html = "".join(
        f'<span class="legend-pill" style="background:{SYMPTOM_COLORS[sid]};">'
        f'{sid}: {SYMPTOM_NAMES[sid]} (confidence: {confidences.get(sid, "-")})'
        f'</span>'
        for sid in symptom_ids
        if sid in SYMPTOM_COLORS
    )
    st.markdown(legend_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    symptom_table = pd.DataFrame(
        [
            {
                "Symptom": f"{sid}: {SYMPTOM_NAMES.get(sid, sid)}",
                "Confidence": confidences.get(sid, "-"),
            }
            for sid in symptom_ids
        ]
    )
    st.dataframe(symptom_table, use_container_width=True, hide_index=True)


def render_step_4():
    """Condition inference with bar chart."""
    step_header("Layer 0 / Step 3", "Condition Inference via Bayesian Update")
    info_box(
        "Using P(symptom | condition) from the knowledge base, a Bayesian update "
        "computes P(condition | symptoms) for each of the 16 maternal conditions."
    )

    _, _, posteriors = get_focus_data()

    if posteriors.empty:
        st.markdown("No posterior data found for this record.")
        return

    display_rows = posteriors.copy()
    display_rows["condition_name"] = display_rows["condition_id"].map(cond_names)
    display_rows = display_rows.sort_values("posterior", ascending=True)

    fig = go.Figure()
    colors = [
        "#2E75B6" if row["indicated"] else "#D0D0D0"
        for _, row in display_rows.iterrows()
    ]
    fig.add_bar(
        y=display_rows["condition_name"],
        x=display_rows["posterior"],
        orientation="h",
        marker_color=colors,
        text=display_rows["posterior"].apply(lambda x: f"{x:.2f}"),
        textposition="outside",
        textfont=dict(size=10, color="#333"),
    )
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        height=500,
        margin=dict(l=0, r=60, t=10, b=30),
        xaxis=dict(
            title=dict(text="P(condition | symptoms)", font=dict(color="#333")),
            range=[0, 1.15],
            gridcolor="#eee",
            tickfont=dict(color="#333"),
        ),
        yaxis=dict(tickfont=dict(size=12, color="#222")),
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

    indicated = posteriors[posteriors["indicated"] == True].copy()
    indicated["condition_name"] = indicated["condition_id"].map(cond_names)
    indicated_display = indicated[["condition_id", "condition_name", "posterior"]].rename(
        columns={"condition_id": "ID", "condition_name": "Condition", "posterior": "Posterior"}
    )
    indicated_display["Posterior"] = indicated_display["Posterior"].round(4)
    st.dataframe(indicated_display, use_container_width=True, hide_index=True)


def render_step_5():
    """Aggregation across facilities."""
    step_header("Layer 0 / Output", "Aggregated Condition Case Estimates")
    info_box(
        "Across all puskesmas, Layer 0 combines diagnosed cases with anamnesis-inferred "
        "soft counts. This table is the contract consumed by Layer 1 demand forecasting."
    )

    facility_id = get_focus_facility()
    latest_period = estimates_df["period"].max()
    period_estimates = estimates_df[
        (estimates_df["facility_id"] == facility_id)
        & (estimates_df["period"] == latest_period)
    ].copy()

    if period_estimates.empty:
        period_estimates = (
            estimates_df[estimates_df["facility_id"] == facility_id]
            .sort_values("period")
            .tail(16)
            .copy()
        )

    period_estimates["condition_name"] = period_estimates["condition_id"].map(cond_names)
    period_estimates = period_estimates.sort_values("estimated_total_cases", ascending=False)

    display = period_estimates[
        ["condition_id", "condition_name", "manual_cases", "anamnesis_indicated_cases", "estimated_total_cases"]
    ].rename(
        columns={
            "condition_id": "ID",
            "condition_name": "Condition",
            "manual_cases": "Diagnosed cases",
            "anamnesis_indicated_cases": "Anamnesis soft count",
            "estimated_total_cases": "Estimated total",
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    total_cases = estimates_df[estimates_df["period"] == latest_period].groupby("condition_id")["estimated_total_cases"].sum().reset_index()
    total_cases["condition_name"] = total_cases["condition_id"].map(cond_names)
    total_cases = total_cases.sort_values("estimated_total_cases", ascending=True).tail(12)

    fig = go.Figure()
    fig.add_bar(
        y=total_cases["condition_name"],
        x=total_cases["estimated_total_cases"],
        orientation="h",
        marker_color="#2E75B6",
        text=total_cases["estimated_total_cases"],
        textposition="outside",
        textfont=dict(size=10, color="#333"),
    )
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        height=350,
        margin=dict(l=0, r=60, t=10, b=30),
        xaxis=dict(title=dict(text="Total estimated cases (all facilities)", font=dict(color="#333")), gridcolor="#eee", tickfont=dict(color="#333")),
        yaxis=dict(tickfont=dict(size=11, color="#222")),
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)


def render_step_6():
    """Layer 1 demand forecast."""
    step_header("Layer 1", "Drug Demand Forecasting")
    info_box(
        "An XGBoost model forecasts drug demand per facility for the next period. "
        "A dynamic buffer is added based on lead time and road accessibility. "
        "Total requirement = forecast demand + buffer units."
    )

    facility_id = get_focus_facility()
    fac_row = facilities_df[facilities_df["facility_id"] == facility_id].iloc[0]

    fac_l1 = l1_df[l1_df["facility_id"] == facility_id].copy()
    fac_l1["drug_name"] = fac_l1["drug_id"].map(drug_names)

    fac_l1_display = fac_l1[
        ["drug_id", "drug_name", "forecast_demand", "buffer_pct", "buffer_units", "total_requirement", "current_stock"]
    ].copy()
    fac_l1_display["buffer_pct"] = (fac_l1_display["buffer_pct"] * 100).round(0).astype(int).astype(str) + "%"
    fac_l1_display = fac_l1_display.rename(
        columns={
            "drug_id": "ID",
            "drug_name": "Drug",
            "forecast_demand": "Forecast",
            "buffer_pct": "Buffer %",
            "buffer_units": "Buffer",
            "total_requirement": "Requirement",
            "current_stock": "Stock",
        }
    )
    st.dataframe(fac_l1_display, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    drugs_sorted = fac_l1.sort_values("total_requirement", ascending=True).tail(15)
    fig = go.Figure()
    fig.add_bar(
        y=drugs_sorted["drug_name"],
        x=drugs_sorted["current_stock"],
        name="Current stock",
        orientation="h",
        marker_color="#C8DFF0",
    )
    fig.add_bar(
        y=drugs_sorted["drug_name"],
        x=drugs_sorted["total_requirement"],
        name="Total requirement",
        orientation="h",
        marker_color="#2E75B6",
        opacity=0.75,
    )
    fig.update_layout(
        barmode="overlay",
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=380,
        margin=dict(l=0, r=20, t=10, b=50),
        xaxis=dict(title=dict(text="Units", font=dict(color="#333")), gridcolor="#eee", tickfont=dict(color="#333")),
        yaxis=dict(tickfont=dict(size=11, color="#222")),
        legend=dict(orientation="h", y=-0.15, font=dict(color="#333")),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_step_7():
    """Layer 2 allocation result: district-wide distribution."""
    step_header("Layer 2", "Equitable Allocation via MILP")
    info_box(
        "A mixed-integer linear program allocates limited IFK stock across all 30 puskesmas. "
        "Priority weights balance drug urgency, accessibility, stockout history, and "
        "regional maternal mortality. An LLM then verbalizes every allocation decision."
    )

    alloc = l2_alloc.copy()
    alloc["drug_name"] = alloc["drug_id"].map(drug_names)

    total_req = int(alloc["requirement"].sum())
    total_alloc = int(alloc["allocated"].sum())
    coverage_pct = total_alloc / total_req if total_req > 0 else 0
    n_facilities = alloc["facility_id"].nunique()
    n_unmet_drugs = int(alloc[alloc["unmet_demand"] > 0].groupby("drug_id").ngroups)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="stat-block"><div class="stat-value">{coverage_pct:.0%}</div>'
            f'<div class="stat-label">District coverage</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="stat-block"><div class="stat-value">{total_alloc:,}</div>'
            f'<div class="stat-label">Units allocated</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="stat-block"><div class="stat-value">{n_facilities}</div>'
            f'<div class="stat-label">Puskesmas served</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="stat-block"><div class="stat-value">{n_unmet_drugs}</div>'
            f'<div class="stat-label">Drugs with shortfall</div></div>',
            unsafe_allow_html=True,
        )

    # Section: coverage per puskesmas
    st.markdown(
        '<div style="font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#666;margin-top:16px;">'
        'Coverage per Puskesmas</div>',
        unsafe_allow_html=True,
    )
    info_box(
        "Each bar shows the average coverage ratio for one puskesmas. "
        "Hard-to-reach facilities (low accessibility score) should receive comparable or better coverage."
    )

    fac_coverage = (
        alloc.groupby("facility_id")
        .apply(lambda g: g["allocated"].sum() / g["requirement"].sum(), include_groups=False)
        .reset_index(name="coverage_ratio")
    )
    fac_coverage["name"] = fac_coverage["facility_id"].map(fac_names)
    fac_meta = facilities_df[["facility_id", "accessibility_score", "remoteness"]].copy()
    fac_coverage = fac_coverage.merge(fac_meta, on="facility_id")
    fac_coverage = fac_coverage.sort_values("accessibility_score", ascending=True)
    fac_coverage["label"] = fac_coverage["facility_id"] + " " + fac_coverage["name"].str.replace("Puskesmas ", "")

    colors_cov = [
        "#D94F4F" if r < 0.5 else ("#E8A838" if r < 0.8 else "#2E75B6")
        for r in fac_coverage["coverage_ratio"]
    ]

    fig_fac = go.Figure()
    fig_fac.add_bar(
        y=fac_coverage["label"],
        x=fac_coverage["coverage_ratio"],
        orientation="h",
        marker_color=colors_cov,
        text=fac_coverage["coverage_ratio"].apply(lambda x: f"{x:.0%}"),
        textposition="outside",
        textfont=dict(size=10, color="#333"),
    )
    fig_fac.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        height=620,
        margin=dict(l=0, r=50, t=10, b=30),
        xaxis=dict(
            title=dict(text="Coverage ratio", font=dict(color="#333")),
            range=[0, 1.3],
            gridcolor="#eee",
            tickformat="%",
            tickfont=dict(color="#333"),
        ),
        yaxis=dict(tickfont=dict(size=10, color="#222")),
    )
    fig_fac.update_traces(marker_line_width=0)
    st.plotly_chart(fig_fac, use_container_width=True)

    # Section: allocation per drug (district total)
    st.markdown(
        '<div style="font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#666;margin-top:12px;">'
        'Supply Gap per Drug (District Total)</div>',
        unsafe_allow_html=True,
    )
    info_box(
        "IFK warehouse stock is limited. This chart shows which drugs face the largest shortfall "
        "across the entire district."
    )

    drug_agg = alloc.groupby("drug_id").agg(
        requirement=("requirement", "sum"),
        allocated=("allocated", "sum"),
    ).reset_index()
    drug_agg["drug_name"] = drug_agg["drug_id"].map(drug_names)
    drug_agg = drug_agg.merge(ifk_df[["drug_id", "available_stock"]], on="drug_id", how="left")
    drug_agg["coverage"] = drug_agg["allocated"] / drug_agg["requirement"]
    drug_agg = drug_agg.sort_values("requirement", ascending=True)

    fig_drug = go.Figure()
    fig_drug.add_bar(
        y=drug_agg["drug_name"],
        x=drug_agg["requirement"],
        name="Total requirement",
        orientation="h",
        marker_color="#D9E8FA",
    )
    fig_drug.add_bar(
        y=drug_agg["drug_name"],
        x=drug_agg["allocated"],
        name="Total allocated",
        orientation="h",
        marker_color="#2E75B6",
    )
    fig_drug.update_layout(
        barmode="overlay",
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=550,
        margin=dict(l=0, r=20, t=10, b=50),
        xaxis=dict(
            title=dict(text="Units", font=dict(color="#333")),
            gridcolor="#eee",
            tickfont=dict(color="#333"),
        ),
        yaxis=dict(tickfont=dict(size=10, color="#222")),
        legend=dict(orientation="h", y=-0.1, font=dict(color="#333")),
    )
    st.plotly_chart(fig_drug, use_container_width=True)

    with st.expander("Full drug allocation table"):
        drug_table = drug_agg[["drug_id", "drug_name", "available_stock", "requirement", "allocated", "coverage"]].copy()
        drug_table["coverage"] = drug_table["coverage"].apply(lambda x: f"{x:.0%}")
        drug_table = drug_table.rename(columns={
            "drug_id": "ID",
            "drug_name": "Drug",
            "available_stock": "IFK stock",
            "requirement": "Required",
            "allocated": "Allocated",
            "coverage": "Coverage",
        })
        st.dataframe(drug_table, use_container_width=True, hide_index=True)

    # Section: AI Justifications
    st.markdown(
        '<div style="font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#666;margin-top:12px;">'
        'AI Allocation Justifications</div>',
        unsafe_allow_html=True,
    )

    summary_just = l2_just[l2_just["target_type"] == "summary"]
    if not summary_just.empty:
        st.markdown(
            f'<div style="background:#f0f4f8;border:1px solid #c8d8e8;border-radius:6px;'
            f'padding:14px 18px;font-size:14px;color:#111;line-height:1.6;margin:8px 0;">'
            f'<span style="font-weight:600;">District Summary</span><br><br>'
            f'{summary_just.iloc[0]["justification_text"]}</div>',
            unsafe_allow_html=True,
        )

    alloc_just = l2_just[l2_just["target_type"] == "allocation"].copy()
    if not alloc_just.empty:
        st.markdown(
            '<div style="font-size:11px;color:#666;margin-top:12px;">Allocation decisions</div>',
            unsafe_allow_html=True,
        )
        for _, row in alloc_just.head(4).iterrows():
            fac_label = fac_names.get(row["facility_id"], row["facility_id"])
            drug_label = drug_names.get(row["drug_id"], row["drug_id"])
            st.markdown(
                f'<div style="background:#fafafa;border:1px solid #e0e0e0;border-radius:6px;'
                f'padding:12px 16px;margin:6px 0;">'
                f'<span style="font-weight:600;color:#111;">{fac_label}</span>'
                f'<span style="color:#999;"> / </span>'
                f'<span style="font-weight:600;color:#2E75B6;">{drug_label}</span><br>'
                f'<span style="font-size:13px;color:#222;line-height:1.5;">{row["justification_text"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    redist_just = l2_just[l2_just["target_type"] == "redistribution"].copy()
    if not redist_just.empty:
        st.markdown(
            '<div style="font-size:11px;color:#666;margin-top:12px;">Inter-facility transfers</div>',
            unsafe_allow_html=True,
        )
        for _, row in redist_just.head(4).iterrows():
            drug_label = drug_names.get(row["drug_id"], row["drug_id"])
            st.markdown(
                f'<div style="background:#fafafa;border:1px solid #e0e0e0;border-radius:6px;'
                f'padding:12px 16px;margin:6px 0;">'
                f'<span style="font-weight:600;color:#2E75B6;">{drug_label}</span><br>'
                f'<span style="font-size:13px;color:#222;line-height:1.5;">{row["justification_text"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


RENDER_FUNCS = {
    1: render_step_1,
    2: render_step_2,
    3: render_step_3,
    4: render_step_4,
    5: render_step_5,
    6: render_step_6,
    7: render_step_7,
}

st.markdown(
    f'<div style="position:fixed;top:16px;left:24px;font-size:14px;font-weight:600;color:#111;">'
    f'MaternaLink</div>',
    unsafe_allow_html=True,
)

step_label = f"{step} / {TOTAL_STEPS}"
st.markdown(
    f'<div style="position:fixed;top:18px;right:24px;font-size:11px;color:#999;">'
    f'{step_label}</div>',
    unsafe_allow_html=True,
)

RENDER_FUNCS[step]()

st.markdown("<br>", unsafe_allow_html=True)

btn_col1, btn_col2, btn_col3 = st.columns([6, 1, 1])
with btn_col2:
    if step > 1:
        if st.button("Back", key="back_btn", use_container_width=True):
            st.session_state["step"] = step - 1
            st.rerun()
with btn_col3:
    if step < TOTAL_STEPS:
        if st.button("Next", key="next_btn", type="primary", use_container_width=True):
            st.session_state["step"] = step + 1
            st.rerun()
    else:
        if st.button("Restart", key="restart_btn", type="primary", use_container_width=True):
            st.session_state["step"] = 1
            st.session_state["carousel_idx"] = 0
            st.session_state["carousel_started"] = False
            st.rerun()
