import os, dotenv
import datetime
from flask import Flask, render_template, request, Response, session, redirect, jsonify
from flask_cors import CORS  # To handle cross-origin requests
from groq import Groq
from letta_client import Letta, MessageCreate
from supabase import create_client, Client
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor()
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

def store_memory(user_id: str, memory_text: str, date: str = None):
    supabase.table("Memory").insert({
        "user_id": user_id,
        "message_text": memory_text,
        "timestamp": date if date else datetime.datetime.now().strftime(r"%Y-%m-%d")
    }).execute()

def get_memories_range(user_id: str, date_start: str, date_end: str):
    result = supabase.table("Memory")\
        .select("message_text")\
        .eq("user_id", user_id)\
        .gte("timestamp", date_start)\
        .lte("timestamp", date_end)\
        .execute()
    
    return [row["message_text"] for row in result.data]

def message_filter(msg):
    if msg.role == "user":
        yield msg.content[0].text.content

def recall_context(user_id: str, query: str, letta_client: Letta, supabase, agent_id: str, date_start, date_end, limit=3):

    context = []

    try:
        letta_context = letta_client.agents.context.retrieve(agent_id=agent_id)

        # Add core memory
        if letta_context.core_memory:
            context.append(f"[Memory]\n{letta_context.core_memory}")

        # Add summary memory
        if letta_context.summary_memory:
            context.append(f"[Summary]\n{letta_context.summary_memory}")

        # Add external/archival summary
        if letta_context.external_memory_summary:
            context.append(f"[Long-term Summary]\n{letta_context.external_memory_summary}")

        # Add recent messages
        for msg in letta_context.messages:
            role = msg.role.capitalize()
            context.append(f"{role}: {msg.content}")
    except Exception as e:
        print("Letta memory search error:", e)

    try:
        supabase_context = get_memories_range(
            user_id=user_id,
            date_start=date_start,
            date_end=date_end
        )
        context.extend(supabase_context)
    except Exception as e:
        print("Supabase memory fetch error:", e)
    return context


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
                model="anthropic/claude-3-5-haiku",
                embedding="openai/text-embedding-3-small",
                memory_blocks=[
                    {"label": "human", "value": f"User name: {user_id}"},
                    {"label": "persona", "value": "You are a memory journal keeper, helping users track their thoughts and experiences. Only respond with 'logged entry for {date}' when the user inputs a message."}
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
async def chat():
    data = request.get_json()
    user_input = data.get("message", "")
    datetime_now = datetime.datetime.now().strftime(r"%Y-%m-%d")
    user_input = f"{datetime_now} \n\n{user_input}"

    if not user_input:
        return {"error": "No message provided"}, 400

    agent_id = session.get("agent_id")

    # Wrap synchronous Letta call into coroutine
    try:
        store_memory(
            user_id=session.get("user_id"),
            memory_text=user_input,
            date=datetime_now
        )
        # add to letta memory 
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are helping people record their memories and thoughts."},
                {"role": "user", "content": f"Give me the important details from this, in a short message: {user_input}"}
            ],
            temperature=0.0
        )
        print(response.choices[0].message.content)
        n = datetime.datetime.now()
        Thread(target=letta_client.agents.messages.create,kwargs={
            "agent_id": agent_id,
            "messages": [MessageCreate(
                role="user",
                content=response.choices[0].message.content
        )]}).start()
        print(datetime.datetime.now() - n)
        
    except Exception as e:
        print("❌ Letta error:", e)
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "response": f"logged entry for {datetime_now}",
        "timestamp": datetime_now
    })


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
    
    return jsonify({"transcription": transcription})
        

@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.get_json()
    #   body = { date_start: dateStart.value, date_end: dateEnd.value };
    date_start = data.get("date_start")
    date_end = data.get("date_end")
    agent_id = session.get("agent_id")
    results = recall_context(
        user_id=session.get("user_id"),
        query="Summarize my memories",
        letta_client=letta_client,
        supabase=supabase,
        agent_id=agent_id,
        date_start=date_start,
        date_end=date_end
    )
    if not results:
        return jsonify({"error": "No memories found"}), 404
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a memory summarizer, helping users summarize their memories. Make your messages without formatting and to the point. Do not mention yoursef at all. You only write small conversational paragraphs."},
                {"role": "user", "content": f"Summarize the following memories briefly: {', '.join(results)}"}
            ],
            temperature=0.0
        )


        summary = response.choices[0].message.content

        return jsonify({"summary": summary})
    except Exception as e:
        
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8003)
