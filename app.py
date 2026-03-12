import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. SYSTEM IDENTITY & STYLE ---
SYSTEM_PROMPT = """
ROLE: Senior Developer for the Ethiopian National Entrance Examination (EUEE).
MISSION: Create original, high-level, and challenging Multiple Choice Questions (MCQs).

STRICT GENERATION RULES:
1. NO REPETITION: Do not copy sentences from the textbook. 
2. SCENARIO-BASED: Create NEW word problems and conceptual scenarios based on the laws/facts in the book.
3. CALCULATIONS: 40% of questions MUST be numerical. Invent realistic variables to test formula application.
4. NO FILLER: Never say 'According to the text'. Ask: 'A 5kg block moves at...' or 'Which molecule represents...'
5. UNIT ANCHORING: Stay strictly within the user's requested unit. Forbid any mention of other chapters.
"""

# --- 2. CONFIGURATION ---
st.set_page_config(page_title="EthioExam National Pro", page_icon="🇪🇹", layout="wide")

st.markdown("""
    <style>
    .stRadio [role="radiogroup"] { 
        background-color: rgba(120, 120, 120, 0.1); 
        border: 2px solid #4CAF50; border-radius: 12px; padding: 25px; 
    }
    .stRadio label { font-size: 1.1rem !important; font-weight: 500; color: inherit !important; }
    div[data-testid="stMetricValue"] { color: #4CAF50; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# API SETUP
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🔑 Please add your GEMINI_API_KEY to Streamlit Secrets!")

# --- 3. PERSISTENT STORAGE ---
def save_exam_to_history(entry):
    file = "exam_history.json"
    data = []
    if os.path.exists(file):
        try:
            with open(file, "r") as f: data = json.load(f)
        except: data = []
    data.append(entry)
    with open(file, "w") as f: json.dump(data, f)

def load_exam_history():
    if os.path.exists("exam_history.json"):
        try:
            with open("exam_history.json", "r") as f: return json.load(f)
        except: return []
    return []

# --- 4. SESSION STATE ---
if "exam" not in st.session_state:
    st.session_state.exam = {
        "questions": [], "idx": 0, "user_ans": {}, 
        "done": False, "start_time": None, "total_time": 0, "unit": ""
    }

# --- 5. SIDEBAR ---
st.sidebar.title("📚 Exam Portal")

history = load_exam_history()
if history:
    with st.sidebar.expander("📜 Your Previous Exams"):
        for h in reversed(history):
            st.write(f"**{h['unit']}** | {h['score']}/{h['total']} | {h['date']}")

st.sidebar.divider()
grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
unit_name = st.sidebar.text_input("Specific Unit Topic", placeholder="e.g. Unit 3: Kinematics")
count = st.sidebar.slider("Questions", 5, 50, 20)

if st.sidebar.button("🔥 Generate Hard National Exam"):
    path = f"textbooks/grade{grade}_{sub.lower()}.pdf"
    if os.path.exists(path):
        with st.spinner("AI is crafting high-level questions..."):
            try:
                file_ref = genai.upload_file(path=path)
                while file_ref.state.name == "PROCESSING": 
                    time.sleep(1)
                    file_ref = genai.get_file(file_ref.name)
                
                # FIXED MODEL NAME: gemini-3.1-flash-lite-preview
                model = genai.GenerativeModel(
                    model_name="gemini-3.1-flash-lite-preview",
                    system_instruction=SYSTEM_PROMPT
                )
                
                query = f"Analyze '{unit_name}' only. Create {count} conceptual and calculation-based MCQs. Format: JSON array ONLY."
                
                res = model.generate_content([file_ref, query])
                clean = res.text.strip().replace("```json", "").replace("```", "")
                
                # Double-check for extra characters
                if "[" in clean and "]" in clean:
                    clean = clean[clean.find("["):clean.rfind("]")+1]

                st.session_state.exam.update({
                    "questions": json.loads(clean), "idx": 0, "user_ans": {}, 
                    "done": False, "start_time": time.time(), 
                    "total_time": count * 120, "unit": unit_name
                })
                st.rerun()
            except Exception as e:
                st.error(f"Generation Error: {e}")
    else:
        st.sidebar.error(f"PDF Not Found: {path}")

# --- 6. LIVE EXAM ENGINE ---
ex = st.session_state.exam
if ex["questions"] and not ex["done"]:
    elapsed = time.time() - ex["start_time"]
    remaining = ex["total_time"] - elapsed
    
    if remaining <= 0:
        ex["done"] = True
        st.rerun()

    c1, c2 = st.columns([3, 1])
    c1.title(f"📍 {ex['unit']}")
    m, s = divmod(int(remaining), 60)
    c2.metric("Timer", f"{m:02d}:{s:02d}")

    q_idx = ex["idx"]
    q_data = ex["questions"][q_idx]
    st.progress((q_idx + 1) / len(ex["questions"]))
    
    st.markdown(f"### Question {q_idx + 1}")
    st.info(q_data['q'])
    
    opts = [q_data['a'], q_data['b'], q_data['c'], q_data['d']]
    labels = ["a", "b", "c", "d"]
    
    current_choice = None
    if q_idx in ex["user_ans"]:
        current_choice = labels.index(ex["user_ans"][q_idx])

    user_selection = st.radio("Choose the best answer:", opts, index=current_choice, key=f"radio_{q_idx}")
    
    if user_selection:
        ex["user_ans"][q_idx] = labels[opts.index(user_selection)]

    n1, n2, n3 = st.columns([1, 1, 1])
    if n1.button("⬅️ Back") and q_idx > 0:
        ex["idx"] -= 1
        st.rerun()
    
    if n3.button("Next ➡️" if q_idx < len(ex["questions"])-1 else "🏁 Submit Exam"):
        if q_idx < len(ex["questions"])-1:
            ex["idx"] += 1
            st.rerun()
        else:
            ex["done"] = True
            st.rerun()

# --- 7. FINAL SCORE & REVIEW ---
if ex["done"] and ex["questions"]:
    st.balloons()
    score = sum(1 for i, q in enumerate(ex["questions"]) if ex["user_ans"].get(i) == q['ans'])
    
    st.header("🏆 Performance Report")
    st.metric("Final Score", f"{score} / {len(ex['questions'])}", f"{int(score/len(ex['questions'])*100)}%")
    
    # Save result if it's the first time finishing this specific run
    save_exam_to_history({
        "unit": ex["unit"], "score": score, "total": len(ex["questions"]),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

    st.divider()
    for i, q in enumerate(ex["questions"]):
        u_ans = ex["user_ans"].get(i, "None")
        correct = u_ans == q['ans']
        with st.expander(f"Question {i+1}: {'✅' if correct else '❌'} (Correct: {q['ans'].upper()})"):
            st.write(f"**Question:** {q['q']}")
            st.write(f"**Your Answer:** {u_ans.upper()}")
            st.success(f"**Explanation:** {q['exp']}")

    if st.button("🔄 Take a Different Exam"):
        st.session_state.exam["questions"] = []
        st.rerun()
