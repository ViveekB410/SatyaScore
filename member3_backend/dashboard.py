"""
Streamlit web demo dashboard.

PRD ref: FR-06.
    - Highlight hallucinated claims in RED, uncertain in AMBER, verified in GREEN
    - Display a bar chart of HalluScore distributions across all claims
    - Allow users to export results as CSV or JSON
    - (File upload .txt/.pdf not yet implemented — see TODO at bottom)

Note (v2.3 rebalancing): this file was moved from Member 4 to Member 3 in
the PRD, since Member 3 already owns the API this dashboard depends on.

Run:
    streamlit run member3_backend/dashboard.py
Requires the API to be running separately:
    uvicorn member3_backend.api:app --reload
"""

import json

import pandas as pd
import requests
import streamlit as st

API_URL = "http://localhost:8000/detect"
API_KEY = "dev-key-satyascore-2026"  # matches the dev key in api.py

VERDICT_COLORS = {
    "Hallucinated": "#ffcccc",
    "Uncertain": "#fff3cd",
    "Verified": "#d4edda",
}

st.set_page_config(page_title="SatyaScore", layout="wide")
st.title("SatyaScore — Hallucination Detection Demo")

with st.sidebar:
    st.header("Settings")
    language = st.selectbox("Language", ["en", "hi", "mr"])
    st.caption(
        "Ablation mode: leave all checked for the full CMHSA score, or "
        "uncheck signals to reproduce the paper's ablation study."
    )
    use_semsim = st.checkbox("Semantic Similarity", value=True)
    use_nli = st.checkbox("NLI Entailment", value=True)
    use_kg = st.checkbox("Knowledge Graph", value=True)

text_input = st.text_area(
    "LLM-generated text to check",
    height=150,
    placeholder="Paste text here, e.g. a chatbot response you want to fact-check...",
)

if st.button("Run Detection", type="primary") and text_input.strip():
    active_signals = [
        name
        for name, enabled in [("semsim", use_semsim), ("nli", use_nli), ("kg", use_kg)]
        if enabled
    ]

    with st.spinner("Scoring claims..."):
        try:
            response = requests.post(
                API_URL,
                json={"text": text_input, "language": language, "active_signals": active_signals},
                headers={"X-API-Key": API_KEY},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as e:
            st.error(
                f"Could not reach the API at {API_URL}. Is it running? "
                f"(`uvicorn member3_backend.api:app --reload`)\n\nDetails: {e}"
            )
            st.stop()

    st.subheader(f"Overall HalluScore: {result['overall_score']:.3f}")

    st.markdown("### Claim-level results")
    for claim in result["claims"]:
        color = VERDICT_COLORS.get(claim["verdict"], "#eeeeee")
        st.markdown(
            f"""<div style="background-color:{color}; padding:10px; border-radius:6px; margin-bottom:8px;">
            <b>{claim['verdict']}</b> (score: {claim['hallu_score']:.3f}, signals: {', '.join(claim['active_signals'])})<br/>
            {claim['text']}
            </div>""",
            unsafe_allow_html=True,
        )

    df = pd.DataFrame(result["claims"])
    st.markdown("### Score distribution")
    st.bar_chart(df.set_index("claim_id")["hallu_score"])

    st.markdown("### Export")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download JSON", data=json.dumps(result, indent=2), file_name="satyascore_results.json"
        )
    with col2:
        st.download_button("Download CSV", data=df.to_csv(index=False), file_name="satyascore_results.csv")

# TODO (Member 3): file upload support (.txt, .pdf) per FR-06 — not yet built.
