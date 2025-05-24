import streamlit as st
import speech_recognition as sr
import pyttsx3
import threading
import time
import re
from difflib import SequenceMatcher
import queue
import asyncio

# Initialize session state
if "voice_transcript" not in st.session_state:
    st.session_state.voice_transcript = ""
if "listening" not in st.session_state:
    st.session_state.listening = False
if "selected_name" not in st.session_state:
    st.session_state.selected_name = ""
if "last_response" not in st.session_state:
    st.session_state.last_response = ""
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "voice_queue" not in st.session_state:
    st.session_state.voice_queue = queue.Queue()
if "recognition_active" not in st.session_state:
    st.session_state.recognition_active = False

# Enhanced faculty data
faculty_data = {
    "faculty": [
        {"name": "Dr. Manoj Pandey", "designation": "HOD of ECE Department", "room_number": "A1-G12", "aliases": ["manoj", "pandey", "hod", "head"]},
        {"name": "Dr. Pankaj Goswami", "designation": "Dean of Engineering and Applied Science", "room_number": "A1-Ground floor (Near Lift)", "aliases": ["pankaj", "goswami", "dean"]},
        {"name": "Dr. Abhishek Kumar", "designation": "Assistant Professor", "room_number": "A1-G13", "aliases": ["abhishek", "kumar"]},
        {"name": "Dr. Sanjeev Kumar", "designation": "Professor", "room_number": "A1-G08", "aliases": ["sanjeev", "kumar"]}
    ]
}

# Function to get faculty list
@st.cache_data
def load_faculty_data():
    return faculty_data["faculty"]

# Enhanced text similarity function
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# Enhanced name extraction and matching
def extract_and_find_faculty(text, faculty_list):
    text = text.lower().strip()
    
    # Remove common words and clean the text
    common_words = ['where', 'is', 'the', 'room', 'of', 'office', 'cabin', 'sir', 'madam', 'professor', 'doctor', 'dr', 'tell', 'me', 'find', 'locate', 'location']
    words = text.split()
    cleaned_words = [word for word in words if word not in common_words]
    cleaned_text = ' '.join(cleaned_words)
    
    best_match = None
    best_score = 0
    
    for faculty in faculty_list:
        # Check full name similarity
        name_score = similarity(cleaned_text, faculty["name"])
        if name_score > best_score and name_score > 0.6:
            best_match = faculty
            best_score = name_score
        
        # Check individual name parts
        name_parts = faculty["name"].lower().split()
        for part in name_parts:
            if len(part) > 2:  # Avoid matching very short words
                if part in cleaned_text:
                    part_score = 0.8
                    if part_score > best_score:
                        best_match = faculty
                        best_score = part_score
        
        # Check aliases
        for alias in faculty.get("aliases", []):
            if alias in cleaned_text:
                alias_score = 0.7
                if alias_score > best_score:
                    best_match = faculty
                    best_score = alias_score
        
        # Check designation keywords
        designation_keywords = {
            "hod": ["hod", "head of department", "head"],
            "dean": ["dean"],
            "professor": ["professor", "prof"]
        }
        
        for keyword, variants in designation_keywords.items():
            if any(variant in text for variant in variants):
                if keyword in faculty["designation"].lower():
                    keyword_score = 0.9
                    if keyword_score > best_score:
                        best_match = faculty
                        best_score = keyword_score
    
    return best_match

# Voice recognition function that works with Streamlit
class VoiceRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Adjust for ambient noise once
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
    
    def listen_once(self):
        try:
            with self.microphone as source:
                # Listen for audio
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
                # Recognize speech
                text = self.recognizer.recognize_google(audio)
                return {"status": "success", "text": text}
        except sr.WaitTimeoutError:
            return {"status": "timeout", "text": ""}
        except sr.UnknownValueError:
            return {"status": "unclear", "text": ""}
        except sr.RequestError as e:
            return {"status": "error", "text": str(e)}
        except Exception as e:
            return {"status": "exception", "text": str(e)}

# Initialize voice recognizer
@st.cache_resource
def get_voice_recognizer():
    return VoiceRecognizer()

