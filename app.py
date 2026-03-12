import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. THE "ELITE" SYSTEM IDENTITY ---
# This is the secret to making it harder. We tell the AI to act as a 
# 'Gatekeeper' for top-tier university entrance.
SYSTEM_PROMPT = """
You are a Senior Examination Scientist for the EUEE. Your goal is to select only the top 1% of students.
Create EXTREMELY CHALLENGING, high-level questions for the specified unit.

STRICT DIFFICULTY RULES:
1. NO DIRECT BOOK QUOTES: Questions must be original scenarios.
2. CONCEPTUAL COMBINATION: Combine two related concepts in one question (e.g., Conservation of Momentum + Kinetic Energy loss).
3. MULTI-STEP CALCULATIONS: 50% of questions must require at least 3 steps of calculation. 
4. REAL-WORLD DATA: Use realistic, non-integer values (e.g., 9.81 m/s², 6.67x10^-11 Nm²/kg²) to test precision.
5. DISTRACTORS: Wrong answers (distractors) must be based on common student calculation errors (like forgetting to square a value or using wrong units).
6. FORMAT: Return ONLY a JSON array: [{"q":"","a":"","b":"","c":"","d":"","ans":"a/b/c/d","exp":""}]
"""

# --- 2. CONFIG & THEME ---
st.set_page_config(page_title="EthioExam Elite", page_icon="🇪🇹", layout="wide")

st.markdown("""
    <style>
    .stRadio [role="radiogroup"] { 
        background-color: rgba(40, 40, 40, 0.4); 
        border: 2px solid #FF4B4B; border-radius: 12px; padding: 25px; 
    }
    .stRadio label { font-size: 1.2rem !important; color: white !important; }
    div[data-testid="stMetricValue"] { color: #FF4B4B; }
    </style>
    """, unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🔑 Key Missing!")

# --- 3. STORAGE ---
def save_history(entry):
    file = "hard_history.json"
    data = []
    if os.path.exists(file):
        try:
            with open(file, "r") as f: data = json.load(f)
        except: data = []
    data.append(entry)
    with open(file, "w") as f: json.dump(data, f)

# --- 4. SESSION STATE ---
if "exam" not in st.session_state:
    st.session_state.exam = {"q": [], "idx": 0, "ans": {}, "done": False, "start": 0, "time": 0, "unit": ""}

# --- 5. SIDEBAR ---
st.sidebar.title("🔥 Elite Exam Engine")
grade = st.sidebar.selectbox("Grade", [11, 12]) # Focused on upper grades for hardness
sub = st.sidebar.selectbox("Subject", ["Physics", "Maths", "Chemistry", "Biology"])
unit_input = st.sidebar.text_input("Unit Topic", placeholder="e.g. Unit 4: Electromagnetism")
count = st.sidebar.slider("Number of Questions", 5, 50, 20)

if st.sidebar.button("💀 Generate Extreme Exam"):
    path = f"textbooks/grade{grade}_{sub.lower()}.pdf"
    if os.path.exists(path):
        with st.spinner("AI is engineering complex problems..."):
            try:
                f_ref = genai.upload_file(path=path)
                while f_ref.state.name == "PROCESSING": time.sleep(1); f_ref = genai.get_file(f_ref.name)
                
                model = genai.GenerativeModel("gemini-2.0-flash-lite", system_instruction=SYSTEM_PROMPT)
                
                # We specifically ask for 'Multi-step' and 'Conceptual' focus
                h_prompt = f"Unit: {unit_input}. Task: Create {count} extremely hard, multi-step EUEE-style questions. No simple recall. Focus on analysis."
                
                res = model.generate_content([f_ref, h_prompt])
                txt = res.text.strip()
                
                # Clean JSON
                if "```json" in txt: txt = txt.split("```json")[1].split("```")[0].strip()
                elif "```" in txt: txt = txt.split("```")[1].split("```")[0].strip()
                
                st.session_state.exam.update({
                    "q": json.loads(txt), "idx": 0, "ans": {}, 
                    "done": False, "start": time.time(), "time": count * 120, "unit": unit_input
                })
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- 6. EXAM UI ---
ex = st.session_state.exam
if ex["q"] and not ex["done"]:
    rem = ex["time"] - (time.time() - ex["start"])
    if rem <= 0:
        ex["done"] = True
        st.rerun()

    c1, c2 = st.columns([3, 1])
    c1.title(f"📍 {ex['unit']}")
    m, s = divmod(int(rem), 60)
    c2.metric("Time Left", f"{m:02d}:{s:02d}")

    q_data = ex["q"][ex["idx"]]
    st.progress((ex["idx"] + 1) / len(ex["q"]))
    
    st.markdown(f"#### Question {ex['idx'] + 1}")
    st.info(q_data.get('q', ''))
    
    opts = [q_data['a'], q_data['b'], q_data['c'], q_data['d']]
    labels = ["a", "b", "c", "d"]
    
    cur_ans = None
    if ex["idx"] in ex["ans"]: cur_ans = labels.index(ex["ans"][ex["idx"]])

    user_sel = st.radio("Select the correct analysis:", opts, index=cur_ans, key=f"ex_{ex['idx']}")
    if user_sel: ex["ans"][ex["idx"]] = labels[opts.index(user_sel)]

    n1, n2, n3 = st.columns([1,1,1])
    if n1.button("⬅️ Previous") and ex["idx"] > 0:
        ex["idx"] -= 1
        st.rerun()
    if n3.button("Next ➡️" if ex["idx"] < len(ex["q"])-1 else "🏁 Submit"):
        if ex["idx"] < len(ex["q"])-1:
            ex["idx"] += 1
            st.rerun()
        else:
            ex["done"] = True
            st.rerun()

# --- 7. RESULTS ---
if ex["done"] and ex["q"]:
    score = sum(1 for i, q in enumerate(ex["q"]) if ex["ans"].get(i) == q.get('ans'))
    st.title("🎯 Performance Breakdown")
    st.metric("Elite Score", f"{score} / {len(ex['q'])}")
    
    save_history({"unit": ex["unit"], "score": score, "total": len(ex["q"]), "date": datetime.now().strftime("%Y-%m-%d")})
    
    for i, q in enumerate(ex["q"]):
        is_correct = ex["ans"].get(i) == q.get('ans')
        with st.expander(f"Analysis of Q{i+1}: {'✅' if is_correct else '❌'}"):
            st.write(f"**Question:** {q.get('q')}")
            st.write(f"**Correct Answer:** {q.get('ans').upper()}")
            st.success(f"**Step-by-Step Logic:** {q.get('exp')}")
    
    if st.button("Try Another Hard Unit"):
        st.session_state.exam["q"] = []
        st.rerun()
