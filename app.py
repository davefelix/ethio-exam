import streamlit as st
import google.generativeai as genai
import json
import time
import os
from datetime import datetime

# --- 1. SYSTEM IDENTITY ---
SYSTEM_PROMPT = """
You are the Lead Examiner for the Ethiopian National Secondary School Leaving Examination.

Your job is to generate ORIGINAL and DIFFICULT exam questions.

Question Design Rules:
- 40% numerical calculation questions requiring multi-step reasoning
- 60% conceptual or analytical questions
- Avoid simple memorization questions
- Questions must require reasoning and deep understanding
- Use realistic but invented values for calculations
- Distractor options must be plausible
- Avoid obvious wrong answers

Difficulty:
Questions must match the hardest Ethiopian National Exam level.

Formatting Rules:
Return ONLY a valid JSON array.
Do not include markdown.
Do not include any explanation outside JSON.

Required JSON format:

[
{
"q": "question text",
"a": "option",
"b": "option",
"c": "option",
"d": "option",
"ans": "a/b/c/d",
"exp": "clear reasoning explanation"
}
]
"""

# --- 2. CONFIG ---
st.set_page_config(page_title="EthioExam Pro", page_icon="🇪🇹", layout="wide")

st.markdown("""
<style>
.stRadio [role="radiogroup"] { 
    background-color: rgba(100, 100, 100, 0.1); 
    border: 2px solid #4CAF50; 
    border-radius: 10px; 
    padding: 20px; 
}
.stRadio label { 
    color: inherit !important; 
    font-size: 1.1rem; 
}
</style>
""", unsafe_allow_html=True)

# --- GEMINI CONFIG ---
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
            with open(file, "r") as f:
                data = json.load(f)
        except:
            data = []

    data.append(entry)

    with open(file, "w") as f:
        json.dump(data, f)

# --- 4. SESSION STATE ---
if "exam" not in st.session_state:
    st.session_state.exam = {
        "q": [],
        "idx": 0,
        "ans": {},
        "done": False,
        "start": 0,
        "time": 0,
        "unit": ""
    }

# --- 5. SIDEBAR ---
st.sidebar.title("🇪🇹 Exam Portal")

grade = st.sidebar.selectbox("Grade", [9, 10, 11, 12])
sub = st.sidebar.selectbox("Subject", ["Maths", "Physics", "Biology", "Chemistry"])
unit = st.sidebar.text_input("Unit Topic", placeholder="e.g. Unit 2: Forces")
count = st.sidebar.slider("Questions", 5, 40, 20)

if st.sidebar.button("🔥 Generate Exam"):

    path = f"textbooks/grade{grade}_{sub.lower()}.pdf"

    if os.path.exists(path):

        with st.spinner("Generating challenging exam questions..."):

            try:
                # Upload textbook
                f = genai.upload_file(path=path)

                while f.state.name == "PROCESSING":
                    time.sleep(1)
                    f = genai.get_file(f.name)

                # Use stronger reasoning model
                model = genai.GenerativeModel(
                    "gemini-1.5-pro",
                    system_instruction=SYSTEM_PROMPT
                )

                # Strong question prompt
                q_prompt = f"""
Generate {count} challenging multiple-choice questions.

Exam Context:
Grade: {grade}
Subject: {sub}
Unit: {unit}

Requirements:
- 40% numerical calculation questions
- 60% conceptual or analytical questions
- Calculation questions must require multiple steps
- Use realistic invented numbers
- Distractor answers should reflect common student mistakes
- Avoid definition-based questions
- Use formulas and concepts from the uploaded textbook

Return ONLY valid JSON.
"""

                res = model.generate_content(
                    [f, q_prompt],
                    generation_config={
                        "temperature": 0.9,
                        "top_p": 0.95,
                        "top_k": 40,
                        "max_output_tokens": 8000
                    }
                )

                txt = res.text.strip()

                # JSON Cleaner
                if "```json" in txt:
                    txt = txt.split("```json")[1].split("```")[0].strip()
                elif "```" in txt:
                    txt = txt.split("```")[1].split("```")[0].strip()

                parsed_questions = json.loads(txt)

                # Validate structure
                if all('q' in item for item in parsed_questions):

                    st.session_state.exam.update({
                        "q": parsed_questions,
                        "idx": 0,
                        "ans": {},
                        "done": False,
                        "start": time.time(),
                        "time": count * 120,
                        "unit": unit
                    })

                    st.rerun()

                else:
                    st.error("AI returned improperly formatted questions. Try again.")

            except Exception as e:
                st.error(f"Generation Error: {e}")

# --- 6. EXAM ENGINE ---
ex = st.session_state.exam

if ex["q"] and not ex["done"]:

    # Timer
    rem = ex["time"] - (time.time() - ex["start"])

    if rem <= 0:
        ex["done"] = True
        st.rerun()

    c1, c2 = st.columns([3, 1])

    c1.title(f"📍 {ex['unit']}")

    m, s = divmod(int(rem), 60)
    c2.metric("Timer", f"{m:02d}:{s:02d}")

    q_data = ex["q"][ex["idx"]]

    st.progress((ex["idx"] + 1) / len(ex["q"]))

    st.markdown(f"### Question {ex['idx'] + 1}")

    st.info(q_data.get("q", "Question text missing"))

    opts = [
        q_data.get("a", ""),
        q_data.get("b", ""),
        q_data.get("c", ""),
        q_data.get("d", "")
    ]

    labels = ["a", "b", "c", "d"]

    cur = None

    if ex["idx"] in ex["ans"]:
        cur = labels.index(ex["ans"][ex["idx"]])

    ans = st.radio(
        "Select Answer:",
        opts,
        index=cur,
        key=f"q_{ex['idx']}"
    )

    if ans:
        ex["ans"][ex["idx"]] = labels[opts.index(ans)]

    # Navigation
    b1, b2, b3 = st.columns([1, 1, 1])

    if b1.button("⬅️ Back") and ex["idx"] > 0:
        ex["idx"] -= 1
        st.rerun()

    if b3.button("Next ➡️" if ex["idx"] < len(ex["q"]) - 1 else "🏁 Finish"):

        if ex["idx"] < len(ex["q"]) - 1:
            ex["idx"] += 1
            st.rerun()

        else:
            ex["done"] = True
            st.rerun()

# --- 7. RESULTS ---
if ex["done"] and ex["q"]:

    score = sum(
        1 for i, q in enumerate(ex["q"])
        if ex["ans"].get(i) == q.get("ans")
    )

    st.header(f"Final Score: {score} / {len(ex['q'])}")

    save_history({
        "unit": ex["unit"],
        "score": score,
        "total": len(ex["q"]),
        "date": datetime.now().strftime("%Y-%m-%d")
    })

    for i, q in enumerate(ex["q"]):

        is_right = ex["ans"].get(i) == q.get("ans")

        with st.expander(f"Q{i+1}: {'✅' if is_right else '❌'}"):

            st.write(f"**Question:** {q.get('q')}")

            st.success(f"**Explanation:** {q.get('exp')}")

    if st.button("New Exam"):
        st.session_state.exam["q"] = []
        st.rerun()
