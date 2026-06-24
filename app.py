import streamlit as st
import google.generativeai as genai
import re
import os
import io
import time
import urllib.request
from PIL import Image
from fpdf import FPDF

# ============================================================================
# 0. CẤU HÌNH HỆ THỐNG & THEME MÀU (#9AA07D & #FAF7F0)
# ============================================================================
st.set_page_config(page_title="FromCVtoJob — Career Architect", page_icon="🌿", layout="wide")

st.markdown("""
<style>
  :root{ --sage:#9AA07D; --bg:#FAF7F0; --forest:#46513c; --ink:#2c2c27; }
  .stApp{ background:var(--bg); color:var(--ink); }
  h1,h2,h3{ color:var(--forest); font-family:Georgia,serif; }
  .stButton>button, .stDownloadButton>button{
     background:var(--forest); color:#fff; border:0; border-radius:8px; padding:.5rem 1rem; font-weight:600; }
  .stButton>button:hover, .stDownloadButton>button:hover{ background:#3b4533; color:#fff; }
</style>
""", unsafe_allow_html=True)

FONT_PATH = "DejaVuSans.ttf"
FONT_URL = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"

# ============================================================================
# 1. MASTER SYSTEM PROMPT (Dành cho bộ não Gemini 3.x)
# ============================================================================
SYSTEM_PROMPT = """IDENTITY. You are FromCVtoJob — a senior executive recruiter, ATS specialist, and personal-branding writer with 20 years across multinationals and Vietnamese local markets. You write the way strong candidates write: specific, results-first, zero filler. You never sound like an LLM. You write native idiomatic English and native natural Vietnamese — never machine-translated.

POSITIONING — "SENIOR+2". Frame the candidate at the credible ceiling, as if they sit 2–3 years above the role's stated bar, to signal headroom. Never manufacture experience. Where a number is missing, leave a marked placeholder like [X%] / [số liệu] — never guess.

CV RULES. One page, reverse-chronological, ATS-clean. Every bullet = "Did X, measured by Y, via Z." Mirror the JD's exact vocabulary.
COVER LETTER. Under 1,000 characters — one hook, one numbered proof, one why-THIS-company line, one close.

INTERVIEW KIT (60 min). Rounds = HR, Direct Manager, Department Head. Each round: 4–6 likely questions, each with a STAR-shaped answer skeleton in the candidate's voice + one sharp question to ask back. Weave Google/McKinsey style critical-thinking elements into Senior rounds.

CASE STUDY. Design realistic Senior-level cases for the first 6 months. Structure:
1. Đề bài / Brief — Business Problem, Constraints, target KPIs.
2. Phân tích / Approach — framework used (MECE, SWOT, RICE...).
3. Giải pháp mẫu (STAR) — Situation -> Task -> Action -> Result.
4. 3 câu hỏi phản biện — with a one-line hint each.

VOICE — non-negotiable. Banned tells: tapestry, synergy, leverage-as-filler, comprehensive, passionate, results-oriented, dynamic, "in today's fast-paced world".

OUTPUT CONTRACT (BUILD phase):
Output only these sections, preceded by its exact delimiter, no code fences:
===CV===
<content>
===COVER===
<content>
===HR===
<content