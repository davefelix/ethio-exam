import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. SYSTEM IDENTITY ---
SYSTEM_PROMPT = """
You are the Lead Examiner for the Ethiopian National Exam. 
Create ORIGINAL, CHALLENGING questions for the specified unit.
- NO 'According to the text' phrases.
- 40% Calculation questions with invented realistic values.
- 60% Conceptual/Analysis questions.
- Format: Return ONLY a JSON array. No other text.
"""

# --- 2. CONFIG ---
st.set_page_config(page_title="EthioExam Pro", page_icon="🇪🇹", layout="wide")

# Custom CSS for Dark Mode visibility
st.markdown("""
    <style>
    .stRadio [role="radiogroup"] { 
        background-color: rgba(100, 100, 100, 0.1); 
        border: 2px solid #4CAF50; border-radius: 10px; padding: 20px; 
    }
    .stRadio label { color: inherit !important; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🔑 API Key Missing!")

# --- 3. STORAGE ---
def save_history(entry):
    file = "history.json"
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
st.sidebar.title("🇪🇹 Exam Portal")
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
unit = st.sidebar.text_input("Unit Topic", placeholder="e.g. Unit 2: Forces")
count = st.sidebar.slider("Questions", 5, 40, 20)

if st.sidebar.button("🔥 Generate Exam"):
    path = f"textbooks/grade{grade}_{sub.lower()}.pdf"
    if os.path.exists(path):
        with st.spinner("Creating Original Questions..."):
            try:
                f = genai.upload_file(path=path)
                while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
                
                # STABLE MODEL: gemini-2.5-flash-lite
                model = genai.GenerativeModel("gemini-2.5-flash-lite", system_instruction=SYSTEM_PROMPT)
                
                # Force strict JSON format
                q_prompt = f"Unit: {unit}. Generate {count} hard MCQs. Output format: [{{'q':'','a':'','b':'','c':'','d':'','ans':'a/b/c/d','exp':''}}]"
                
                res = model.generate_content([f, q_prompt])
                txt = res.text.strip()
                
                # JSON Cleaner Logic
                if "```json" in txt: txt = txt.split("```json")[1].split("```")[0].strip()
                elif "```" in txt: txt = txt.split("```")[1].split("```")[0].strip()
                
                parsed_questions = json.loads(txt)
                
                # Verify 'q' key exists in every question to prevent KeyError
                if all('q' in item for item in parsed_questions):
                    st.session_state.exam.update({
                        "q": parsed_questions, "idx": 0, "ans": {}, 
                        "done": False, "start": time.time(), "time": count * 120, "unit": unit
                    })
                    st.rerun()
                else:
                    st.error("AI failed to format questions correctly. Please try again.")
            except Exception as e: st.error(f"Error: {e}")

# --- 6. EXAM ENGINE ---
ex = st.session_state.exam
if ex["q"] and not ex["done"]:
    # Timer
    rem = ex["time"] - (time.time() - ex["start"])
    if rem <= 0:
        ex["done"] = True
        st.rerun()

    c1, c2 = st.columns([3, 1])
    c1.title(f"📍 {ex['unit']}")
    m, s = divmod(int(rem), 60)
    c2.metric("Timer", f"{m:02d}:{secs:02d}" if 'secs' in locals() else f"{m:02d}:{int(rem%60):02d}")

    q_data = ex["q"][ex["idx"]]
    st.progress((ex["idx"] + 1) / len(ex["q"]))
    
    # SAFE DISPLAY
    st.markdown(f"### Question {ex['idx'] + 1}")
    st.info(q_data.get('q', "Question text missing"))
    
    opts = [q_data.get('a',''), q_data.get('b',''), q_data.get('c',''), q_data.get('d','')]
    labels = ["a", "b", "c", "d"]
    
    cur = None
    if ex["idx"] in ex["ans"]: cur = labels.index(ex["ans"][ex["idx"]])

    ans = st.radio("Select Answer:", opts, index=cur, key=f"q_{ex['idx']}")
    if ans: ex["ans"][ex["idx"]] = labels[opts.index(ans)]

    # Nav
    b1, b2, b3 = st.columns([1,1,1])
    if b1.button("⬅️ Back") and ex["idx"] > 0:
        ex["idx"] -= 1
        st.rerun()
    if b3.button("Next ➡️" if ex["idx"] < len(ex["q"])-1 else "🏁 Finish"):
        if ex["idx"] < len(ex["q"])-1:
            ex["idx"] += 1
            st.rerun()
        else:
            ex["done"] = True
            st.rerun()

# --- 7. RESULTS ---
if ex["done"] and ex["q"]:
    score = sum(1 for i, q in enumerate(ex["q"]) if ex["ans"].get(i) == q.get('ans'))
    st.header(f"Final Score: {score} / {len(ex['q'])}")
    
    save_history({"unit": ex["unit"], "score": score, "total": len(ex["q"]), "date": datetime.now().strftime("%Y-%m-%d")})
    
    for i, q in enumerate(ex["q"]):
        is_right = ex["ans"].get(i) == q.get('ans')
        with st.expander(f"Q{i+1}: {'✅' if is_right else '❌'}"):
            st.write(f"**Question:** {q.get('q')}")
            st.success(f"**Explanation:** {q.get('exp')}")
    
    if st.button("New Exam"):
        st.session_state.exam["q"] = []
        st.rerun()
