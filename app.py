import streamlit as st
from google import genai
from google.genai import types
import json
import time
import os

# --- 1. CLOUD SECURITY ---
# This pulls the key from Streamlit's secret vault when you go live
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("Setup Error: Please add GEMINI_API_KEY to Streamlit Secrets.")

st.set_page_config(page_title="Ethiopian Exam AI", layout="wide")

# --- 2. INTERFACE STYLE (CSS) ---
st.markdown("""
    <style>
    .stRadio [role=radiogroup]{ 
        background-color: #f0f2f6; 
        padding: 20px; 
        border-radius: 15px; 
        border: 1px solid #ddd; 
    }
    .timer { 
        font-size: 22px; 
        font-weight: bold; 
        color: #d9534f; 
        text-align: right; 
        padding-bottom: 10px;
    }
    .question-box {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #007bff;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. PERSISTENT STORAGE (The Digital Library) ---
def get_book_store(grade, subject):
    store_id = f"store_g{grade}_{subject.lower()}"
    if store_id not in st.session_state:
        # Create a persistent store so it only reads the PDF once
        store = client.file_search_stores.create(config={'display_name': store_id})
        path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
        if os.path.exists(path):
            with st.spinner("AI is indexing the textbook... please wait."):
                client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store.name, file=path
                )
            st.session_state[store_id] = store.name
        else:
            st.error(f"Missing file: {path}. Please upload it to your 'textbooks' folder.")
            return None
    return st.session_state[store_id]

# --- 4. SESSION MANAGEMENT ---
if "questions" not in st.session_state:
    st.session_state.update({"questions": [], "current_idx": 0, "answers": {}, "start_time": None, "done": False})

# --- 5. SIDEBAR ---
st.sidebar.title("🇪🇹 Ethio-Exam AI")
grade = st.sidebar.selectbox("Select Grade", [9, 10, 11, 12])
subject = st.sidebar.selectbox("Subject", ["Physics", "Biology", "Chemistry", "Maths"])
chapter = st.sidebar.text_input("Chapter Name/Number")

if st.sidebar.button("Generate 30 Questions") and chapter:
    sid = get_book_store(grade, subject)
    if sid:
        # Prompting Gemini to return structured JSON from the File Search tool
        prompt = f"Using the textbook, go to {chapter}. Generate 30 Multiple Choice Questions (15 conceptual, 15 calculational). Return ONLY a JSON array: [{{'q':'','a':'','b':'','c':'','d':'','ans':'a','exp':''}}]"
        
        with st.spinner("Creating 30 fresh questions..."):
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))]
                )
            )
            
            try:
                json_str = response.text.replace("```json","").replace("```","").strip()
                st.session_state.update({
                    "questions": json.loads(json_str), 
                    "current_idx": 0, 
                    "answers": {}, 
                    "start_time": time.time(), 
                    "done": False
                })
                st.rerun()
            except:
                st.error("The AI failed to format the JSON. Please try generating again.")

# --- 6. EXAM ENGINE ---
if st.session_state.questions and not st.session_state.done:
    # 40 Minute Timer (2400 seconds)
    rem = max(0, 2400 - int(time.time() - st.session_state.start_time))
    st.markdown(f'<p class="timer">⏳ Time Remaining: {rem//60:02d}:{rem%60:02d}</p>', unsafe_allow_html=True)
    
    if rem <= 0: 
        st.session_state.done = True
        st.rerun()

    curr = st.session_state.current_idx
    q_data = st.session_state.questions[curr]
    
    st.progress((curr + 1) / 30)
    st.write(f"### Question {curr + 1} of 30")
    
    st.markdown(f'<div class="question-box">{q_data["q"]}</div>', unsafe_allow_html=True)
    
    opts = [f"A) {q_data['a']}", f"B) {q_data['b']}", f"C) {q_data['c']}", f"D) {q_data['d']}"]
    
    # Pre-select if user returns to this question
    existing_ans_idx = None
    if curr in st.session_state.answers:
        existing_ans_idx = "abcd".find(st.session_state.answers[curr])

    choice = st.radio("Choose the best option:", opts, key=f"q{curr}", index=existing_ans_idx)
    
    if choice:
        st.session_state.answers[curr] = choice[0].lower()

    # Navigation Buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("⬅️ Previous") and curr > 0: 
            st.session_state.current_idx -= 1
            st.rerun()
    with col3:
        if curr < 29:
            if st.button("Next Question ➡️"): 
                st.session_state.current_idx += 1
                st.rerun()
        else:
            if st.button("🏁 FINISH & SUBMIT"): 
                st.session_state.done = True
                st.rerun()

# --- 7. RESULTS & EXPLANATIONS ---
if st.session_state.done:
    st.header("Exam Results")
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['ans'])
    
    st.balloons()
    st.metric("Total Score", f"{score} / 30", f"{int((score/30)*100)}%")
    
    st.write("---")
    st.write("### Detailed Review")
    
    for i, q in enumerate(st.session_state.questions):
        user_ans = st.session_state.answers.get(i, "None")
        is_correct = user_ans == q['ans']
        
        with st.expander(f"Q{i+1}: {'✅' if is_correct else '❌'} {q['q'][:50]}..."):
            st.write(f"**Full Question:** {q['q']}")
            st.write(f"**Your Answer:** {user_ans.upper()}")
            st.write(f"**Correct Answer:** {q['ans'].upper()}")
            st.info(f"**Textbook Explanation:** {q['exp']}")
