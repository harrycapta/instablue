from atproto import Client, models
import time
from utils import (
    load_config,
    load_keywords,
    load_liked_posts,
    save_liked_posts,
    load_followed_users,
    save_followed_users,
)

# --- Setup ---
config = load_config()
KEYWORDS = load_keywords()
LIKED_POSTS = load_liked_posts()
FOLLOWED_USERS = load_followed_users()
ACTION_INTERVAL = max(1, 3600 / config.get('actions_per_hour', 30))
FOLLOW_EXPIRE = 96 * 3600  # 96 hours

client = Client(base_url=config.get('base_url'))
client.login(config['username'], config['password'])
MY_DID = client.me.did
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

def get_all_follower_handles(handle):
    """Return the set of DIDs that follow the provided handle."""
    followers = set()
    cursor = None
    while True:
        res = client.app.bsky.graph.get_followers({'actor': handle, 'cursor': cursor})
        for user in res.followers:
            followers.add(user.did)
        if not res.cursor:
            break
        cursor = res.cursor
    return followers

my_following = get_all_following_handles(config['username'])
print(f"👥 Amici diretti trovati: {len(my_following)}")

my_followers = get_all_follower_handles(config['username'])
print(f"🙋 Follower trovati: {len(my_followers)}")

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
                if author_did not in my_following:
                    try:
                        follow_res = client.follow(author_did)
                        print(f"➕ Follow a {post.author.handle}")
                        FOLLOWED_USERS[author_did] = {
                            'timestamp': time.time(),
                            'follow_uri': follow_res.uri,
                            'handle': post.author.handle,
                        }
                        my_following.add(author_did)
                    except Exception as e:
                        print(f"⚠️ Errore follow: {e}")
                return True
            except Exception as e:
                print(f"⚠️ Errore like: {e}")
                return False
    return False

def unfollow_non_reciprocated():
    """Unfollow users who didn't follow back within FOLLOW_EXPIRE."""
    global my_followers
    current_time = time.time()
    my_followers = get_all_follower_handles(config['username'])
    to_remove = []
    for did, data in list(FOLLOWED_USERS.items()):
        if current_time - data['timestamp'] >= FOLLOW_EXPIRE and did not in my_followers:
            try:
                client.unfollow(data['follow_uri'])
                print(f"❌ Unfollow da {data['handle']}")
                my_following.discard(did)
                to_remove.append(did)
            except Exception as e:
                print(f"⚠️ Errore unfollow: {e}")
    for did in to_remove:
        FOLLOWED_USERS.pop(did, None)

# --- Loop principale ---
try:
    while True:
        like_matching_post()
        unfollow_non_reciprocated()
        save_liked_posts(LIKED_POSTS)
        save_followed_users(FOLLOWED_USERS)
        time.sleep(ACTION_INTERVAL)
except KeyboardInterrupt:
    print("🛑 Uscita manuale, salvando storico like...")
    save_liked_posts(LIKED_POSTS)
    save_followed_users(FOLLOWED_USERS)
