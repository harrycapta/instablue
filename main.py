from atproto import Client, models
import time
from utils import load_config, load_keywords, load_liked_posts, save_liked_posts

# --- Setup ---
config = load_config()
KEYWORDS = load_keywords()
LIKED_POSTS = load_liked_posts()
ACTION_INTERVAL = max(1, 3600 / config.get('actions_per_hour', 30))

client = Client(base_url=config.get('base_url'))
client.login(config['username'], config['password'])
print("✅ Login effettuato")

# --- Ottieni following (amici e amici-di-amici) ---
def get_all_following_handles(handle):
    """Return the set of DIDs that the provided handle follows."""
    following = set()
    cursor = None
    while True:
        res = client.app.bsky.graph.get_follows({'actor': handle, 'cursor': cursor})
        for user in res.follows:
            following.add(user.did)
        if not res.cursor:
            break
        cursor = res.cursor
    return following

my_following = get_all_following_handles(config['username'])
print(f"👥 Amici diretti trovati: {len(my_following)}")

# Estende con amici-di-amici (facoltativo)
friends_of_friends = set()
for friend_did in list(my_following)[:10]:  # Limite per non fare troppe chiamate
    friends_of_friends |= get_all_following_handles(friend_did)

all_allowed_users = my_following | friends_of_friends
print(f"👨‍👩‍👧‍👦 Rete estesa utenti: {len(all_allowed_users)}")

# --- Like ai post ---
def like_matching_post():
    """Mette like al primo post che soddisfa i criteri."""
    feed = client.app.bsky.feed.get_timeline(limit=config['max_feed_items'])

    for item in feed.feed:
        post = item.post
        uri = post.uri
        cid = post.cid
        text = post.record.text.lower()
        author_did = post.author.did

        if uri in LIKED_POSTS:
            continue  # già likato

        if any(kw in text for kw in KEYWORDS) or author_did in all_allowed_users:
            try:
                client.like(uri, cid)
                print(f"❤️ Like a post di {post.author.handle}: {text[:40]}")
                LIKED_POSTS.add(uri)
                return True
            except Exception as e:
                print(f"⚠️ Errore like: {e}")
                return False
    return False

# --- Loop principale ---
try:
    while True:
        like_matching_post()
        save_liked_posts(LIKED_POSTS)
        time.sleep(ACTION_INTERVAL)
except KeyboardInterrupt:
    print("🛑 Uscita manuale, salvando storico like...")
    save_liked_posts(LIKED_POSTS)