# Enhanced TTS initialization with error handling
def init_tts():
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)
        voices = engine.getProperty('voices')
        if voices:
            engine.setProperty('voice', voices[0].id)
        return engine
    except Exception as e:
        st.warning(f"Text-to-speech initialization failed: {e}")
        return None

# Enhanced text-to-speech function
def speak_text(text):
    def _speak():
        engine = init_tts()
        if engine:
            try:
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                print(f"TTS Error: {e}")
    
    threading.Thread(target=_speak, daemon=True).start()

# Function to get intelligent suggestions
def get_intelligent_suggestions(faculty_list, query):
    if not query or len(query) < 2:
        return []
    
    suggestions = []
    query = query.lower()
    
    for faculty in faculty_list:
        # Check name similarity
        if similarity(query, faculty["name"]) > 0.3:
            suggestions.append(faculty)
        # Check if query is in name or designation
        elif query in faculty["name"].lower() or query in faculty["designation"].lower():
            suggestions.append(faculty)
        # Check aliases
        elif any(query in alias for alias in faculty.get("aliases", [])):
            suggestions.append(faculty)
    
    # Sort by relevance
    suggestions.sort(key=lambda x: similarity(query, x["name"]), reverse=True)
    return suggestions[:4]  # Return top 4 suggestions

# Enhanced response generation
def generate_response(faculty, query_type="general"):
    if not faculty:
        return "I couldn't find any faculty member matching your query. Please try again with a different name."
    
    name = faculty["name"]
    designation = faculty["designation"]
    room = faculty["room_number"]
    
    responses = [
        f"{name}, who is the {designation}, is located in room {room}.",
        f"You can find {name} in room {room}. They are the {designation}.",
        f"{name}'s office is in room {room}.",
        f"Room {room} is where you'll find {name}, the {designation}."
    ]
    
    import random
    return random.choice(responses)

# Streamlit UI
st.set_page_config(
    page_title="Faculty Enquiry System",
    page_icon="🏫",
    layout="wide"
)

st.title("🏫 Faculty Enquiry System")
st.markdown("*Find faculty locations using voice or text input*")

# Load faculty data
faculty_list = load_faculty_data()

# Create two main columns
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("💬 Ask Your Question")
    
    # Text input with placeholder
    query = st.text_input(
        "Type your question:",
        placeholder="e.g., 'Where is Dr. Manoj Pandey?' or 'HOD room number'",
        help="You can ask in natural language like 'Where is the dean's office?' or just type a name"
    )
    
    # Voice input section
    st.subheader("🎤 Voice Input")
    
    col_voice1, col_voice2 = st.columns([1, 1])
    
    with col_voice1:
        # Voice input button with immediate processing
        if st.button("🎤 Click & Speak", help="Click and speak immediately"):
            recognizer = get_voice_recognizer()
            
            with st.spinner("🎧 Listening... Please speak now!"):
                result = recognizer.listen_once()
            
            if result["status"] == "success":
                st.session_state.voice_transcript = result["text"]
                st.success(f"✅ Heard: \"{result['text']}\"")
                
                # Process immediately
                matched_faculty = extract_and_find_faculty(result["text"], faculty_list)
                if matched_faculty:
                    response = generate_response(matched_faculty)
                    st.success(f"🎯 {response}")
                    speak_text(f"{matched_faculty['name']} is in room {matched_faculty['room_number']}")
                    
                    # Add to conversation history
                    st.session_state.conversation_history.append({
                        "query": result["text"],
                        "response": response,
                        "timestamp": time.strftime("%H:%M:%S")
                    })
                else:
                    error_msg = "❌ I couldn't find any faculty member matching your request."
                    st.error(error_msg)
                    speak_text("Sorry, I couldn't find that faculty member. Please try again.")
                    
            elif result["status"] == "timeout":
                st.warning("⏱️ No speech detected. Please try again.")
                speak_text("I didn't hear anything. Please try again.")
            elif result["status"] == "unclear":
                st.warning("🔊 Couldn't understand the speech. Please speak clearly.")
                speak_text("Sorry, I couldn't understand. Please speak clearly.")
            else:
                st.error(f"❌ Voice recognition error: {result['text']}")
                speak_text("There was an error. Please try again.")
    
    with col_voice2:
        # Alternative: Continuous listening mode
        if st.button("🔄 Continuous Mode", help="Keep listening for multiple queries"):
            st.info("🎧 Continuous listening mode activated! Speak multiple queries.")
            recognizer = get_voice_recognizer()
            
            # Listen for multiple inputs
            for i in range(3):  # Allow up to 3 consecutive inputs
                with st.spinner(f"🎧 Listening... (Attempt {i+1}/3)"):
                    result = recognizer.listen_once()
                
                if result["status"] == "success":
                    st.write(f"**Query {i+1}:** \"{result['text']}\"")
                    
                    matched_faculty = extract_and_find_faculty(result["text"], faculty_list)
                    if matched_faculty:
                        response = generate_response(matched_faculty)
                        st.success(f"➤ {response}")
                        speak_text(f"{matched_faculty['name']} is in room {matched_faculty['room_number']}")
                    else:
                        st.error("➤ Faculty not found")
                        speak_text("Faculty not found")
                elif result["status"] == "timeout":
                    st.info("⏱️ No more speech detected. Stopping continuous mode.")
                    break
                else:
                    st.warning(f"⚠️ {result['status']}: {result['text']}")

