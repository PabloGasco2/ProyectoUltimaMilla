from __future__ import annotations

import streamlit as st


PRIMARY = "#FED7F6"
PRIMARY_DARK = "#111111"
PRIMARY_SOFT = "#FFF3FC"
PRIMARY_PALE = "#FFFAFE"
ACCENT = "#111111"
ACCENT_SOFT = "#F4F4F5"
BLUE = "#5F5F64"
CYAN = "#8B8B92"
AMBER = "#D26BBB"
DANGER = "#B42376"
SUCCESS = "#2F2F33"
BG = "#FFFBFE"
PANEL = "#FFFFFF"
BORDER = "#F2D1EA"
TEXT = "#111111"
MUTED = "#68606A"


PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": BG,
        "plot_bgcolor": PANEL,
        "font": {"color": TEXT, "family": "Inter, Segoe UI, sans-serif"},
        "colorway": [TEXT, PRIMARY, "#D88BCB", "#8B8B92", "#EDEDED"],
        "margin": {"l": 26, "r": 18, "t": 46, "b": 36},
    }
}


def apply_theme() -> None:
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: Inter, Segoe UI, sans-serif;
        }}

        .stApp {{
            background: {BG};
            color: {TEXT};
        }}

        header[data-testid="stHeader"] {{
            height: 0;
            min-height: 0;
            background: transparent;
            visibility: hidden;
        }}

        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        #MainMenu {{
            display: none !important;
        }}

        .block-container {{
            max-width: 1180px;
            padding-top: .35rem;
            padding-bottom: 0;
        }}

        h1, h2, h3 {{
            color: {TEXT};
            letter-spacing: 0;
        }}

        .landing {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 28px;
            padding: clamp(24px, 5vw, 54px);
            min-height: 420px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-shadow: 0 24px 70px rgba(17,17,17,.07);
            margin-bottom: 18px;
        }}

        .landing-mark {{
            display: inline-flex;
            width: fit-content;
            padding: 8px 12px;
            border-radius: 999px;
            background: {PRIMARY};
            color: {TEXT};
            font-weight: 850;
            font-size: .78rem;
            letter-spacing: .08em;
            text-transform: uppercase;
            margin-bottom: 18px;
        }}

        .landing h1 {{
            margin: 0;
            font-size: clamp(2.3rem, 7vw, 5rem);
            line-height: .96;
            font-weight: 900;
            max-width: 880px;
        }}

        .landing p {{
            max-width: 720px;
            margin: 18px 0 0 0;
            color: {MUTED};
            font-size: clamp(1rem, 2vw, 1.15rem);
        }}

        .appbar {{
            position: sticky;
            top: .6rem;
            z-index: 20;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            background: rgba(255,255,255,.94);
            border: 1px solid {BORDER};
            border-radius: 20px;
            padding: 12px 14px;
            box-shadow: 0 14px 40px rgba(17,17,17,.06);
            margin-bottom: 14px;
            backdrop-filter: blur(12px);
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
        }}

        .brand-dot {{
            width: 34px;
            height: 34px;
            border-radius: 12px;
            background: {PRIMARY};
            border: 1px solid {BORDER};
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
        }}

        .brand-title {{
            font-weight: 900;
            line-height: 1;
        }}

        .brand-subtitle {{
            color: {MUTED};
            font-size: .78rem;
            margin-top: 2px;
        }}

        .profile-chip {{
            background: {PRIMARY};
            border: 1px solid {BORDER};
            border-radius: 999px;
            padding: 8px 12px;
            font-weight: 850;
            white-space: nowrap;
        }}

        .selector-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
            margin: 16px 0;
        }}

        .select-card {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 22px;
            padding: 18px;
            box-shadow: 0 14px 42px rgba(17,17,17,.055);
            min-height: 170px;
        }}

        .select-card h3 {{
            margin: 0 0 8px 0;
            font-size: 1.35rem;
        }}

        .select-card p {{
            color: {MUTED};
            margin: 0 0 14px 0;
        }}

        .mini-section {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 18px;
            padding: 14px;
            box-shadow: 0 10px 28px rgba(17,17,17,.045);
            margin-bottom: 10px;
        }}

        .section-title {{
            color: {TEXT};
            font-size: .96rem;
            font-weight: 900;
            margin-bottom: 4px;
        }}

        .section-copy {{
            color: {MUTED};
            font-size: .88rem;
        }}

        .persona-banner {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 18px;
            padding: 14px;
            margin: 10px 0 14px 0;
            box-shadow: 0 10px 30px rgba(17,17,17,.05);
        }}

        .persona-kicker {{
            color: {MUTED};
            font-size: .72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: .08em;
        }}

        .persona-title {{
            font-size: clamp(1.1rem, 2vw, 1.45rem);
            font-weight: 900;
            color: {TEXT};
            margin-top: 2px;
        }}

        .persona-copy {{
            color: {MUTED};
            font-size: .9rem;
            margin-top: 2px;
        }}

        .card, .card-flat, .soft-panel, .metric-card {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 14px;
            box-shadow: 0 10px 28px rgba(17,17,17,.045);
            height: 100%;
        }}

        .soft-panel {{
            background: {PRIMARY_PALE};
        }}

        .card-title {{
            color: {TEXT};
            font-weight: 900;
            font-size: .98rem;
            margin-bottom: 6px;
        }}

        .muted {{
            color: {MUTED};
            font-size: .88rem;
        }}

        .metric-label {{
            color: {MUTED};
            font-size: .7rem;
            font-weight: 850;
            letter-spacing: .06em;
            text-transform: uppercase;
        }}

        .metric-value {{
            color: {TEXT};
            font-size: 1.32rem;
            font-weight: 900;
            margin-top: 4px;
        }}

        .badge, .badge-purple, .badge-blue, .badge-orange {{
            display: inline-flex;
            align-items: center;
            padding: 4px 8px;
            border-radius: 999px;
            background: {PRIMARY};
            color: {TEXT};
            border: 1px solid {BORDER};
            font-weight: 850;
            font-size: .68rem;
            margin: 2px 4px 2px 0;
            white-space: nowrap;
        }}

        .journey-step {{
            border-left: 3px solid {TEXT};
            padding: 7px 0 7px 11px;
            margin: 6px 0;
            color: {TEXT};
        }}

        .alert-card, .success-card {{
            background: {PRIMARY_PALE};
            border: 1px solid {BORDER};
            border-left: 5px solid {TEXT};
            border-radius: 14px;
            padding: 12px 14px;
        }}

        .stButton > button {{
            background: {TEXT};
            color: white;
            border: 1px solid {TEXT};
            border-radius: 12px;
            padding: .52rem .85rem;
            font-weight: 850;
            box-shadow: none;
        }}

        .stButton > button:hover {{
            background: {PRIMARY};
            border-color: {TEXT};
            color: {TEXT};
        }}

        div[role="radiogroup"] {{
            gap: 8px;
            flex-wrap: wrap;
        }}

        div[role="radiogroup"] label {{
            background: {TEXT} !important;
            border: 1px solid {TEXT} !important;
            border-radius: 8px !important;
            padding: 10px 14px !important;
            min-height: 42px;
            box-shadow: none;
        }}

        div[role="radiogroup"] label * {{
            color: #FFFFFF !important;
            font-weight: 850 !important;
        }}

        div[role="radiogroup"] label:has(input:checked) {{
            background: {PRIMARY} !important;
            border-color: {TEXT};
        }}

        div[role="radiogroup"] label:has(input:checked) * {{
            color: {TEXT} !important;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 6px;
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 6px;
            overflow-x: auto;
        }}

        .stTabs [data-baseweb="tab"] {{
            background: transparent;
            border-radius: 12px;
            padding: 8px 10px;
            min-height: 38px;
            color: {MUTED};
            font-weight: 850;
            font-size: .88rem;
        }}

        .stTabs [aria-selected="true"] {{
            background: {PRIMARY} !important;
            color: {TEXT} !important;
            border: 1px solid {BORDER};
        }}

        [data-testid="stExpander"] {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 14px;
            box-shadow: 0 8px 22px rgba(17,17,17,.035);
            overflow: hidden;
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid {BORDER};
            border-radius: 14px;
            overflow: hidden;
        }}

        .footer {{
            margin-top: 28px;
            padding: 18px 0 0 0;
            border-top: 1px solid {BORDER};
            color: {MUTED};
            font-size: .82rem;
        }}

        .footer-grid {{
            display: grid;
            grid-template-columns: 1.2fr 1fr 1fr;
            gap: 12px;
        }}

        @media (max-width: 760px) {{
            .block-container {{
                padding-left: .85rem;
                padding-right: .85rem;
            }}
            .landing {{
                min-height: auto;
                padding: 24px 18px;
                border-radius: 20px;
            }}
            .selector-grid, .footer-grid {{
                grid-template-columns: 1fr;
            }}
            .appbar {{
                position: static;
                align-items: flex-start;
                flex-direction: column;
            }}
            .profile-chip {{
                white-space: normal;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
