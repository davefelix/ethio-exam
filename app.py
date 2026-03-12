import streamlit as st
from google import genai
from google.genai import types
import json
import time
import os

# --- 1. CLOUD SECURITY ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("Setup Error: Please add GEMINI_API_KEY to Streamlit Secrets.")

st.set_page_config(page_title="EthioExam AI", page_icon="🇪🇹", layout="wide")

# --- 2. HELPERS ---
def get_book_store(grade, subject):
    store_id = f"store-g{grade}-{subject.lower()}"
    if store_id not in st.session_state:
        store = client.file_search_stores.create(config={'display_name': store_id})
        path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
        if os.path.exists(path):
            with st.spinner(f"AI is opening the {subject} book..."):
                op = client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store.name, file=path
                )
                while not op.done:
                    time.sleep(2)
                    op = client.operations.get(op)
            st.session_state[store_id] = store.name
        else:
            return None
    return st.session_state[store_id]

# --- 3. SESSION STATE ---
if "chapters" not in st.session_state:
    st.session_state.update({"chapters": [], "questions": [], "current_idx": 0, "answers": {}, "done": False})

# --- 4. SIDEBAR (Step 1: Selection) ---
st.sidebar.header("🎓 National Exam Prep")
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])

# Button to "Scan" the book for chapters
if st.sidebar.button("🔍 Scan Textbook for Chapters"):
    sid = get_book_store(grade, sub)
    if sid:
        with st.spinner("AI is reading the Table of Contents..."):
            prompt = "Read the Table of Contents of this textbook and list all the Unit/Chapter titles. Return ONLY a comma-separated list."
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=prompt,
                config=types.GenerateContentConfig(tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))])
            )
            st.session_state.chapters = [c.strip() for c in response.text.split(",")]
            st.rerun()

# --- 5. MAIN AREA (Step 2: Chapter Selection) ---
if st.session_state.chapters:
    st.write("### 📖 Step 2: Select a Chapter")
    selected_chapter = st.selectbox("Which chapter should I use for the exam?", st.session_state.chapters)
    
    if st.button("🚀 Generate 30 Questions"):
        sid = get_book_store(grade, sub)
        prompt = f"Using the textbook, go to '{selected_chapter}'. Generate 30 MCQs. Return ONLY a JSON array: [{{'q':'','a':'','b':'','c':'','d':'','ans':'a','exp':''}}]"
        
        with st.spinner(f"Generating questions for {selected_chapter}..."):
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=prompt,
                config=types.GenerateContentConfig(tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))])
            )
            json_str = response.text.replace("```json","").replace("```","").strip()
            st.session_state.update({
                "questions": json.loads(json_str), 
                "current_idx": 0, "answers": {}, "start_time": time.time(), "done": False
            })
            st.rerun()

# --- 6. EXAM ENGINE ---
if st.session_state.questions and not st.session_state.done:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    
    st.progress((idx + 1) / 30)
    st.subheader(f"Question {idx + 1}")
    st.info(q['q'])
    
    ans = st.radio("Select Answer:", [f"A) {q['a']}", f"B) {q['b']}", f"C) {q['c']}", f"D) {q['d']}"], key=f"q{idx}")
    st.session_state.answers[idx] = ans[0].lower()

    if st.button("Next Question ➡️" if idx < 29 else "Finish Exam"):
        if idx < 29:
            st.session_state.current_idx += 1
        else:
            st.session_state.done = True
        st.rerun()

# --- 7. RESULTS ---
if st.session_state.done:
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['ans'])
    st.success(f"Exam Finished! Final Score: {score}/30")
    if st.button("Start New Exam"):
        st.session_state.clear()
        st.rerun()
