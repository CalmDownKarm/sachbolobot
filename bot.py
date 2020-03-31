import os
import re
import json
import time
import logging
import requests
from urllib3.exceptions import ReadTimeoutError

from algoliasearch.search_client import SearchClient
import tweepy

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


def init_algolia():
    ''' init the algolia index '''
    client = SearchClient.create(
        tokens['algolia_appid'], tokens['algolia_adminAPI'])
    logging.info(client.list_indices())
    index = client.init_index('CoronaFactChecks')
    index.set_settings({
        'removeStopWords': True
    })
    return index


api = get_api()
logging.info('global api object created')
index = init_algolia()


def reply(status):
    ''' Takes a status object and replies '''
    try:
        original_tweet = api.get_status(status.in_reply_to_status_id)
        text = re.sub(r"(?:\@|https?\://)\S+", "",
                      original_tweet.text)  # Remove user mentions
        # search our index
        results = index.search(text)
        if results['nbHits'] > 0:
            best_result = results['hits'][0]
            api.update_status(
                f'@{status.in_reply_to_screen_name} This has been debunked, {best_result["fact_checked_reason"]} read more at {best_result["link"]} ')
            logging.info(f'Replied, {status.id}')
        else:
            api.update_status(
                f'@{status.in_reply_to_screen_name} No matching articles found in our search')
    except Exception as e:
        logging.error(e)


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
