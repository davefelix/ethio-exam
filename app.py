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

# --- 2. INTERFACE STYLE ---
st.markdown("""
    <style>
    .stRadio [role=radiogroup]{ background-color: #f8f9fa; padding: 15px; border-radius: 12px; border: 1px solid #ddd; }
    .timer { font-size: 22px; font-weight: bold; color: #d9534f; text-align: right; }
    .main-card { background-color: #ffffff; padding: 25px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# --- 3. PERSISTENT BOOK STORAGE ---
def get_book_store(grade, subject):
    store_id = f"store_g{grade}_{subject.lower()}"
    if store_id not in st.session_state:
        store = client.file_search_stores.create(config={'display_name': store_id})
        path = f"textbooks/grade{grade}_{subject.lower()}.pdf"
        if os.path.exists(path):
            with st.spinner(f"Reading {subject} Grade {grade} Textbook..."):
                client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store.name, file=path
                )
            st.session_state[store_id] = store.name
        else:
            st.error(f"⚠️ File Not Found: Please ensure '{path}' is in the textbooks folder.")
            return None
    return st.session_state[store_id]

# --- 4. SESSION STATE ---
if "questions" not in st.session_state:
    st.session_state.update({"questions": [], "current_idx": 0, "answers": {}, "start_time": None, "done": False})

# --- 5. SIDEBAR NAVIGATION ---
st.sidebar.header("🎓 National Exam Prep")
grade_choice = st.sidebar.selectbox("Select Grade", [9, 10, 11, 12])
subject_choice = st.sidebar.selectbox("Select Subject", ["Maths", "Physics", "Biology", "Chemistry"])

# Since unit counts vary, we let the user type the Unit Number/Name
unit_choice = st.sidebar.text_input("Enter Unit/Chapter (e.g., Unit 1 or Unit 4)")

if st.sidebar.button("✨ Generate 30 Questions"):
    if not unit_choice:
        st.sidebar.warning("Please enter a Unit name or number.")
    else:
        sid = get_book_store(grade_choice, subject_choice)
        if sid:
            prompt = f"""
            Identify '{unit_choice}' in the {subject_choice} Grade {grade_choice} textbook.
            Generate 30 Multiple Choice Questions from this unit ONLY.
            - 15 Conceptual/Theory questions.
            - 15 Calculation/Application questions (if applicable).
            Return ONLY a valid JSON array: 
            [{{"q":"question","a":"opt1","b":"opt2","c":"opt3","d":"opt4","ans":"a","exp":"explanation"}}]
            """
            with st.spinner("AI is analyzing the textbook and drafting 30 unique questions..."):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash", 
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[sid]))]
                        )
                    )
                    json_str = response.text.replace("```json","").replace("```","").strip()
                    st.session_state.update({
                        "questions": json.loads(json_str), 
                        "current_idx": 0, "answers": {}, 
                        "start_time": time.time(), "done": False
                    })
                    st.rerun()
                except Exception as e:
                    st.error("Generation failed. Please check your Unit Name and try again.")

# --- 6. EXAM ENGINE ---
if st.session_state.questions and not st.session_state.done:
    # 40-minute Countdown
    rem = max(0, 2400 - int(time.time() - st.session_state.start_time))
    m, s = divmod(rem, 60)
    st.markdown(f'<p class="timer">⏳ Time: {m:02d}:{s:02d}</p>', unsafe_allow_html=True)
    
    if rem <= 0:
        st.session_state.done = True
        st.rerun()

    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    
    st.progress((idx + 1) / 30)
    st.write(f"### Question {idx + 1} of 30")
    
    with st.container():
        st.markdown(f'<div class="main-card"><strong>{q["q"]}</strong></div>', unsafe_allow_html=True)
        st.write("")
        
        opts = [f"A) {q['a']}", f"B) {q['b']}", f"C) {q['c']}", f"D) {q['d']}"]
        # Maintain selection if user goes back
        current_ans = st.session_state.answers.get(idx, None)
        index = "abcd".find(current_ans) if current_ans else None
        
        choice = st.radio("Choose the correct answer:", opts, key=f"radio_{idx}", index=index)
        if choice:
            st.session_state.answers[idx] = choice[0].lower()

    # Nav
    col1, col2 = st.columns([1,1])
    if col1.button("⬅️ Previous") and idx > 0:
        st.session_state.current_idx -= 1
        st.rerun()
    if col2.button("Next ➡️" if idx < 29 else "🏁 Finish"):
        if idx < 29:
            st.session_state.current_idx += 1
        else:
            st.session_state.done = True
        st.rerun()

# --- 7. RESULTS ---
if st.session_state.done:
    score = sum(1 for i, q in enumerate(st.session_state.questions) if st.session_state.answers.get(i) == q['ans'])
    st.header("🎯 Your Results")
    st.metric("Final Score", f"{score}/30", f"{int((score/30)*100)}%")
    
    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Q{i+1}: {q['q'][:60]}..."):
            st.write(f"**Question:** {q['q']}")
            st.write(f"**Correct Answer:** {q['ans'].upper()}")
            st.info(f"**Explanation:** {q['exp']}")
