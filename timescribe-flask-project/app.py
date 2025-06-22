import os, dotenv
import datetime
from flask import Flask, render_template, request, Response, session, redirect, jsonify
from flask_cors import CORS  # To handle cross-origin requests
from groq import Groq
from letta_client import Letta, MessageCreate
import requests
from supabase import create_client, Client

dotenv.load_dotenv()
letta_client = Letta(token=os.getenv("LETTA_API_KEY"))
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)
groq_client = Groq(
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
        # Check if this user already has an agent
        existing = supabase.table("agent_ids").select("*").eq("user_id", user_id).execute()
        if existing.data:
            agent_id = existing.data[0]['agent_id']
            print(f"Agent already exists for {user_id}: {agent_id}")
        else:
            agent = letta_client.agents.create(
                model="openai/gpt-4o-mini",
                embedding="openai/text-embedding-3-small",
                memory_blocks=[
                    {"label": "human", "value": f"User name: {user_id}"},
                    {"label": "persona", "value": "You are a memory journal keeper, helping users track their thoughts and experiences."}
                ]
            )
            agent_id = agent.id
            supabase.table("agent_ids").insert({
                "user_id": user_id,
                "agent_id": agent_id
            }).execute()
            print(f"Created new agent for {user_id}: {agent_id}")
        session["agent_id"] = agent_id
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
    datetime_now = datetime.datetime.now().strftime(r"%Y-%m-%d %H:%M")
    user_input = f"{datetime_now} \n\n{user_input}"
    print(f"User input: {user_input}")
    if not user_input:
        return {"error": "No message provided"}, 400

    try:
        response = letta_client.agents.messages.create(
            agent_id=session.get("agent_id"),
            messages=[
                MessageCreate(
                    role="user",
                    content=user_input,
                ),
            ],
        )
        print("Letta response:", response)
    except requests.exceptions.Timeout as e:
        print("❌ Letta timeout error:", e)
        return jsonify({"error": "Request timed out"}), 504
    except Exception as e:
        print("❌ Letta error:", e)
        return jsonify({"error": str(e)}), 500
    print("Gurt", response.messages[1].content)

    return Response(response=response.messages[1].content, mimetype="text/plain")

@app.route("/transcribe", methods=["POST"])
def transcribe():
    # Specify the path to the audio file
    audio_file = request.files["audio"]
    filename = audio_file.filename 
    # Open the audio file
    file_bytes = audio_file.read()
    # Return the translation text as a response
    translation = groq_client.audio.translations.create(
    file=(filename, file_bytes), # Required audio file
    model="whisper-large-v3", # Required model to use for translation
    prompt="Specify context or spelling",  # Optional
    response_format="json",  # Optional
    temperature=0.0  # Optional
    )

    if translation.text:
        transcription = translation.text
    else:
        transcription = "No transcription available."

    print(transcription)
    
    return jsonify({"transcription": transcription})
        
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8002)
