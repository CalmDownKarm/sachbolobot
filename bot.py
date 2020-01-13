import os
import re
import json
import time
import logging
import requests
from urllib3.exceptions import ReadTimeoutError

import tweepy
from bs4 import BeautifulSoup

with open('tokens.json') as f:
    tokens = json.load(f)

logging.basicConfig(filename=f'{time.ctime()}bot.log', filemode='w',
                    format='%(process)d - %(asctime)s - %(levelname)s - %(message)s', 
                    level=os.environ.get("LOGLEVEL", "INFO"))


def get_api():
    ''' Establishes auth and gets an API object '''
    auth = tweepy.OAuthHandler(tokens['key'], tokens['secret'])
    auth.set_access_token(tokens['access'], tokens['access_secret'])
    logging.info('auth token set')
    return tweepy.API(auth)


api = get_api()
logging.info('global api object created')


def reply(status):
    ''' Takes a status object and replies '''
    try:
        original_tweet = api.get_status(status.in_reply_to_status_id)
        text = re.sub(r"(?:\@|https?\://)\S+", "",
                      original_tweet.text)  # Remove user mentions
        r = requests.get(f'https://www.altnews.in/?s={text}')
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'lxml').find_all('article')
            if soup:
                urls = soup[0].find_all('a')
                if urls:
                    url, title = urls[0]['href'], urls[0]['title']
                    api.update_status(
                        f'@{status.in_reply_to_screen_name} FactCheck {title}, {url}', original_tweet.id)
                    logging.info(f'Succes reply made {status.id}')
                else:
                    api.update_status(
                        f'@{status.in_reply_to_screen_name} No Articles Found', original_tweet.id)
                    logging.error(f'No article found {status.id}')
            else:
                logging.error(f'No soup object {status.id}')
        else:
            logging.error(f'Alt News Request Broke {status.id}')
    except Exception as e:
        logging.error(f'Something Broke {status.id}, {e}')


class track_streams(tweepy.StreamListener):

    def on_status(self, status):
        logging.info(f'Invoked: {status.text}, id: {status.id}')
        # Filter out if anyone retweets a sachbolo reply - we don't want to recursively enter a loop
        if not any([status.is_quote_status, hasattr(status, 'retweeted_status')]):
            reply(status)


def start_stream(stream, **kwargs):
    try:
        stream.filter(**kwargs)
    except ReadTimeoutError:
        stream.disconnect()
        logging.exception('ReadTimeoutError exception')
        start_stream(stream, **kwargs)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, Exception) as e:
        stream.disconnect()
        logging.exception(f'Fatal exception. Consult logs.{e}')
        start_stream(stream, **kwargs)


def main():
    stream_tracker = track_streams()
    myStream = tweepy.Stream(auth=api.auth, listener=stream_tracker)
    start_stream(myStream, track=['@sachbolopls'], is_async=True)
    logging.info('Streaming On')


if __name__ == "__main__":
    main()
