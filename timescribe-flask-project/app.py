import os, dotenv
import json
from flask import Flask, render_template, request, Response, session, redirect
from flask_cors import CORS  # To handle cross-origin requests
from groq import Groq

dotenv.load_dotenv()
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)  # Allow all domains for now (development only)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

@app.route("/")
def index():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    else:
        print(f"User ID: {user_id} is logged in")
        return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Handle login logic here
        user_id = request.form.get("user_id")
        if user_id:
            session["user_id"] = user_id
            return redirect("/")
        else:
            return "Please provide a user ID", 400
    # Render a simple login page
    else:
        return render_template("login.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("message", "")

    if not user_input:
        return {"error": "No message provided"}, 400
    
    def stream():
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": user_input}],
            temperature=1,
            max_completion_tokens=1024,
            top_p=1,
            stream=True,
        )
        for chunk in completion:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    return Response(stream(), mimetype="text/plain")

app.route("/transcribe", methods=["POST"])
def transcribe():
    # Specify the path to the audio file
    filename = os.path.dirname(__file__) + "recording.webm" # Replace with your audio file!
    # Open the audio file
    with open(filename, "rb") as file:
    # Create a translation of the audio file
        translation = client.audio.translations.create(
        file=(filename, file.read()), # Required audio file
        model="distil-whisper-large-v3-en", # Required model to use for translation
        prompt="Specify context or spelling",  # Optional
        language="en", # Optional ('en' only)
        response_format="json",  # Optional
        temperature=0.0  # Optional
    )
    # Return the translation text as a response
    if translation.text:
        transcription = translation.text
    else:
        return {"error": "No translation available"}, 400
    
    print(transcription)
    
    return Response(transcription, mimetype="text/plain")
        
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    app.run(debug=True, host="0.0.0.0", port=port)
