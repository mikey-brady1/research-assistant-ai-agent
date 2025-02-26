import os
import json
import re
import requests
from flask import Flask, request, jsonify
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
from llmproxy import generate

app = Flask(__name__)

# Retrieve API Key & Endpoint from environment variables
apiKey = os.environ.get("apiKey", "").strip()
endPoint = os.environ.get("endPoint", "").strip().strip('"')  # Strip accidental quotes

# Debugging Logs
print(f"Loaded API Key: {apiKey}")  
print(f"Loaded Endpoint: {endPoint}")  

if not apiKey or not endPoint:
    raise RuntimeError("API_KEY or ENDPOINT is missing! Ensure they are set correctly in Koyeb.")

# Rocket.Chat Bot Credentials
RC_TOKEN = "LSyyCDMk0-vey1SFnWGL976a5dwdcTVQugpB_pmojlO"
RC_USER_ID = "JTzYdypXa5E6Qh4uE"

# User session storage for chat history
user_chat_history = {}

@app.route('/query', methods=['POST'])
def main():
    """
    Handles incoming messages from Rocket.Chat.
    Routes queries through `research_assistant_agent`.
    """
    data = request.get_json()
    user = data.get("user_name", "Unknown")  # Identify user session
    message = data.get("text", "").strip()

    print(f"Incoming request from {user}: {message}")

    if data.get("bot") or not message:
        return jsonify({"status": "ignored"})

    # Route through the Research Assistant Agent
    response_text = research_assistant_agent(user, message)

    # Send response back to Rocket.Chat
    send_rocketchat_message(user, response_text)

    return jsonify({"status": "message_sent"})

### **Rocket.Chat Integration**
def send_rocketchat_message(user, message):
    """
    Sends a message to a user in Rocket.Chat.
    Uses bot authentication.
    """
    url = "https://chat.genaiconnect.net/api/v1/chat.postMessage"

    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": RC_TOKEN,
        "X-User-Id": RC_USER_ID
    }

    payload = {
        "channel": f"@{user}",
        "text": message
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        if response.status_code == 200 and response_data.get("success"):
            print(f"[DEBUG] Message sent to {user}: {message}")
        else:
            print(f"[ERROR] Failed to send message to {user}: {response_data}")
    except Exception as e:
        print(f"[ERROR] Exception in sending message to Rocket.Chat: {e}")

### **Research Assistant Agent**
def research_assistant_agent(user_id, query):
    """
    The primary agent that understands user intent and routes the query accordingly.
    It ensures the chatbot behaves like a helpful research assistant.
    """
    print(f"[DEBUG] Research Assistant processing query: {query} for user {user_id}")

    # Retrieve past interactions
    chat_history = get_chat_history(user_id)

    # If it's the first message from the user, greet and guide them
    if not chat_history:
        store_chat_history(user_id, query, "New user session started.")
        user_chat_history[user_id] = {"stage": "initial"}  # Track user progress
        return (
            "👋 Hello! I'm your Research Assistant. I can help with:\n"
            "📖 Detailed explanations of academic topics\n"
            "📝 Summaries of complex texts\n"
            "🔎 Finding credible sources online\n"
            "Just tell me what you need, and I'll assist!"
        )

    # Detect user intent
    intent = detect_intent(query)

    if intent == "explanation":
        return research_agent(query, user_id)
    elif intent == "summary":
        return summarization_agent(query)
    elif intent == "websearch":
        return websearch(query)
    
    # If intent is unclear, ask for clarification
    return (
        "🤖 I couldn't determine what you're looking for. Are you asking for:\n"
        "- A detailed explanation of a topic?\n"
        "- A summary of a document or text?\n"
        "- Credible sources and research articles?\n"
        "Try rephrasing your request or specifying what you need!"
    )


### **Research Agent**
def research_agent(query, user_id):
    """
    Handles research queries by:
    1. Using LLM for structured research-based responses.
    2. Performing a web search for additional sources.
    3. Storing conversation history for better user experience.
    """
    print(f"[DEBUG] Research Agent processing: {query}")

    # Generate response from LLM
    response = generate(
        model="4o-mini",
        system="You are an AI research assistant providing structured, fact-based responses.",
        query=query,
        temperature=0.7,
        lastk=0,
        session_id=f"research-agent-{user_id}",  
        rag_usage=False  
    )

    # Debugging output
    print(f"[DEBUG] Full API Response: {response}")

    # Perform web search
    web_results = websearch(query)

    # Format final response
    llm_response = response.get("response", "No research data found. Try rewording your question.")
    
    final_response = f"**📖 Research Summary:**\n{llm_response}\n\n**🔎 Web Search Results:**\n{web_results}"

    # Store chat history
    store_chat_history(user_id, query, final_response)

    return final_response

### **Intent Detection**
def detect_intent(query):
    """
    Determines user intent based on input.
    - Returns 'explanation', 'summary', or 'websearch'.
    """
    query_lower = query.lower()

    # Keywords for different intents
    explanation_keywords = ["explain", "describe", "how does", "what is", "overview", "deep dive"]
    summary_keywords = ["summarize", "condense", "tl;dr", "short version"]
    websearch_keywords = ["find sources", "look up", "research articles", "search online", "credible sources"]

    # Intent classification
    if any(keyword in query_lower for keyword in explanation_keywords):
        return "explanation"
    elif any(keyword in query_lower for keyword in summary_keywords):
        return "summary"
    elif any(keyword in query_lower for keyword in websearch_keywords):
        return "websearch"
    
    return "unknown"  # If unclear, bot will prompt for clarification

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
