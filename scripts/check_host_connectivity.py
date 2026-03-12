import socket
import os
import sys

def check_ollama():
    host = '127.0.0.1'
    port = 11434
    
    # Check if listening on 127.0.0.1
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        if s.connect_ex((host, port)) == 0:
            print(f"✅ Ollama is listening on {host}:{port}")
        else:
            print(f"❌ Ollama is NOT listening on {host}:{port}. Is it running?")
            return

    # Check if listening on ALL interfaces (required for Docker)
    all_interfaces = '0.0.0.0'
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        # Note: We can't connect to 0.0.0.0 to check, but we can check the host IP
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if s.connect_ex((host_ip, port)) == 0:
            print(f"✅ Ollama is accessible via Host IP ({host_ip}:{port})")
            print("   Docker should be able to reach it!")
        else:
            print(f"❌ Ollama is NOT accessible via Host IP ({host_ip}).")
            print("   It is likely restricted to 127.0.0.1 (Local Only).")
            print("\nFIX:")
            print("1. Set OLLAMA_HOST environment variable to '0.0.0.0'")
            print("   Command (PowerShell): [System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0', 'User')")
            print("2. RESTART OLLAMA (completely exit from tray and relaunch).")

if __name__ == "__main__":
    check_ollama()
