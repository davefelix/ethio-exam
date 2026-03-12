import streamlit as st
from google import genai
from google.genai import types
import json
import time
import os
import re

# --- 1. SETUP & SECURITY ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("🔑 API Key Missing! Please add it to Streamlit Secrets.")

st.set_page_config(page_title="EthioExam AI", page_icon="🇪🇹", layout="wide")

# --- 2. THE BRAIN (File Search) ---
def get_book_store(grade, subject):
    # API names must be simple: no spaces, lowercase only
    store_id = f"store-g{grade}-{subject.lower()}"
    
    if store_id not in st.session_state:
        try:
            # Step A: Create a 'Knowledge Store' on Google's Server
            store = client.file_search_stores.create(config={'display_name': store_id})
            path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
            
            if os.path.exists(path):
                with st.status(f"📖 Reading Grade {grade} {subject}...", expanded=True) as status:
                    # Step B: Upload the PDF
                    op = client.file_search_stores.upload_to_file_search_store(
                        file_search_store_name=store.name, file=path
                    )
                    # Step C: Wait for the AI to 'Finish Reading' (Index)
                    while not op.done:
                        time.sleep(2)
                        op = client.operations.get(op)
                    status.update(label="✅ Textbook Ready!", state="complete")
                st.session_state[store_id] = store.name
            else:
                st.error(f"❌ File not found: {path}")
                return None
        except Exception as e:
            st.error(f"⚠️ API Connection Error. Please wait 60 seconds. ({str(e)})")
            return None
    return st.session_state[store_id]

# --- 3. SESSION STATE ---
if "chapters" not in st.session_state:
    st.session_state.update({
        "chapters": [], "questions": [], "current_idx": 0, 
        "answers": {}, "done": False, "scanning": False
    })

# --- 4. SIDEBAR ---
st.sidebar.title("🇪🇹 EthioExam AI")
grade = st.sidebar.selectbox("Choose Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Choose Subject", ["Maths", "Physics", "Biology", "Chemistry"])

# SCAN BUTTON
if st.sidebar.button("🔍 Step 1: Scan Chapters", disabled=st.session_state.scanning):
    st.session_state.scanning = True
    sid = get_book_store(grade, sub)
    if sid:
        prompt = "Look at the Table of Contents. List ONLY the Unit/Chapter titles as a comma-separated list. Do not write anything else."
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))]
                )
            )
            st.session_state.chapters = [c.strip() for c in response.text.split(",")]
            st.session_state.scanning = False
            st.rerun()
        except Exception as e:
            st.sidebar.error("Quota full. Wait 1 minute.")
            st.session_state.scanning = False

# --- 5. MAIN INTERFACE ---
if st.session_state.chapters and not st.session_state.questions:
    st.markdown("### 📖 Step 2: Pick your Unit")
    selected = st.selectbox("Which chapter should we focus on?", st.session_state.chapters)
    
    if st.button("🚀 Start 30-Question Exam"):
        sid = get_book_store(grade, sub)
        prompt = f"Using the textbook, go to '{selected}'. Generate 30 MCQs. Format: JSON array ONLY. Include 'q', 'a', 'b', 'c', 'd', 'ans', 'exp'."
        
        with st.spinner("AI is drafting your exam..."):
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))]
                    )
                )
                clean_json = response.text.strip().lstrip('```json').rstrip('```').strip()
                st.session_state.questions = json.loads(clean_json)
                st.session_state.start_time = time.time()
                st.rerun()
            except:
                st.error("Error generating questions. Try again in a moment.")

# --- 6. EXAM ENGINE ---
if st.session_state.questions and not st.session_state.done:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    
    # Header & Progress
    st.progress((idx + 1) / len(st.session_state.questions))
    st.write(f"**Question {idx + 1} of {len(st.session_state.questions)}**")
    
    # The Question
    st.info(q['q'])
    
    # Options
    opts = [f"A) {q['a']}", f"B) {q['b']}", f"C) {q['c']}", f"D) {q['d']}"]
    choice = st.radio("Your Answer:", opts, key=f"q_{idx}")
    st.session_state.answers[idx] = choice[0].lower()

    # Navigation
    if st.button("Next ➡️" if idx < len(st.session_state.questions)-1 else "🏁 Submit Exam"):
        if idx < len(st.session_state.questions)-1:
            st.session_state.current_idx += 1
        else:
            st.session_state.done = True
        st.rerun()

# --- 7. RESULTS ---
if st.session_state.done:
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['ans'])
    st.balloons()
    st.success(f"🏆 You scored {score} out of {len(st.session_state.questions)}!")
    
    if st.button("🔄 Try Another Chapter"):
        st.session_state.clear()
        st.rerun()
