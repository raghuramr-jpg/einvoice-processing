import os
from langchain_ollama import ChatOllama

def check_ollama():
    try:
        llm = ChatOllama(model="qwen2.5", base_url="http://localhost:11434")
        response = llm.invoke("Hi")
        print(f"Ollama Response: {response.content}")
        return True
    except Exception as e:
        print(f"Ollama Error: {e}")
        return False

if __name__ == "__main__":
    check_ollama()
