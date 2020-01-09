import re
import json
import requests

import tweepy
from bs4 import BeautifulSoup

with open('tokens.json') as f:
    tokens = json.load(f)

def get_api():
    ''' Establishes auth and gets an API object '''
    auth = tweepy.OAuthHandler(tokens['key'], tokens['secret'])
    auth.set_access_token(tokens['access'], tokens['access_secret'])
    return tweepy.API(auth)

api = get_api()

def reply(status):
    ''' Takes a status object and replies '''
    if isinstance(status, tweepy.Status):
        try:
            original_tweet = api.get_status(status.in_reply_to_status_id)
            text = re.sub(r"(?:\@|https?\://)\S+", "", original_tweet.text) # Remove user mentions
            r = requests.get(f'https://www.altnews.in/?s={text}')
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'lxml').find_all('article')
                if soup:
                    urls = soup[0].find_all('a')
                    if urls:
                        url, title = urls[0]['href'], urls[0]['title']
                        api.update_status(f'@{status.in_reply_to_screen_name} FactCheck {title}, {url}', status.id)
                    else:
                        print('no articles found')
        except Exception as e:
            print('Something Broke', e, status.id)

class track_streams(tweepy.StreamListener):
    
    def on_status(self, status):
        print(status.text)
        # Filter out if anyone retweets a sachbolo reply - we don't want to recursively enter a loop
        if not any([status.is_quote_status, hasattr(status, 'retweeted_status')]):
            # api.update_status(f'@{status.in_reply_to_screen_name} does it tho?', status.id)
            reply(status)


def main():
    stream_tracker = track_streams()
    myStream = tweepy.Stream(auth = api.auth, listener=stream_tracker)
    myStream.filter(track=['@sachbolopls'], is_async=True)
    print('Run Forest Run')





if __name__ == "__main__":
    main()