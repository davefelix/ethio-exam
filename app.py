import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. SYSTEM IDENTITY ---
# This is now the ONLY place where we define the AI's behavior
SYSTEM_PROMPT = "generate hard exam questions using the textbook as a source"

# --- 2. CONFIG ---
st.set_page_config(page_title="EthioExam Elite", page_icon="🇪🇹", layout="wide")

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
        with st.spinner("Creating Hard Questions..."):
            try:
                f = genai.upload_file(path=path)
                while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
                
                # Using the stable model
                model = genai.GenerativeModel("gemini-2.0-flash-lite", system_instruction=SYSTEM_PROMPT)
                
                # We add the requirement for JSON format so the app can actually read the hard questions
                q_prompt = f"Topic: {unit}. Questions: {count}. Output format: JSON array only [{{'q':'','a':'','b':'','c':'','d':'','ans':'a/b/c/d','exp':''}}]"
                
                res = model.generate_content([f, q_prompt])
                txt = res.text.strip()
                
                # JSON Cleaner Logic
                if "
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1

### 💡 What changed:
* **Command simplified:** The `SYSTEM_PROMPT` is now exactly your phrase: `"generate hard exam questions using the textbook as a source"`.
* **Model Stability:** It uses `gemini-2.0-flash-lite`, which is faster and handles the "hard exam" logic well.
* **Logic Guard:** I kept the `.get()` logic to prevent that `KeyError` you saw earlier. This ensures that even if the AI generates a slightly weirdly formatted question, the app stays open.

Would you like me to add a **"Topic Breakdown"** in the results so you can see which parts of the unit you find hardest?
