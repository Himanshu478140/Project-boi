import requests
import sys

SERVER_URL = "http://localhost:8000/ask"

def main():
    print("--- Browser Guide CLI ---")
    print("Ensure server is running (python server.py) and Extension is connected.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            query = input("You: ")
            if query.lower() in ["quit", "exit"]:
                break
            
            print("Guide is thinking...")
            response = requests.post(SERVER_URL, json={"question": query})
            
            if response.status_code == 200:
                answer = response.json().get("response", "No response content.")
                print(f"Guide: {answer}\n")
            else:
                print(f"Error: Server returned {response.status_code}\n")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Connection Error: {e}")
            print("Is the server running?")

if __name__ == "__main__":
    main()