with col2:
    st.subheader("📋 Faculty Directory")
    
    with st.expander("View All Faculty", expanded=False):
        for faculty in faculty_list:
            st.write(f"**{faculty['name']}**")
            st.write(f"*{faculty['designation']}*")
            st.write(f"📍 Room: {faculty['room_number']}")
            if st.button(f"Get {faculty['name']}'s location", key=f"dir_{faculty['name']}"):
                response = generate_response(faculty)
                st.success(response)
                speak_text(f"{faculty['name']} is in room {faculty['room_number']}")
            st.write("---")

# Process text input with suggestions
if query:
    suggestions = get_intelligent_suggestions(faculty_list, query)
    if suggestions:
        st.subheader("💡 Suggestions")
        cols = st.columns(min(len(suggestions), 2))
        for i, faculty in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(f"📍 {faculty['name']}", key=f"suggestion_{i}"):
                    response = generate_response(faculty)
                    st.success(f"✅ {response}")
                    speak_text(f"{faculty['name']} is in room {faculty['room_number']}")
    
    # Direct processing of text query
    matched_faculty = extract_and_find_faculty(query, faculty_list)
    if matched_faculty and not suggestions:
        response = generate_response(matched_faculty)
        st.success(f"✅ {response}")
        speak_text(f"{matched_faculty['name']} is in room {matched_faculty['room_number']}")

# Conversation History
if st.session_state.conversation_history:
    st.subheader("📜 Recent Queries")
    with st.expander("View Conversation History", expanded=False):
        for entry in reversed(st.session_state.conversation_history[-5:]):  # Show last 5
            st.write(f"**[{entry['timestamp']}]** *{entry['query']}*")
            st.write(f"➤ {entry['response']}")
            st.write("---")

# Help section
with st.expander("ℹ️ How to Use", expanded=False):
    st.markdown("""
    **Voice Commands Examples:**
    - "Where is Dr. Manoj Pandey?"
    - "HOD room number"
    - "Dean's office location"
    - "Abhishek Kumar cabin"
    - "Cabin of Manoj Pandey"
    
    **Text Input Examples:**
    - Type any faculty name
    - Ask "Where is [name]?"
    - Search by designation like "HOD" or "Dean"
    
    **Tips:**
    - Click "🎤 Click & Speak" and speak immediately
    - Speak clearly and at normal pace
    - You can use partial names or common titles
    - Try "Continuous Mode" for multiple queries
    """)

# Clear history button
if st.session_state.conversation_history:
    if st.button("🗑️ Clear History"):
        st.session_state.conversation_history = []
        st.rerun()