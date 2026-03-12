import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="EthioExam Pro", page_icon="🇪🇹", layout="wide")

# Custom CSS for "Interactive" feel
st.markdown("""
    <style>
    .stRadio [role="radiogroup"] { padding: 10px; border-radius: 10px; background-color: #f0f2f6; }
    .stButton > button { width: 100%; border-radius: 5px; height: 3em; transition: 0.3s; }
    .stButton > button:hover { background-color: #ff4b4b; color: white; }
    </style>
    """, unsafe_allow_html=True)

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception:
    st.error("🔑 API Key Missing in Streamlit Secrets!")

# --- 2. SESSION STATE (The App's Memory) ---
if "questions" not in st.session_state:
    st.session_state.update({
        "questions": [], "current_idx": 0, "answers": {}, 
        "done": False, "start_time": None, "history": []
    })

# --- 3. SIDEBAR: HISTORY & SETTINGS ---
st.sidebar.title("📚 Exam Dashboard")

# Show History
if st.session_state.history:
    st.sidebar.subheader("Previous Exams")
    for idx, h in enumerate(st.session_state.history):
        if st.sidebar.button(f"View: {h['unit']} ({h['score']}/{h['total']})", key=f"hist_{idx}"):
            st.session_state.questions = h['questions']
            st.session_state.answers = h['user_answers']
            st.session_state.done = True
            st.rerun()

st.sidebar.divider()
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
q_count = st.sidebar.slider("Number of Questions", 5, 30, 15)
unit_name = st.sidebar.text_input("Unit Name", placeholder="e.g. Unit 4")

# --- 4. ENGINE FUNCTIONS ---
def process_book(grade, subject):
    path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
    if not os.path.exists(path): return None
    try:
        sample_file = genai.upload_file(path=path)
        while sample_file.state.name == "PROCESSING":
            time.sleep(1)
            sample_file = genai.get_file(sample_file.name)
        return sample_file
    except: return None

if st.sidebar.button("🚀 Generate New Exam"):
    book_ref = process_book(grade, sub)
    if book_ref and unit_name:
        model = genai.GenerativeModel("gemini-2.5-flash-lite") 
        prompt = f"Find '{unit_name}'. Generate {q_count} MCQs. JSON array ONLY: [{{'q':'','a':'','b':'','c':'','d':'','ans':'a/b/c/d','exp':''}}]"
        with st.spinner("AI is crafting your exam..."):
            try:
                response = model.generate_content([book_ref, prompt])
                txt = response.text.strip().replace("```json", "").replace("```", "")
                st.session_state.update({
                    "questions": json.loads(txt), "current_idx": 0, 
                    "answers": {}, "done": False, "start_time": time.time(),
                    "total_time_allowed": q_count * 120 # 2 mins per question
                })
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- 5. THE EXAM INTERFACE ---
if st.session_state.questions and not st.session_state.done:
    # Timer Logic
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.total_time_allowed - elapsed
    
    if remaining <= 0:
        st.session_state.done = True
        st.warning("⏰ Time is up!")
        st.rerun()

    # Header: Timer & Progress
    cols = st.columns([3, 1])
    cols[0].title(f"📖 {unit_name} Exam")
    mins, secs = divmod(int(remaining), 60)
    cols[1].metric("Time Left", f"{mins:02d}:{secs:02d}")
    
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    st.progress((idx + 1) / len(st.session_state.questions))
    
    # Question Card
    st.info(f"**Question {idx + 1}:** {q['q']}")
    
    # Options (Interactive & No Auto-selection)
    options = [f"A) {q['a']}", f"B) {q['b']}", f"C) {q['c']}", f"D) {q['d']}"]
    
    # Map stored answer to index
    current_ans_index = None
    if idx in st.session_state.answers:
        ans_map = {'a':0, 'b':1, 'c':2, 'd':3}
        current_ans_index = ans_map.get(st.session_state.answers[idx])

    selected_opt = st.radio("Select your answer:", options, index=current_ans_index, key=f"radio_{idx}")
    
    if selected_opt:
        st.session_state.answers[idx] = selected_opt[0].lower()

    # Navigation
    nav_cols = st.columns([1, 1, 1])
    if nav_cols[0].button("⬅️ Previous") and idx > 0:
        st.session_state.current_idx -= 1
        st.rerun()
    
    if nav_cols[2].button("Next ➡️" if idx < len(st.session_state.questions)-1 else "🏁 Finish"):
        if idx < len(st.session_state.questions)-1:
            st.session_state.current_idx += 1
        else:
            # Save to history before finishing
            score = sum(1 for i, question in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == question['ans'])
            st.session_state.history.append({
                "unit": unit_name, "score": score, "total": len(st.session_state.questions),
                "questions": st.session_state.questions, "user_answers": st.session_state.answers
            })
            st.session_state.done = True
        st.rerun()

# --- 6. FINAL RESULTS & REVIEW ---
if st.session_state.done:
    st.header("🏆 Exam Results")
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['ans'])
    st.metric("Final Score", f"{score} / {len(st.session_state.questions)}", f"{int(score/len(st.session_state.questions)*100)}%")
    
    if st.button("🔄 Start New Different Exam"):
        st.session_state.questions = []
        st.rerun()

    st.divider()
    st.subheader("📝 Detailed Review & Explanations")
    
    for i, q in enumerate(st.session_state.questions):
        user_ans = st.session_state.answers.get(i, "None")
        is_correct = user_ans == q['ans']
        
        with st.expander(f"Question {i+1}: {'✅' if is_correct else '❌'}"):
            st.write(f"**Q:** {q['q']}")
            st.write(f"**Your Answer:** {user_ans.upper()}")
            st.write(f"**Correct Answer:** {q['ans'].upper()}")
            st.success(f"**AI Explanation:** {q['exp']}")
