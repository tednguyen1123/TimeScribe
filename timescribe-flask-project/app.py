import os, dotenv
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
            model="meta-llama/llama-4-scout-17b-16e-instruct",
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    app.run(debug=True, host="0.0.0.0", port=port)
