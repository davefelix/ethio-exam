import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. CONFIG & DARK MODE CSS ---
st.set_page_config(page_title="EthioExam Elite", page_icon="🇪🇹", layout="wide")

st.markdown("""
    <style>
    /* Fix for Dark Mode visibility */
    .stRadio [role="radiogroup"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #4CAF50;
        border-radius: 10px;
        padding: 15px;
    }
    .stRadio label {
        color: inherit !important; /* Forces text to follow theme */
        font-weight: 500;
    }
    div[data-testid="stMetricValue"] { color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("🔑 API Key Missing!")

# --- 3. SESSION STATE ---
if "state" not in st.session_state:
    st.session_state.state = {
        "questions": [], "idx": 0, "answers": {}, 
        "done": False, "start_time": None, "history": [],
        "unit": "", "limit_time": 0
    }

# --- 4. THE BRAIN (Advanced Prompting) ---
def generate_hard_exam(file_ref, unit, count):
    # This prompt forces the AI to be a "Hard" teacher
    prompt = f"""
    ROLE: Senior Ethiopian National Exam Developer.
    TASK: Generate {count} HIGH-LEVEL Multiple Choice Questions for '{unit}'.
    
    STRICT RULES:
    1. SOURCE: Use ONLY the provided textbook content.
    2. BOUNDARY: Do NOT include content from other Units. Stay strictly within {unit}.
    3. DIFFICULTY: Include 30% calculation-based questions (if applicable) and 40% conceptual/analysis questions.
    4. NO FILLER: Never ask 'What is not covered' or 'Who wrote this book'. Ask about the science/math concepts.
    5. FORMAT: Return ONLY a valid JSON array. 
    Example: [{{"q":"Calculate the force...","a":"10N","b":"20N","c":"5N","d":"15N","ans":"a","exp":"Using F=ma, 2kg * 5m/s2 = 10N"}}]
    """
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    response = model.generate_content([file_ref, prompt])
    clean_txt = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(clean_txt)

# --- 5. SIDEBAR & UPLOADER ---
st.sidebar.title("🇪🇹 EthioExam Elite")
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
unit_input = st.sidebar.text_input("Specific Unit (e.g. Unit 1: Vectors)")
q_num = st.sidebar.slider("Questions", 10, 30, 20)

if st.sidebar.button("🚀 Create Hard Exam"):
    path = f"textbooks/grade{grade}_{sub.lower()}.pdf"
    if os.path.exists(path):
        with st.spinner("Analyzing Chapter..."):
            f_ref = genai.upload_file(path=path)
            while f_ref.state.name == "PROCESSING": time.sleep(1); f_ref = genai.get_file(f_ref.name)
            
            st.session_state.state["questions"] = generate_hard_exam(f_ref, unit_input, q_num)
            st.session_state.state["unit"] = unit_input
            st.session_state.state["start_time"] = time.time()
            st.session_state.state["limit_time"] = q_num * 120 # 2 mins each
            st.session_state.state["idx"] = 0
            st.session_state.state["answers"] = {}
            st.session_state.state["done"] = False
            st.rerun()

# --- 6. EXAM UI ---
s = st.session_state.state
if s["questions"] and not s["done"]:
    # REAL-TIME TIMER
    elapsed = time.time() - s["start_time"]
    remaining = s["limit_time"] - elapsed
    
    if remaining <= 0:
        s["done"] = True
        st.rerun()

    t_col1, t_col2 = st.columns([3,1])
    t_col1.subheader(f"Unit: {s['unit']}")
    mins, secs = divmod(int(remaining), 60)
    t_col2.metric("Timer", f"{mins:02d}:{secs:02d}")

    # Question Display
    q = s["questions"][s["idx"]]
    st.progress((s["idx"] + 1) / len(s["questions"]))
    
    st.markdown(f"#### Q{s['idx']+1}: {q['q']}")
    
    # NO AUTO-TICK: index=None forces user to select
    opts = [f"A) {q['a']}", f"B) {q['b']}", f"C) {q['c']}", f"D) {q['d']}"]
    
    # Track selection
    cur_val = None
    if s["idx"] in s["answers"]:
        mapping = {'a':0, 'b':1, 'c':2, 'd':3}
        cur_val = mapping.get(s["answers"][s["idx"]])

    ans = st.radio("Choose the correct option:", opts, index=cur_val, key=f"r_{s['idx']}")
    
    if ans:
        s["answers"][s["idx"]] = ans[0].lower()

    # Nav
    n1, n2, n3 = st.columns([1,1,1])
    if n1.button("⬅️ Back") and s["idx"] > 0:
        s["idx"] -= 1
        st.rerun()
    if n3.button("Next ➡️" if s["idx"] < len(s["questions"])-1 else "🏁 Submit"):
        if s["idx"] < len(s["questions"])-1:
            s["idx"] += 1
            st.rerun()
        else:
            s["done"] = True
            st.rerun()

# --- 7. RESULTS & EXPLANATIONS ---
if s["done"] and s["questions"]:
    st.balloons()
    score = sum(1 for i, q in enumerate(s["questions"]) if s["answers"].get(i) == q['ans'])
    st.header(f"Final Result: {score}/{len(s['questions'])}")
    
    # History Save (Local Session)
    if {"unit": s["unit"], "score": score} not in s["history"]:
        s["history"].append({"unit": s["unit"], "score": score, "date": datetime.now().strftime("%Y-%m-%d")})

    for i, q in enumerate(s["questions"]):
        u_ans = s["answers"].get(i, "None")
        is_right = u_ans == q['ans']
        with st.expander(f"Q{i+1}: {'✅' if is_right else '❌'} (Correct: {q['ans'].upper()})"):
            st.write(f"**Question:** {q['q']}")
            st.write(f"**Explanation:** {q['exp']}")

    if st.button("Clear and Start New"):
        s["questions"] = []
        st.rerun()
