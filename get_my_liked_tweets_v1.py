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
        
        # Setup authentication for v1.1 API
        auth = tweepy.OAuthHandler(self.twitter_keys["api_key"], self.twitter_keys["api_secret_key"])
        auth.set_access_token(self.twitter_keys['oauth_key'], self.twitter_keys['oauth_secret'])
        self.api = tweepy.API(auth, wait_on_rate_limit=True)
        
        # Test authentication
        try:
            self.api.verify_credentials()
            logging.info("Authentication successful")
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            raise
        
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
    
    def save_checkpoint(self, max_id=None, tweets_fetched=0):
        """Save checkpoint data."""
        checkpoint = {
            "max_id": max_id,
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
    
    def process_tweet(self, tweet, download_media=True):
        """Process a single tweet and extract relevant information."""
        tweet_data = {
            "id": str(tweet.id),
            "created_at": tweet.created_at.isoformat(),
            "text": tweet.full_text if hasattr(tweet, 'full_text') else tweet.text,
            "author": {
                "id": str(tweet.author.id),
                "name": tweet.author.name,
                "screen_name": tweet.author.screen_name,
                "profile_image_url": tweet.author.profile_image_url_https
            },
            "favorite_count": tweet.favorite_count,
            "retweet_count": tweet.retweet_count,
            "tweet_url": f"https://twitter.com/{tweet.author.screen_name}/status/{tweet.id}",
            "media": []
        }
        
        # Extract media if present
        if hasattr(tweet, 'entities') and 'media' in tweet.entities:
            for i, media in enumerate(tweet.entities['media']):
                media_info = {
                    "type": media['type'],
                    "url": media['media_url_https'],
                    "local_path": None
                }
                
                # Download media if requested
                if download_media:
                    local_path = self.download_media(
                        media['media_url_https'], 
                        tweet.id, 
                        i
                    )
                    if local_path:
                        media_info["local_path"] = local_path
                
                tweet_data["media"].append(media_info)
        
        # Handle extended entities for multiple images
        if hasattr(tweet, 'extended_entities') and 'media' in tweet.extended_entities:
            # Clear and re-process with extended entities
            tweet_data["media"] = []
            for i, media in enumerate(tweet.extended_entities['media']):
                media_info = {
                    "type": media['type'],
                    "url": media['media_url_https'],
                    "local_path": None
                }
                
                # Download media if requested
                if download_media:
                    local_path = self.download_media(
                        media['media_url_https'], 
                        tweet.id, 
                        i
                    )
                    if local_path:
                        media_info["local_path"] = local_path
                
                tweet_data["media"].append(media_info)
        
        return tweet_data
    
    def test_api_access(self):
        """Test different API endpoints to see what's available."""
        logging.info("Testing API access...")
        
        # Test getting user timeline
        try:
            tweets = self.api.user_timeline(count=1, tweet_mode='extended')
            logging.info(f"✓ Can access user timeline (found {len(tweets)} tweets)")
        except Exception as e:
            logging.error(f"✗ Cannot access user timeline: {e}")
        
        # Test getting favorites/likes
        try:
            tweets = self.api.get_favorites(count=1, tweet_mode='extended')
            logging.info(f"✓ Can access liked tweets (found {len(tweets)} tweets)")
            return True
        except Exception as e:
            logging.error(f"✗ Cannot access liked tweets: {e}")
            return False
    
    def fetch_liked_tweets(self, count=200, download_media=True, save_interval=20):
        """Fetch liked tweets with incremental saving."""
        logging.info(f"Starting to fetch liked tweets (target: {count})")
        
        # Test API access first
        if not self.test_api_access():
            logging.error("API access test failed. The favorites/likes endpoint may require elevated access.")
            logging.info("Alternative options:")
            logging.info("1. Request elevated access at https://developer.twitter.com")
            logging.info("2. Use Twitter's data export feature at https://twitter.com/settings/download_your_data")
            logging.info("3. Use the web interface and manually save liked tweets")
            return []
        
        # Resume from checkpoint if available
        max_id = self.checkpoint.get('max_id')
        tweets_fetched = len(self.tweets_data)
        existing_ids = {tweet['id'] for tweet in self.tweets_data}
        
        try:
            while tweets_fetched < count:
                # Calculate how many tweets to fetch in this batch
                remaining = count - tweets_fetched
                batch_size = min(200, remaining)  # Twitter API max is 200 per request
                
                logging.info(f"Fetching batch (up to {batch_size} tweets)...")
                
                # Fetch tweets
                kwargs = {
                    'count': batch_size,
                    'tweet_mode': 'extended'  # Get full text
                }
                if max_id:
                    kwargs['max_id'] = max_id
                
                tweets = self.api.get_favorites(**kwargs)
                
                if not tweets:
                    logging.info("No more tweets to fetch")
                    break
                
                # Process each tweet
                new_tweets_in_batch = 0
                for tweet in tweets:
                    # Skip if we already have this tweet
                    if str(tweet.id) in existing_ids:
                        continue
                    
                    tweet_data = self.process_tweet(tweet, download_media)
                    self.tweets_data.append(tweet_data)
                    existing_ids.add(str(tweet.id))
                    new_tweets_in_batch += 1
                    tweets_fetched += 1
                    
                    # Save incrementally
                    if tweets_fetched % save_interval == 0:
                        self.save_tweets_data()
                        self.save_checkpoint(max_id=tweet.id - 1, tweets_fetched=tweets_fetched)
                        logging.info(f"Progress: {tweets_fetched}/{count} tweets fetched")
                    
                    if tweets_fetched >= count:
                        break
                
                # Update max_id for next batch
                if tweets:
                    max_id = tweets[-1].id - 1
                
                logging.info(f"Processed {new_tweets_in_batch} new tweets in this batch")
                
                # If we got fewer tweets than requested, we've reached the end
                if len(tweets) < batch_size:
                    logging.info("Reached the end of liked tweets")
                    break
                
        except Exception as e:
            logging.error(f"Error fetching tweets: {e}")
            # Save progress before exiting
            self.save_tweets_data()
            self.save_checkpoint(max_id=max_id, tweets_fetched=tweets_fetched)
            raise
        
        # Final save
        self.save_tweets_data()
        self.save_checkpoint(max_id=max_id, tweets_fetched=tweets_fetched)
        
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
        description='Fetch your liked tweets from Twitter using v1.1 API'
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
    if tweets:
        fetcher.generate_summary()


if __name__ == "__main__":
    main()