import json

def load_config():
    with open('config.json') as f:
        return json.load(f)

def load_keywords():
    with open('keywords.txt') as f:
        return [line.strip().lower() for line in f if line.strip()]

def load_liked_posts():
    try:
        with open('liked_posts.json') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_liked_posts(liked_set):
    with open('liked_posts.json', 'w') as f:
        json.dump(list(liked_set), f, indent=2)
