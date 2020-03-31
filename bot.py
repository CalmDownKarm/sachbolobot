import os
import re
import json
import time
import logging
import requests
import traceback
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
    logging.info(f'status{status.in_reply_to_screen_name}')
    logging.info(f'{status}')
    try:
        original_tweet = api.get_status(status.in_reply_to_status_id)
        logging.info('Reached here')
        text = re.sub(r"(?:\@|https?\://)\S+", "",
                      original_tweet.text)  # Remove user mentions
        logging.info(f'text - {text}')
        # search our index
        SearchResults = index.search(text)
        if SearchResults['nbHits'] > 0:
            _reason, _link = SearchResults['hits'][0]['fact_checked_reason'], SearchResults['hits'][0]['link']
            reply_string = ' '.join([
                f'@{status.in_reply_to_screen_name} ',
                f'This has been debunked, {_reason} '
                f'read more at {_link}'
            ])
            reply = api.update_status(reply_string, in_reply_to_status_id=original_tweet.id)
            logging.info(f'Replied, Reply ID: {reply.id}, Status ID: {status.id}')
        else:
            api.update_status(
                f'@{status.in_reply_to_screen_name} No matching article found in our search', in_reply_to_status_id=original_tweet.id)
            logging.error(f'No match {text}')
    except Exception as e:
        logging.error(traceback.format_exc())


class track_streams(tweepy.StreamListener):

    def on_status(self, status):
        logging.info(f'Invoked: {status.text}, id: {status.id}')
        # Filter out if anyone retweets a sachbolo reply - we don't want to recursively enter a loop
        if not any([status.is_quote_status, hasattr(status, 'retweeted_status')]):
            logging.info('trying to reply')
            reply(status)
        else:
            logging.error('Did not reply')


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
