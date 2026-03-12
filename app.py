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
    st.session_state.update({"questions": [], "current_idx": 0, "answers": {}, "done": False})

# --- 3. SIDEBAR ---
st.sidebar.title("🇪🇹 EthioExam AI")
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
unit_name = st.sidebar.text_input("Unit Name (e.g. Unit 3)", placeholder="Type unit here...")

# --- 4. UPLOADER ---
def process_book(grade, subject):
    path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
    if not os.path.exists(path):
        st.error(f"File not found: {path}")
        return None
    
    with st.spinner("AI is opening the book..."):
        try:
            # Direct upload to Gemini
            sample_file = genai.upload_file(path=path)
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
        st.sidebar.error("Enter a Unit name first!")
    else:
        book_ref = process_book(grade, sub)
        if book_ref:
            # CHANGED: Using gemini-2.5-flash-lite (The only reliable free model right now)
            model = genai.GenerativeModel("gemini-2.5-flash-lite") 
            prompt = f"Find '{unit_name}' in this book. Generate 15 MCQs. Format: JSON array ONLY. Keys: q, a, b, c, d, ans, exp."
            
            with st.spinner("Creating your exam..."):
                try:
                    response = model.generate_content([book_ref, prompt])
                    txt = response.text.strip().replace("```json", "").replace("```", "")
                    st.session_state.questions = json.loads(txt)
                    st.session_state.current_idx = 0
                    st.session_state.done = False
                    st.rerun()
                except Exception as e:
                    if "429" in str(e):
                        st.error("Too many requests! Please wait 60 seconds and click Generate again.")
                    else:
                        st.error(f"Error: {e}")

# --- 6. EXAM ENGINE ---
if st.session_state.questions and not st.session_state.done:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    
    st.progress((idx + 1) / len(st.session_state.questions))
    st.write(f"### Question {idx + 1}")
    st.info(q['q'])
    
    ans = st.radio("Choose:", [q['a'], q['b'], q['c'], q['d']], key=f"q{idx}")
    st.session_state.answers[idx] = ans
    
    if st.button("Next ➡️" if idx < len(st.session_state.questions)-1 else "Finish"):
        if idx < len(st.session_state.questions)-1:
            st.session_state.current_idx += 1
        else:
            st.session_state.done = True
        st.rerun()

# --- 7. RESULTS ---
if st.session_state.done:
    st.success("Exam Complete!")
    if st.button("New Exam"):
        st.session_state.questions = []
        st.rerun()
