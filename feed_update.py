import tweepy
import json

twitter_keys_file_name = "/Users/akuna/preps/twitter_auto_scripts/twitter_keys.json"
with open(twitter_keys_file_name, encoding='utf-8', errors='ignore') as json_data:
    twitter_keys = json.load(json_data)

auth = tweepy.OAuthHandler(twitter_keys["api_key"], twitter_keys["api_secret_key"])

def get_OAuth_access():
    try:
        redirect_url = auth.get_authorization_url()
    except tweepy.TweepError:
        print('Error, failed to get request token')

    print(redirect_url)

    # Example w/o callback (desktop)
    verifier = input('Verifier:')

    try:
        auth.get_access_token(verifier)
    except tweepy.TweepError:
        print('Error! Failed to get access token.')

    print(auth.access_token)
    print(auth.access_token_secret)

# get_OAuth_access()
auth.set_access_token(twitter_keys['oauth_key'], twitter_keys['oauth_secret'])

# calling the api 
api = tweepy.API(auth, wait_on_rate_limit=True)

screen_name = "awlego"
list_name = "Alex's Feed (Auto)"
list_id = 1400695918391746560

def create_list():
    # name of the list
    name = "Alex's Feed (Auto)"
    description="A list of all the people I follow, automatically updated daily."

    # creating the list
    list = api.create_list(name=list_name, description=description)

    print("Name of the list : " + list.name)
    print("Number of members in the list : " + str(list.member_count))
    print("Mode of the list : " + list.mode)


def get_follows(screen_name):
    follows_ids = []
    for user in tweepy.Cursor(api.friends, screen_name=screen_name).items():
        follows_ids.append(user.id)
    print(follows_ids)
    return follows_ids


def get_current_list(list_id):
    current_list_ids = []
    for member in tweepy.Cursor(api.list_members, list_id=list_id).items():
        current_list_ids.append(member.id)
    print(f"current_list_ids: {current_list_ids}")
    return current_list_ids


def find_new_follows(current_list_ids, follows_ids):
    new_follows = [id for id in follows_ids if id not in current_list_ids]
    print(new_follows)
    return new_follows


def find_old_follows(current_list_ids, follows_ids):
    old_follows = [id for id in current_list_ids if id not in follows_ids]
    print(old_follows)
    return old_follows


def find_diff(follows_ids, current_list_ids):
    to_add = find_new_follows(current_list_ids, follows_ids)
    to_remove = find_old_follows(current_list_ids, follows_ids)
    print(to_add)
    print(to_remove)
    return to_add, to_remove


# I wonder if there is a better way of doing this... whatever this works.
def split_list(input_list, chunk_length):
    num_slices = len(input_list) // chunk_length
    if len(input_list) % chunk_length != 0:
        num_slices += 1

    split_list = []
    for i in range(num_slices):
        new_array = input_list[i*chunk_length:(i+1)*chunk_length]
        split_list.append(new_array)
    return split_list


def update_list(list_id, to_add, to_remove):
    chunked_ids_to_add = split_list(to_add, 100)
    chunked_ids_to_remove = split_list(to_remove, 100)

    for ids_list in chunked_ids_to_add:
        status = api.add_list_members(list_id=list_id, screen_name=ids_list)
    for ids_list in chunked_ids_to_remove:
        status = api.remove_list_member(list_id=list_id, screen_name=ids_list)

follows_ids = get_follows(screen_name)
current_list_ids = get_current_list(list_id)
to_add, to_remove = find_diff(follows_ids, current_list_ids)
update_list(list_id, to_add, to_remove)