import requests
import json

def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            print("Available Ollama models:")
            for m in models:
                print(f"- {m['name']}")
        else:
            print(f"Failed to connect to Ollama: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")

if __name__ == "__main__":
    check_ollama()
