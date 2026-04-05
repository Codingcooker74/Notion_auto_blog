import os

def sanitize_env():
    env_path = '.env'
    if not os.path.exists(env_path):
        print("❌ .env file not found.")
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith('GEMINI_API_KEY='):
            key, val = line.strip().split('=', 1)
            # Remove quotes and whitespace
            val = val.strip().strip("'").strip('"').strip()
            new_lines.append(f"{key}={val}\n")
            print(f"✅ Sanitized GEMINI_API_KEY: {val[:4]}****")
        else:
            new_lines.append(line)

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✨ .env file sanitized.")

if __name__ == '__main__':
    sanitize_env()
