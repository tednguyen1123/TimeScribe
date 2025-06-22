import os, dotenv
from letta_client import Letta
from supabase import create_client, Client

dotenv.load_dotenv()
client = Letta(token=os.getenv("LETTA_API_KEY"))
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)
name = "Sid"  # or from signup/login system

# Check if this user already has an agent
existing = supabase.table("agent_ids").select("*").eq("user_id", name).execute()
if existing.data:
    agent_id = existing.data[0]['agent_id']
    print(f"Agent already exists for {name}: {agent_id}")
else:
    agent = client.agents.create(
        model="openai/gpt-4",
        embedding="openai/text-embedding-3-small",
        memory_blocks=[
            {"label": "human", "value": f"User name: {name}"},
            {"label": "persona", "value": "You are a memory journal keeper, helping users track their thoughts and experiences."}
        ]
    )
    agent_id = agent.id
    supabase.table("agent_ids").insert({
        "user_id": name,
        "agent_id": agent_id
    }).execute()
    print(f"Created new agent for {name}: {agent_id}")