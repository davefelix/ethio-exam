import streamlit as st
from google import genai
from google.genai import types
import json
import time
import os
import re

# --- 1. CLOUD SECURITY ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("Setup Error: Please add GEMINI_API_KEY to Streamlit Secrets.")

st.set_page_config(page_title="EthioExam AI", page_icon="🇪🇹", layout="wide")

# --- 2. CLEANER NAMING ---
def clean_name(text):
    # API names must be lowercase, alphanumeric, or dashes only
    return re.sub(r'[^a-z0-9-]', '', text.lower())

def get_book_store(grade, subject):
    # Ensure name is valid for Google API
    clean_sid = clean_name(f"store-g{grade}-{subject}")
    
    if clean_sid not in st.session_state:
        try:
            # Check if store already exists on Google's side to avoid "Already Exists" error
            store = client.file_search_stores.create(config={'display_name': clean_sid})
            path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
            
            if os.path.exists(path):
                with st.spinner(f"AI is reading {subject}..."):
                    op = client.file_search_stores.upload_to_file_search_store(
                        file_search_store_name=store.name, file=path
                    )
                    while not op.done:
                        time.sleep(2)
                        op = client.operations.get(op)
                st.session_state[clean_sid] = store.name
            else:
                st.error(f"File '{path}' missing in GitHub!")
                return None
        except Exception as e:
            st.error(f"API Error during upload: {str(e)}")
            return None
    return st.session_state[clean_sid]

# --- 3. SESSION STATE ---
if "chapters" not in st.session_state:
    st.session_state.update({"chapters": [], "questions": [], "current_idx": 0, "answers": {}, "done": False})

# --- 4. SIDEBAR ---
st.sidebar.header("🎓 Exam Settings")
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])

if st.sidebar.button("🔍 Scan for Chapters"):
    sid = get_book_store(grade, sub)
    if sid:
        with st.spinner("Listing Units..."):
            # Use a slightly more stable model name if 'flash' fails
            prompt = "List all Unit/Chapter names from this book. Just names, comma-separated."
            try:
                response = client.models.generate_content(
                    model="gemini-1.5-flash", 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))]
                    )
                )
                st.session_state.chapters = [c.strip() for c in response.text.split(",")]
                st.rerun()
            except Exception as e:
                st.error(f"Scan Failed: {str(e)}")

# --- 5. EXAM GENERATION ---
if st.session_state.chapters:
    selected_chapter = st.selectbox("Pick a Chapter:", st.session_state.chapters)
    if st.button("🚀 Start 30-Question Exam"):
        sid = get_book_store(grade, sub)
        prompt = f"Using the PDF, find '{selected_chapter}'. Generate 30 MCQs. Return ONLY a JSON array."
        
        with st.spinner("Generating..."):
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash", 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))]
                    )
                )
                # Clean the response for JSON
                raw = response.text.strip().lstrip('```json').rstrip('```').strip()
                st.session_state.update({
                    "questions": json.loads(raw), 
                    "current_idx": 0, "answers": {}, "start_time": time.time(), "done": False
                })
                st.rerun()
            except Exception as e:
                st.error(f"Generation Failed: {str(e)}")

# --- 6. EXAM ENGINE (Simple) ---
if st.session_state.questions and not st.session_state.done:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    st.subheader(f"Question {idx + 1}")
    st.info(q['q'])
    ans = st.radio("Choose:", [q['a'], q['b'], q['c'], q['d']], key=f"q{idx}")
    if st.button("Next"):
        if idx < len(st.session_state.questions)-1:
            st.session_state.current_idx += 1
            st.rerun()
        else:
            st.session_state.done = True
            st.rerun()

if st.session_state.done:
    st.success("Exam Complete!")
    if st.button("Restart"):
        st.session_state.clear()
        st.rerun()
