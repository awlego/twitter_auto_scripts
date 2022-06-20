import argparse
import json
import logging
import re
import time

import tweepy

logging.basicConfig(
    filename='feed_update.log',
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def get_OAuth_access(twitter_keys):
    """Generates the links you need to follow to setup OAuth
    """
    auth = tweepy.OAuthHandler(twitter_keys["api_key"], twitter_keys["api_secret_key"])

    try:
        redirect_url = auth.get_authorization_url()
    except tweepy.TweepyException:
        print('Error, failed to get request token')

    print(redirect_url)

    # Example w/o callback (desktop)
    verifier = input('Verifier:')

    try:
        auth.get_access_token(verifier)
    except tweepy.TweepyException:
        print('Error! Failed to get access token.')

    print(auth.access_token)
    print(auth.access_token_secret)


class ListUpdater():

    def __init__(self, twitter_keys_file_name, screen_name):
        with open(twitter_keys_file_name, encoding='utf-8', errors='ignore') as json_data:
            self.twitter_keys = json.load(json_data)

        auth = tweepy.OAuthHandler(self.twitter_keys["api_key"], self.twitter_keys["api_secret_key"])
        auth.set_access_token(self.twitter_keys['oauth_key'], self.twitter_keys['oauth_secret'])
        self.api = tweepy.API(auth, wait_on_rate_limit=True)

        self.screen_name = screen_name
        self.follows = None


    def create_list(self):
        # One time function I used to create the list.
        # name of the list
        name = "Alex's Feed (Auto)"
        description="A list of all the people I follow, automatically updated daily."

        # creating the list
        list = self.api.create_list(name=self.list_name, description=description)

        print("Name of the list : " + list.name)
        print("Number of members in the list : " + str(list.member_count))
        print("Mode of the list : " + list.mode)


    def get_follows(self, screen_name):
        follows_ids = []
        for user in tweepy.Cursor(self.api.get_friends, screen_name=screen_name).items():
            follows_ids.append(user.id)
        self.follows = follows_ids


    def get_current_list(self, list_id):
        """Fetches a list of twitter ids given a twitter list.

        Args:
            list_id (int): twitter ID of the list.

        Returns:
            [int]: List of twitter ids in the list.
        """
        current_list_ids = []
        for member in tweepy.Cursor(self.api.get_list_members, list_id=list_id).items():
            current_list_ids.append(member.id)
        logging.info(f"current_list_ids: {current_list_ids}")
        return current_list_ids


    def find_new_follows(self, current_list_ids, follows_ids):
        new_follows = [id for id in follows_ids if id not in current_list_ids]
        return new_follows


    def find_old_follows(self, current_list_ids, follows_ids):
        old_follows = [id for id in current_list_ids if id not in follows_ids]
        return old_follows


    def find_diff(self, follows_ids, current_list_ids):
        to_add = self.find_new_follows(current_list_ids, follows_ids)
        to_remove = self.find_old_follows(current_list_ids, follows_ids)
        return to_add, to_remove


    # I wonder if there is a better way of doing this... whatever this works.
    def split_list(self, input_list, chunk_length):
        num_slices = len(input_list) // chunk_length
        if len(input_list) % chunk_length != 0:
            num_slices += 1

        split_list = []
        for i in range(num_slices):
            new_array = input_list[i*chunk_length:(i+1)*chunk_length]
            split_list.append(new_array)
        return split_list


    def update_list(self, list_id, to_add, to_remove):
        chunked_ids_to_add = self.split_list(to_add, 100)
        chunked_ids_to_remove = self.split_list(to_remove, 100)

        for ids_list in chunked_ids_to_add:
            self.api.add_list_members(list_id=list_id, user_id=ids_list)
        for ids_list in chunked_ids_to_remove:
            self.api.remove_list_members(list_id=list_id, user_id=ids_list)


    def update_following(self, list_id=1400695918391746560):
        if not self.follows:
            self.get_follows(self.screen_name)
        current_list_ids = self.get_current_list(list_id)
        to_add, to_remove = self.find_diff(self.follows, current_list_ids)
        logging.info(f"New followers found, to add: {to_add}")
        logging.info(f"Old followers found, to remove: {to_remove}")
        self.update_list(list_id, to_add, to_remove)


    def get_followers(self):
        """
        Returns a list of twitter ids of users who follow the user.
        """
        followers = []
        for user in tweepy.Cursor(self.api.get_followers, screen_name=self.screen_name).items():
            followers.append(user.id)
        return followers
    

    def get_names_and_handles(self, twitter_ids):
        """returns the names and handles of the users given their twitter ids.
        """
        return_value = []
        users = self.api.lookup_users(user_id=twitter_ids)
        for user in users:
            return_value.append((user.name, user.screen_name))
        return return_value


    def update_mutuals(self, list_id=1437506909926354944):
        mutuals = []
        if not self.follows:
            self.get_follows(self.screen_name)
        followers = self.get_followers()
        for follow in self.follows:
            if follow in followers:
                mutuals.append(follow) 

        current_list_ids = self.get_current_list(list_id)
        to_add, to_remove = self.find_diff(mutuals, current_list_ids)
        logging.info(f"New mutuals found, to add: {to_add}")
        logging.info(f"Old mutuals found, to remove: {to_remove}")

        # names, handles = self.get_names_and_handles(to_add)
        # for name, handle in names, handles:
        #     logging.info(f"New mutuals found: {name} @{handle}")

        # names, handles = self.get_names_and_handles(to_remove)
        # for name, handle in names, handles:
        #     logging.info(f"Old mutuals removed: {name} @{handle}")

        self.update_list(list_id, to_add, to_remove)


    def update(self):
        self.update_following()
        self.update_mutuals()


def main():
    logging.info("Starting update")

    parser = argparse.ArgumentParser(
        description='Auto update a twitter list')
    parser.add_argument(
        'keys',
        default="/Users/akuna/preps/twitter_auto_scripts/twitter_keys.json",
        help='path to the twitter keys json file')
    args = parser.parse_args()

    screen_name = "awlego"
    # lists_to_update = [("Awlego's Feed (Auto)", 1400695918391746560), ("Awlego's Mutuals", 1437506909926354944)]

    list_updater = ListUpdater(args.keys, screen_name)
    list_updater.update()

    logging.info("Finished update")


if __name__ == "__main__":
    main()
    