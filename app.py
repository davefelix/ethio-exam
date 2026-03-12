import streamlit as st
from google import genai
from google.genai import types
import json
import time
import os

# --- 1. SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("🔑 API Key Missing! Check Streamlit Secrets.")

st.set_page_config(page_title="EthioExam AI", page_icon="🇪🇹", layout="wide")

# --- 2. THE BRAIN ---
def get_book_store(grade, subject):
    store_id = f"store-g{grade}-{subject.lower()}"
    if store_id not in st.session_state:
        try:
            store = client.file_search_stores.create(config={'display_name': store_id})
            path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
            if os.path.exists(path):
                with st.status(f"📖 Reading {subject} Grade {grade}...", expanded=False) as s:
                    op = client.file_search_stores.upload_to_file_search_store(
                        file_search_store_name=store.name, file=path
                    )
                    while not op.done:
                        time.sleep(2)
                        op = client.operations.get(op)
                    s.update(label="✅ Ready!", state="complete")
                st.session_state[store_id] = store.name
            else:
                st.error(f"❌ Missing file: {path}")
                return None
        except Exception as e:
            st.error(f"⚠️ Connection Error: {str(e)}")
            return None
    return st.session_state[store_id]

# --- 3. SESSION STATE ---
if "chapters" not in st.session_state:
    st.session_state.update({"chapters": [], "questions": [], "current_idx": 0, "answers": {}, "done": False})

# --- 4. SIDEBAR ---
st.sidebar.title("🇪🇹 EthioExam AI")
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])

if st.sidebar.button("🔍 Scan Book"):
    sid = get_book_store(grade, sub)
    if sid:
        with st.spinner("Finding chapters..."):
            prompt = "List only the Unit/Chapter names from this book, separated by commas."
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))])
                )
                if response.text:
                    st.session_state.chapters = [c.strip() for c in response.text.split(",") if len(c) > 2]
                st.rerun()
            except:
                st.sidebar.warning("Auto-scan failed. Use manual entry below.")

# --- 5. MAIN INTERFACE (THE FIX) ---
if not st.session_state.questions:
    st.markdown("### 📖 Select Chapter")
    
    # If scan worked, show dropdown. If not, show text input.
    if st.session_state.chapters:
        target_unit = st.selectbox("Choose a detected unit:", st.session_state.chapters)
    else:
        st.warning("AI couldn't list chapters automatically.")
        target_unit = st.text_input("Type the Unit Name manually (e.g., 'Unit 1' or 'Vectors'):")

    if st.button("🚀 Start Exam") and target_unit:
        sid = get_book_store(grade, sub)
        with st.spinner(f"Generating 30 questions for {target_unit}..."):
            try:
                prompt = f"Using the PDF, find the chapter '{target_unit}'. Generate 30 MCQs. Format: JSON array ONLY. Include 'q', 'a', 'b', 'c', 'd', 'ans', 'exp'."
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))])
                )
                raw = response.text.strip().lstrip('```json').rstrip('```').strip()
                st.session_state.questions = json.loads(raw)
                st.rerun()
            except Exception as e:
                st.error("Generation failed. Try a simpler unit name.")

# --- 6. EXAM ENGINE ---
if st.session_state.questions and not st.session_state.done:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    st.progress((idx + 1) / len(st.session_state.questions))
    st.info(f"**Question {idx+1}:** {q['q']}")
    ans = st.radio("Select:", [f"A) {q['a']}", f"B) {q['b']}", f"C) {q['c']}", f"D) {q['d']}"], key=f"q{idx}")
    st.session_state.answers[idx] = ans[0].lower()
    if st.button("Next ➡️" if idx < len(st.session_state.questions)-1 else "🏁 Submit"):
        if idx < len(st.session_state.questions)-1:
            st.session_state.current_idx += 1
        else:
            st.session_state.done = True
        st.rerun()

# --- 7. RESULTS ---
if st.session_state.done:
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['ans'])
    st.success(f"Final Score: {score}/{len(st.session_state.questions)}")
    if st.button("New Exam"):
        st.session_state.clear()
        st.rerun()
