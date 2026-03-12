import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. SYSTEM IDENTITY (The "Secret Sauce") ---
# This tells the AI to stop acting like a robot and start acting like an examiner.
SYSTEM_PROMPT = """
You are the Lead Developer for the Ethiopian National Entrance Examination. 
Your task is to create high-stakes, competitive Multiple Choice Questions.

STRICT STYLE RULES:
1. NO REFERENCING: Never say 'According to the text', 'In this chapter', or 'As mentioned'. 
2. DIRECTNESS: Ask the question directly. (e.g., 'What is the maximum height of...' NOT 'Based on the textbook, calculate...')
3. DIFFICULTY: Focus on conceptual depth and mathematical calculations. 
4. PHRASING: Use the formal tone of the Grade 12 National Exam (EUEE).
5. NO TRIVIA: Do not ask about table of contents, authors, or unit numbers. Ask about the SCIENCE and MATH.
"""

# --- 2. CONFIG & THEME ---
st.set_page_config(page_title="EthioExam National", page_icon="🇪🇹", layout="wide")

# Dark Mode Compatible CSS
st.markdown("""
    <style>
    .stRadio [role="radiogroup"] { 
        background-color: rgba(120, 120, 120, 0.1); 
        border: 2px solid #4CAF50; border-radius: 10px; padding: 20px; 
    }
    div[data-testid="stMetricValue"] { color: #4CAF50; font-size: 40px; }
    </style>
    """, unsafe_allow_html=True)

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("🔑 API Key Missing!")

# --- 3. STORAGE & HISTORY ---
def save_history(entry):
    history_file = "exam_history.json"
    data = []
    if os.path.exists(history_file):
        with open(history_file, "r") as f: data = json.load(f)
    data.append(entry)
    with open(history_file, "w") as f: json.dump(data, f)

def load_history():
    if os.path.exists("exam_history.json"):
        with open("exam_history.json", "r") as f: return json.load(f)
    return []

# --- 4. SESSION STATE ---
if "exam" not in st.session_state:
    st.session_state.exam = {"q": [], "idx": 0, "ans": {}, "done": False, "start": None, "time": 0, "unit": ""}

# --- 5. SIDEBAR: HISTORY & CREATION ---
st.sidebar.title("🇪🇹 Exam Portal")

# View History Section
past_exams = load_history()
if past_exams:
    with st.sidebar.expander("📂 Past Exam Results"):
        for h in reversed(past_exams):
            st.write(f"**{h['unit']}**: {h['score']}/{h['total']} ({h['date']})")

st.sidebar.divider()
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
unit = st.sidebar.text_input("Enter Unit Topic", placeholder="e.g. Work and Energy")
num_q = st.sidebar.slider("Number of Questions", 10, 50, 30)

if st.sidebar.button("🔥 Generate National Exam"):
    path = f"textbooks/grade{grade}_{sub.lower()}.pdf"
    if os.path.exists(path):
        with st.spinner("AI is analyzing the topic deepy..."):
            f = genai.upload_file(path=path)
            while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
            
            # Using Gemini 2.5 Flash Lite with System Instruction
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash-lite",
                system_instruction=SYSTEM_PROMPT
            )
            
            prompt = f"Create a {num_q}-question Exam on '{unit}'. Ensure questions involve calculations where appropriate. Return ONLY JSON array: [{{'q':'','a':'','b':'','c':'','d':'','ans':'a','exp':''}}]"
            
            try:
                res = model.generate_content([f, prompt])
                raw = res.text.strip().replace("```json", "").replace("```", "")
                st.session_state.exam.update({
                    "q": json.loads(raw), "idx": 0, "ans": {}, 
                    "done": False, "start": time.time(), 
                    "time": num_q * 120, "unit": unit
                })
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- 6. LIVE EXAM ENGINE ---
ex = st.session_state.exam
if ex["q"] and not ex["done"]:
    # REAL-TIME CLOCK
    rem = ex["time"] - (time.time() - ex["start"])
    if rem <= 0:
        ex["done"] = True
        st.rerun()

    c1, c2 = st.columns([3, 1])
    c1.title(f"National Style: {ex['unit']}")
    m, s = divmod(int(rem), 60)
    c2.metric("Time Remaining", f"{m:02d}:{s:02d}")

    q = ex["q"][ex["idx"]]
    st.progress((ex["idx"] + 1) / len(ex["q"]))
    
    st.subheader(f"Question {ex['idx']+1}")
    st.markdown(f"#### {q['q']}")
    
    # INTERACTIVE CHOICES (No auto-select)
    opts = [q['a'], q['b'], q['c'], q['d']]
    labels = ["A", "B", "C", "D"]
    
    cur_idx = None
    if ex["idx"] in ex["ans"]:
        cur_idx = labels.index(ex["ans"][ex["idx"]].upper())

    choice = st.radio("Select Answer:", opts, index=cur_idx, key=f"q{ex['idx']}")
    
    if choice:
        ex["ans"][ex["idx"]] = labels[opts.index(choice)].lower()

    # NAVIGATION
    b1, b2, b3 = st.columns([1, 1, 1])
    if b1.button("⬅️ Previous") and ex["idx"] > 0:
        ex["idx"] -= 1
        st.rerun()
    if b3.button("Next ➡️" if ex["idx"] < len(ex["q"])-1 else "🏁 Submit"):
        if ex["idx"] < len(ex["q"])-1:
            ex["idx"] += 1
            st.rerun()
        else:
            ex["done"] = True
            st.rerun()

# --- 7. RESULTS & AUTO-SAVE ---
if ex["done"] and ex["q"]:
    score = sum(1 for i, q in enumerate(ex["q"]) if ex["ans"].get(i) == q['ans'])
    st.title("🏆 Exam Result")
    st.metric("Total Score", f"{score} / {len(ex['q'])}")
    
    # Save to file
    save_history({"unit": ex["unit"], "score": score, "total": len(ex["q"]), "date": datetime.now().strftime("%Y-%b-%d %H:%M")})
    
    st.divider()
    for i, q in enumerate(ex["q"]):
        is_right = ex["ans"].get(i) == q['ans']
        with st.expander(f"Q{i+1}: {'✅' if is_right else '❌'} (Answer: {q['ans'].upper()})"):
            st.write(f"**Question:** {q['q']}")
            st.success(f"**Explanation:** {q['exp']}")
    
    if st.button("Take Another Exam"):
        st.session_state.exam["q"] = []
        st.rerun()
