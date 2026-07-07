from core.engines.profile_manager import ProfileManager
import os

def migrate():
    print("Migrating profile data...")
    pm = ProfileManager()
    
    # Read legacy txt
    if os.path.exists("user_profile.txt"):
        with open("user_profile.txt", "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                    print(f"Found Name: {name}")
                    pm.set_name(name)
                    print("Updated ProfileManager.")
                    break
    else:
        print("user_profile.txt not found.")

if __name__ == "__main__":
    migrate()