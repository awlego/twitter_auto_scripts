import argparse
import json
import logging
import os
import time
from datetime import datetime
import requests

import tweepy

# Setup logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

class LikedTweetsFetcher:
    def __init__(self, twitter_keys_file_name, output_dir="liked_tweets"):
        """Initialize the fetcher with Twitter API credentials."""
        with open(twitter_keys_file_name, encoding='utf-8', errors='ignore') as json_data:
            self.twitter_keys = json.load(json_data)
        
        # Setup authentication for API v2
        # Check if we have a bearer token
        if "bearer_token" in self.twitter_keys:
            self.client = tweepy.Client(
                bearer_token=self.twitter_keys["bearer_token"],
                consumer_key=self.twitter_keys["api_key"],
                consumer_secret=self.twitter_keys["api_secret_key"],
                access_token=self.twitter_keys['oauth_key'],
                access_token_secret=self.twitter_keys['oauth_secret'],
                wait_on_rate_limit=True
            )
        else:
            # Use OAuth 1.0a User Context
            self.client = tweepy.Client(
                consumer_key=self.twitter_keys["api_key"],
                consumer_secret=self.twitter_keys["api_secret_key"],
                access_token=self.twitter_keys['oauth_key'],
                access_token_secret=self.twitter_keys['oauth_secret'],
                wait_on_rate_limit=True
            )
        
        # Also keep v1.1 API for media downloads
        auth = tweepy.OAuthHandler(self.twitter_keys["api_key"], self.twitter_keys["api_secret_key"])
        auth.set_access_token(self.twitter_keys['oauth_key'], self.twitter_keys['oauth_secret'])
        self.api = tweepy.API(auth, wait_on_rate_limit=True)
        
        # Setup output directories
        self.output_dir = output_dir
        self.media_dir = os.path.join(output_dir, "media")
        self.checkpoint_file = os.path.join(output_dir, "checkpoint.json")
        self.tweets_file = os.path.join(output_dir, "liked_tweets.json")
        
        # Create directories if they don't exist
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.media_dir, exist_ok=True)
        
        # Load existing data and checkpoint
        self.tweets_data = self.load_existing_tweets()
        self.checkpoint = self.load_checkpoint()
        
    def load_existing_tweets(self):
        """Load existing tweets data if available."""
        if os.path.exists(self.tweets_file):
            try:
                with open(self.tweets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logging.info(f"Loaded {len(data)} existing tweets")
                    return data
            except Exception as e:
                logging.error(f"Error loading existing tweets: {e}")
                return []
        return []
    
    def load_checkpoint(self):
        """Load checkpoint data to resume from last position."""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                    logging.info(f"Loaded checkpoint: {checkpoint}")
                    return checkpoint
            except Exception as e:
                logging.error(f"Error loading checkpoint: {e}")
                return {}
        return {}
    
    def save_checkpoint(self, pagination_token=None, tweets_fetched=0):
        """Save checkpoint data."""
        checkpoint = {
            "pagination_token": pagination_token,
            "tweets_fetched": tweets_fetched,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        logging.info(f"Saved checkpoint: {checkpoint}")
    
    def save_tweets_data(self):
        """Save all tweets data to JSON file."""
        with open(self.tweets_file, 'w', encoding='utf-8') as f:
            json.dump(self.tweets_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(self.tweets_data)} tweets to {self.tweets_file}")
    
    def download_media(self, media_url, tweet_id, media_index=0):
        """Download media file and return local path."""
        try:
            # Get file extension from URL
            ext = media_url.split('.')[-1].split('?')[0]
            if ext not in ['jpg', 'jpeg', 'png', 'gif', 'mp4']:
                ext = 'jpg'  # Default extension
            
            # Create filename
            filename = f"{tweet_id}_{media_index}.{ext}"
            filepath = os.path.join(self.media_dir, filename)
            
            # Skip if already downloaded
            if os.path.exists(filepath):
                logging.info(f"Media already exists: {filename}")
                return filepath
            
            # Download the media
            response = requests.get(media_url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logging.info(f"Downloaded media: {filename}")
            return filepath
            
        except Exception as e:
            logging.error(f"Error downloading media from {media_url}: {e}")
            return None
    
    def process_tweet(self, tweet, author, download_media=True):
        """Process a single tweet and extract relevant information."""
        tweet_data = {
            "id": str(tweet.id),
            "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
            "text": tweet.text,
            "author": {
                "id": str(author.id),
                "name": author.name,
                "username": author.username,
                "profile_image_url": author.profile_image_url if hasattr(author, 'profile_image_url') else None
            },
            "like_count": tweet.public_metrics.get('like_count', 0) if tweet.public_metrics else 0,
            "retweet_count": tweet.public_metrics.get('retweet_count', 0) if tweet.public_metrics else 0,
            "tweet_url": f"https://twitter.com/{author.username}/status/{tweet.id}",
            "media": []
        }
        
        # Extract media if present
        if hasattr(tweet, 'attachments') and tweet.attachments and 'media_keys' in tweet.attachments:
            # Media will be processed from includes.media
            pass
        
        return tweet_data
    
    def fetch_liked_tweets(self, count=200, download_media=True, save_interval=20):
        """Fetch liked tweets with incremental saving."""
        logging.info(f"Starting to fetch liked tweets (target: {count})")
        
        # Get authenticated user ID
        try:
            me = self.client.get_me()
            if not me.data:
                logging.error("Could not get authenticated user")
                return []
            user_id = me.data.id
            logging.info(f"Fetching likes for user ID: {user_id}")
        except Exception as e:
            logging.error(f"Error getting user ID: {e}")
            return []
        
        # Resume from checkpoint if available
        pagination_token = self.checkpoint.get('pagination_token')
        tweets_fetched = len(self.tweets_data)
        existing_ids = {tweet['id'] for tweet in self.tweets_data}
        
        try:
            while tweets_fetched < count:
                # Calculate how many tweets to fetch in this batch
                remaining = count - tweets_fetched
                batch_size = min(100, remaining)  # Twitter API v2 max is 100 per request
                
                logging.info(f"Fetching batch (up to {batch_size} tweets)...")
                
                # Fetch liked tweets using v2 API
                response = self.client.get_liked_tweets(
                    id=user_id,
                    max_results=batch_size,
                    pagination_token=pagination_token,
                    tweet_fields=['created_at', 'public_metrics', 'attachments'],
                    expansions=['author_id', 'attachments.media_keys'],
                    user_fields=['name', 'username', 'profile_image_url'],
                    media_fields=['url', 'preview_image_url', 'type']
                )
                
                if not response.data:
                    logging.info("No more tweets to fetch")
                    break
                
                # Create lookup dictionaries for users and media
                users_dict = {}
                if response.includes and 'users' in response.includes:
                    users_dict = {user.id: user for user in response.includes['users']}
                
                media_dict = {}
                if response.includes and 'media' in response.includes:
                    media_dict = {media.media_key: media for media in response.includes['media']}
                
                # Process each tweet
                new_tweets_in_batch = 0
                for tweet in response.data:
                    # Skip if we already have this tweet
                    if str(tweet.id) in existing_ids:
                        continue
                    
                    # Get author info
                    author = users_dict.get(tweet.author_id)
                    if not author:
                        logging.warning(f"No author found for tweet {tweet.id}")
                        continue
                    
                    tweet_data = self.process_tweet(tweet, author, download_media)
                    
                    # Process media if present
                    if hasattr(tweet, 'attachments') and tweet.attachments and 'media_keys' in tweet.attachments:
                        for i, media_key in enumerate(tweet.attachments['media_keys']):
                            media = media_dict.get(media_key)
                            if media:
                                media_url = None
                                if hasattr(media, 'url'):
                                    media_url = media.url
                                elif hasattr(media, 'preview_image_url'):
                                    media_url = media.preview_image_url
                                
                                if media_url:
                                    media_info = {
                                        "type": media.type,
                                        "url": media_url,
                                        "local_path": None
                                    }
                                    
                                    # Download media if requested
                                    if download_media and media_url:
                                        local_path = self.download_media(
                                            media_url, 
                                            tweet.id, 
                                            i
                                        )
                                        if local_path:
                                            media_info["local_path"] = local_path
                                    
                                    tweet_data["media"].append(media_info)
                    
                    self.tweets_data.append(tweet_data)
                    existing_ids.add(str(tweet.id))
                    new_tweets_in_batch += 1
                    tweets_fetched += 1
                    
                    # Save incrementally
                    if tweets_fetched % save_interval == 0:
                        self.save_tweets_data()
                        self.save_checkpoint(pagination_token=pagination_token, tweets_fetched=tweets_fetched)
                        logging.info(f"Progress: {tweets_fetched}/{count} tweets fetched")
                    
                    if tweets_fetched >= count:
                        break
                
                # Update pagination token for next batch
                if hasattr(response.meta, 'next_token'):
                    pagination_token = response.meta.next_token
                else:
                    logging.info("No more pages available")
                    break
                
                logging.info(f"Processed {new_tweets_in_batch} new tweets in this batch")
                
        except Exception as e:
            logging.error(f"Error fetching tweets: {e}")
            # Save progress before exiting
            self.save_tweets_data()
            self.save_checkpoint(pagination_token=pagination_token, tweets_fetched=tweets_fetched)
            raise
        
        # Final save
        self.save_tweets_data()
        self.save_checkpoint(pagination_token=pagination_token, tweets_fetched=tweets_fetched)
        
        logging.info(f"Finished! Total tweets fetched: {tweets_fetched}")
        return self.tweets_data
    
    def generate_summary(self):
        """Generate a summary of the fetched tweets."""
        total_tweets = len(self.tweets_data)
        tweets_with_media = sum(1 for tweet in self.tweets_data if tweet['media'])
        total_media = sum(len(tweet['media']) for tweet in self.tweets_data)
        
        summary = f"""
Liked Tweets Summary:
--------------------
Total tweets fetched: {total_tweets}
Tweets with media: {tweets_with_media}
Total media files: {total_media}
Output directory: {self.output_dir}
Tweets data file: {self.tweets_file}
Media directory: {self.media_dir}
"""
        
        # Save summary
        summary_file = os.path.join(self.output_dir, "summary.txt")
        with open(summary_file, 'w') as f:
            f.write(summary)
        
        print(summary)
        return summary


def main():
    parser = argparse.ArgumentParser(
        description='Fetch your liked tweets from Twitter'
    )
    parser.add_argument(
        'keys',
        help='Path to the twitter keys JSON file'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=200,
        help='Number of tweets to fetch (default: 200)'
    )
    parser.add_argument(
        '--output',
        default='liked_tweets',
        help='Output directory (default: liked_tweets)'
    )
    parser.add_argument(
        '--no-media',
        action='store_true',
        help='Skip downloading media files'
    )
    parser.add_argument(
        '--save-interval',
        type=int,
        default=20,
        help='Save progress every N tweets (default: 20)'
    )
    
    args = parser.parse_args()
    
    # Create fetcher instance
    fetcher = LikedTweetsFetcher(args.keys, args.output)
    
    # Fetch tweets
    tweets = fetcher.fetch_liked_tweets(
        count=args.count,
        download_media=not args.no_media,
        save_interval=args.save_interval
    )
    
    # Generate summary
    fetcher.generate_summary()


if __name__ == "__main__":
    main()