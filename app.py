from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import requests
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Ollama configuration
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"
ollama_connected = False
ollama_model = OLLAMA_MODEL

def check_ollama_connection():
    """Check if Ollama is running and get model information"""
    global ollama_connected, ollama_model
    try:
        # Test Ollama connection
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if response.status_code == 200:
            ollama_connected = True
            # Get available models
            models = response.json().get('models', [])
            # Find the first available model
            if models:
                ollama_model = models[0]['name']
            print(f"Ollama connected successfully. Using model: {ollama_model}")
        else:
            ollama_connected = False
            print("Ollama connection failed:", response.status_code)
    except Exception as e:
        ollama_connected = False
        print("Ollama connection error:", str(e))
    return ollama_connected, ollama_model

# Check Ollama connection on startup
check_ollama_connection()

@app.route('/')
def index():
    return render_template('chat.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send Ollama status to new client
    emit('ollama_status', {
        'connected': ollama_connected,
        'model': ollama_model
    })

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('message')
def handle_message(data):
    print(f'Received message: {data}')
    # Broadcast user message to all clients
    emit('message', data, broadcast=True)
    
    # If Ollama is connected, send message to model
    if ollama_connected:
        try:
            # Prepare request to Ollama API
            payload = {
                "model": ollama_model,
                "prompt": data['message'],
                "stream": False
            }
            
            # Send request to Ollama
            response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', '')
                # Send AI response back to all clients
                emit('message', {"message": ai_response, "is_ai": True}, broadcast=True)
                print(f'AI response: {ai_response}')
            else:
                print(f'Ollama API error: {response.status_code}')
                # Send error message to client
                emit('message', {"message": f"Ollama API error: {response.status_code}", "is_ai": True}, broadcast=True)
        except Exception as e:
            print(f'Error calling Ollama: {str(e)}')
            # Send error message to client
            emit('message', {"message": f"Error calling Ollama: {str(e)}", "is_ai": True}, broadcast=True)

@socketio.on('check_ollama')
def handle_check_ollama():
    """Handle client request to check Ollama status"""
    connected, model = check_ollama_connection()
    emit('ollama_status', {
        'connected': connected,
        'model': model
    })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
