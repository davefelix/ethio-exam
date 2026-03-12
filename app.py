import streamlit as st
import google.generativeai as genai
import json
import time
import os

# --- 1. SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception:
    st.error("🔑 API Key Missing in Streamlit Secrets!")

st.set_page_config(page_title="EthioExam AI", page_icon="🇪🇹", layout="wide")

# --- 2. SESSION STATE ---
if "questions" not in st.session_state:
    st.session_state.update({
        "questions": [], "current_idx": 0, "answers": {}, "done": False, "file_ref": None
    })

# --- 3. SIDEBAR ---
st.sidebar.title("🇪🇹 EthioExam AI")
st.sidebar.info("Upload once, then generate any exam.")
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
unit_name = st.sidebar.text_input("Unit Name/Number", placeholder="e.g., Unit 2")

# --- 4. THE POWERFUL UPLOADER ---
def process_book(grade, subject):
    path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
    if not os.path.exists(path):
        st.error(f"File not found: {path}")
        return None
    
    # Upload directly to Gemini's temporary cache
    with st.spinner("AI is reading the textbook directly..."):
        try:
            sample_file = genai.upload_file(path=path)
            # Wait for file to be processed
            while sample_file.state.name == "PROCESSING":
                time.sleep(2)
                sample_file = genai.get_file(sample_file.name)
            return sample_file
        except Exception as e:
            st.error(f"Upload failed: {e}")
            return None

# --- 5. GENERATION ---
if st.sidebar.button("🚀 Generate Exam"):
    if not unit_name:
        st.sidebar.error("Please enter a Unit name!")
    else:
        book_file = process_book(grade, sub)
        if book_file:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Using this textbook, find '{unit_name}'. Generate exactly 20 high-quality MCQs. Return ONLY a JSON array with keys: q, a, b, c, d, ans, exp. Do not include markdown formatting."
            
            with st.spinner("Generating 20 Questions..."):
                try:
                    response = model.generate_content([book_file, prompt])
                    # Clean the JSON
                    raw = response.text.strip().replace("```json", "").replace("```", "")
                    st.session_state.questions = json.loads(raw)
                    st.session_state.current_idx = 0
                    st.session_state.answers = {}
                    st.session_state.done = False
                    st.rerun()
                except Exception as e:
                    st.error(f"AI Error: {e}")

# --- 6. EXAM UI ---
if st.session_state.questions and not st.session_state.done:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    
    st.progress((idx + 1) / len(st.session_state.questions))
    st.write(f"### Question {idx + 1}")
    st.info(q['q'])
    
    choices = [f"A) {q['a']}", f"B) {q['b']}", f"C) {q['c']}", f"D) {q['d']}"]
    ans = st.radio("Select your answer:", choices, key=f"q{idx}")
    st.session_state.answers[idx] = ans[0].lower()
    
    col1, col2 = st.columns(2)
    if col1.button("⬅️ Back") and idx > 0:
        st.session_state.current_idx -= 1
        st.rerun()
    if col2.button("Next ➡️" if idx < len(st.session_state.questions)-1 else "🏁 Submit"):
        if idx < len(st.session_state.questions)-1:
            st.session_state.current_idx += 1
        else:
            st.session_state.done = True
        st.rerun()

# --- 7. RESULTS ---
if st.session_state.done:
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['ans'])
    st.success(f"Final Score: {score}/{len(st.session_state.questions)}")
    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Review Q{i+1}"):
            st.write(f"Correct Answer: {q['ans'].upper()}")
            st.write(f"Explanation: {q['exp']}")
    if st.button("New Exam"):
        st.session_state.questions = []
        st.rerun()
