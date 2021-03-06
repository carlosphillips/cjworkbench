from collections import namedtuple
import json
import unittest
from asgiref.sync import async_to_sync
import dateutil
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch
from server.modules.twitter import Twitter
from server.modules.types import ProcessResult
from .util import MockParams


def table_to_result(table):
    result = ProcessResult(table)
    result.sanitize_in_place()  # alters dataframe.equals() result
    return result


class MockAiohttpRequest:
    def __init__(self, url, args, kwargs):
        self.url = url
        self.args = args
        self.kwargs = kwargs


class MockAiohttpResponse:
    def __init__(self, json_dict):
        self.json_dict = json_dict

    async def json(self):
        return self.json_dict

    def raise_for_status(self):
        pass


class MockAiohttpSession:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        self.i = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, url, *args, **kwargs):
        self.requests.append(MockAiohttpRequest(url, args, kwargs))
        ret = MockAiohttpResponse(self.responses[self.i])
        self.i += 1
        return ret


MockAuth = namedtuple('MockAuth', ['consumer_key', 'consumer_secret'])


def mock_auth(name):
    return MockAuth('a-key', 'a-secret')


# test data, excerpted from tweepy repo.
# One overlapping tweet between the two sets of two tweets, and include a
# retweet.
# Added whitespace makes nvim syntax-highlight much more quickly.
user_timeline_json = """[
{
    "created_at":"Sat Nov 05 21:38:46 +0000 2016",
    "id":795017539831103489,
    "id_str":"795017539831103489",
    "full_text":"Hello",
    "truncated":false,
    "entities":{"hashtags":[],"symbols":[],"user_mentions":[],"urls":[]},
    "source":"\\u003ca href=\\"http://twitter.com\\" rel=\\"nofollow\\"\\u003eTwitter Web Client\\u003c/a\\u003e",
    "in_reply_to_status_id":null,
    "in_reply_to_status_id_str":null,
    "in_reply_to_user_id":null,
    "in_reply_to_user_id_str":null,
    "in_reply_to_screen_name":null,
    "user":{"id":794682839556038656,"id_str":"794682839556038656","name":"Tweepy Test","screen_name":"TheTweepyTester","location":"","description":"","url":null,"entities":{"description":{"urls":[]}},"protected":false,"followers_count":1,"friends_count":18,"listed_count":0,"created_at":"Fri Nov 04 23:28:48 +0000 2016","favourites_count":0,"utc_offset":-25200,"time_zone":"Pacific Time (US & Canada)","geo_enabled":false,"verified":false,"statuses_count":112,"lang":"en","contributors_enabled":false,"is_translator":false,"is_translation_enabled":false,"profile_background_color":"000000","profile_background_image_url":"http://abs.twimg.com/images/themes/theme1/bg.png","profile_background_image_url_https":"https://abs.twimg.com/images/themes/theme1/bg.png","profile_background_tile":false,"profile_image_url":"http://abs.twimg.com/sticky/default_profile_images/default_profile_6_normal.png","profile_image_url_https":"https://abs.twimg.com/sticky/default_profile_images/default_profile_6_normal.png","profile_banner_url":"https://pbs.twimg.com/profile_banners/794682839556038656/1478382257","profile_link_color":"1B95E0","profile_sidebar_border_color":"000000","profile_sidebar_fill_color":"000000","profile_text_color":"000000","profile_use_background_image":false,"has_extended_profile":false,"default_profile":false,"default_profile_image":true,"following":false,"follow_request_sent":false,"notifications":false,"translator_type":"none"},
    "geo":null,
    "coordinates":null,
    "place":null,
    "contributors":null,
    "is_quote_status":false,
    "retweet_count":0,
    "favorite_count":0,
    "favorited":false,
    "retweeted":false,
    "lang":"en"
},
{
    "created_at":"Sat Nov 05 21:37:13 +0000 2016",
    "id":795017147651162112,
    "id_str":"795017147651162112",
    "full_text":"testing 1000 https://t.co/3vt8ITRQ3w",
    "truncated":false,
    "entities":{"hashtags":[],"symbols":[],"user_mentions":[],"urls":[],"media":[{"id":795017144849272832,"id_str":"795017144849272832","indices":[13,36],"media_url":"http://pbs.twimg.com/media/Cwh34Y0WEAA6m1l.jpg","media_url_https":"https://pbs.twimg.com/media/Cwh34Y0WEAA6m1l.jpg","url":"https://t.co/3vt8ITRQ3w","display_url":"pic.twitter.com/3vt8ITRQ3w","expanded_url":"https://twitter.com/TheTweepyTester/status/795017147651162112/photo/1","type":"photo","sizes":{"medium":{"w":1200,"h":600,"resize":"fit"},"large":{"w":1252,"h":626,"resize":"fit"},"thumb":{"w":150,"h":150,"resize":"crop"},"small":{"w":680,"h":340,"resize":"fit"}}}]},
    "extended_entities":{"media":[{"id":795017144849272832,"id_str":"795017144849272832","indices":[13,36],"media_url":"http://pbs.twimg.com/media/Cwh34Y0WEAA6m1l.jpg","media_url_https":"https://pbs.twimg.com/media/Cwh34Y0WEAA6m1l.jpg","url":"https://t.co/3vt8ITRQ3w","display_url":"pic.twitter.com/3vt8ITRQ3w","expanded_url":"https://twitter.com/TheTweepyTester/status/795017147651162112/photo/1","type":"photo","sizes":{"medium":{"w":1200,"h":600,"resize":"fit"},"large":{"w":1252,"h":626,"resize":"fit"},"thumb":{"w":150,"h":150,"resize":"crop"},"small":{"w":680,"h":340,"resize":"fit"}}}]},
    "source":"\\u003ca href=\\"https://github.com/tweepy/tweepy\\" rel=\\"nofollow\\"\\u003eTweepy dev\\u003c/a\\u003e",
    "in_reply_to_status_id":null,
    "in_reply_to_status_id_str":null,
    "in_reply_to_user_id":null,
    "in_reply_to_user_id_str":null,
    "in_reply_to_screen_name":null,
    "user":{"id":794682839556038656,"id_str":"794682839556038656","name":"Tweepy Test","screen_name":"TheTweepyTester","location":"","description":"","url":null,"entities":{"description":{"urls":[]}},"protected":false,"followers_count":1,"friends_count":18,"listed_count":0,"created_at":"Fri Nov 04 23:28:48 +0000 2016","favourites_count":0,"utc_offset":-25200,"time_zone":"Pacific Time (US & Canada)","geo_enabled":false,"verified":false,"statuses_count":112,"lang":"en","contributors_enabled":false,"is_translator":false,"is_translation_enabled":false,"profile_background_color":"000000","profile_background_image_url":"http://abs.twimg.com/images/themes/theme1/bg.png","profile_background_image_url_https":"https://abs.twimg.com/images/themes/theme1/bg.png","profile_background_tile":false,"profile_image_url":"http://abs.twimg.com/sticky/default_profile_images/default_profile_6_normal.png","profile_image_url_https":"https://abs.twimg.com/sticky/default_profile_images/default_profile_6_normal.png","profile_banner_url":"https://pbs.twimg.com/profile_banners/794682839556038656/1478382257","profile_link_color":"1B95E0","profile_sidebar_border_color":"000000","profile_sidebar_fill_color":"000000","profile_text_color":"000000","profile_use_background_image":false,"has_extended_profile":false,"default_profile":false,"default_profile_image":true,"following":false,"follow_request_sent":false,"notifications":false,"translator_type":"none"},
    "geo":null,
    "coordinates":null,
    "place":null,
    "contributors":null,
    "is_quote_status":false,
    "retweet_count":0,
    "favorite_count":0,
    "favorited":false,
    "retweeted":false,
    "possibly_sensitive":false,
    "lang":"en"
}
]"""
user_timeline2_json = """[
{
    "created_at":"Sat Nov 05 21:44:24 +0000 2016",
    "id":795018956507582465,
    "id_str":"795018956507582465",
    "full_text":"testing 1000 https://t.co/HFZNy7Fz9o",
    "truncated":false,
    "entities":{"hashtags":[],"symbols":[],"user_mentions":[],"urls":[],"media":[{"id":795018953181593600,"id_str":"795018953181593600","indices":[13,36],"media_url":"http://pbs.twimg.com/media/Cwh5hpYXgAAXF-1.jpg","media_url_https":"https://pbs.twimg.com/media/Cwh5hpYXgAAXF-1.jpg","url":"https://t.co/HFZNy7Fz9o","display_url":"pic.twitter.com/HFZNy7Fz9o","expanded_url":"https://twitter.com/TheTweepyTester/status/795018956507582465/photo/1","type":"photo","sizes":{"small":{"w":680,"h":340,"resize":"fit"},"medium":{"w":1200,"h":600,"resize":"fit"},"thumb":{"w":150,"h":150,"resize":"crop"},"large":{"w":1252,"h":626,"resize":"fit"}}}]},
    "extended_entities":{"media":[{"id":795018953181593600,"id_str":"795018953181593600","indices":[13,36],"media_url":"http://pbs.twimg.com/media/Cwh5hpYXgAAXF-1.jpg","media_url_https":"https://pbs.twimg.com/media/Cwh5hpYXgAAXF-1.jpg","url":"https://t.co/HFZNy7Fz9o","display_url":"pic.twitter.com/HFZNy7Fz9o","expanded_url":"https://twitter.com/TheTweepyTester/status/795018956507582465/photo/1","type":"photo","sizes":{"small":{"w":680,"h":340,"resize":"fit"},"medium":{"w":1200,"h":600,"resize":"fit"},"thumb":{"w":150,"h":150,"resize":"crop"},"large":{"w":1252,"h":626,"resize":"fit"}}}]},
    "source":"\\u003ca href=\\"https://github.com/tweepy/tweepy\\" rel=\\"nofollow\\"\\u003eTweepy dev\\u003c/a\\u003e",
    "in_reply_to_status_id":null,
    "in_reply_to_status_id_str":null,
    "in_reply_to_user_id":null,
    "in_reply_to_user_id_str":null,
    "in_reply_to_screen_name":null,
    "user":{"id":794682839556038656,"id_str":"794682839556038656","name":"Tweepy Test","screen_name":"TheTweepyTester","location":"","description":"","url":null,"entities":{"description":{"urls":[]}},"protected":false,"followers_count":1,"friends_count":18,"listed_count":0,"created_at":"Fri Nov 04 23:28:48 +0000 2016","favourites_count":0,"utc_offset":-25200,"time_zone":"Pacific Time (US & Canada)","geo_enabled":false,"verified":false,"statuses_count":112,"lang":"en","contributors_enabled":false,"is_translator":false,"is_translation_enabled":false,"profile_background_color":"000000","profile_background_image_url":"http://abs.twimg.com/images/themes/theme1/bg.png","profile_background_image_url_https":"https://abs.twimg.com/images/themes/theme1/bg.png","profile_background_tile":false,"profile_image_url":"http://abs.twimg.com/sticky/default_profile_images/default_profile_6_normal.png","profile_image_url_https":"https://abs.twimg.com/sticky/default_profile_images/default_profile_6_normal.png","profile_banner_url":"https://pbs.twimg.com/profile_banners/794682839556038656/1478382257","profile_link_color":"1B95E0","profile_sidebar_border_color":"000000","profile_sidebar_fill_color":"000000","profile_text_color":"000000","profile_use_background_image":false,"has_extended_profile":false,"default_profile":false,"default_profile_image":true,"following":false,"follow_request_sent":false,"notifications":false,"translator_type":"none"},
    "geo":null,
    "coordinates":null,
    "place":null,
    "contributors":null,
    "is_quote_status":false,
    "retweet_count":0,
    "favorite_count":0,
    "favorited":false,
    "retweeted":false,
    "possibly_sensitive":false,
    "lang":"en"
},
{
  "created_at": "Sat Nov 05 18:20:40 +0000 2016",
  "id": 794967685113188400,
  "id_str": "794967685113188352",
  "full_text": "RT @ritanyaaskar: Hi...tweepy darlings...my first tweets to my sweety tweeps.",
  "truncated": false,
  "entities": {
    "hashtags": [],
    "symbols": [],
    "user_mentions": [
      {
        "screen_name": "ritanyaaskar",
        "name": "Ritanya Askar Gowda",
        "id": 732544292636397600,
        "id_str": "732544292636397569",
        "indices": [
          3,
          16
        ]
      }
    ],
    "urls": []
  },
  "source":"\\u003ca href=\\"http://twitter.com\\" rel=\\"nofollow\\"\\u003eTwitter Web Client\\u003c/a\\u003e",
  "metadata": {
    "iso_language_code": "en",
    "result_type": "recent"
  },
  "in_reply_to_status_id": null,
  "in_reply_to_status_id_str": null,
  "in_reply_to_user_id": null,
  "in_reply_to_user_id_str": null,
  "in_reply_to_screen_name": null,
  "user": {
    "id": 4591599690,
    "id_str": "4591599690",
    "name": "Sujan Loy Castelino",
    "screen_name": "LoySujan",
    "location": "India",
    "description": "\\u0ca8\\u0cbe\\u0ca8\\u0cc1....\\u2764 \\u0cb8\\u0cc1\\u0c9c\\u0cc1 \\u2764..!!!  \\u0ca8\\u0cbf\\u0cae\\u0ccd\\u0cae  \\u0cb9\\u0cc3\\u0ca6\\u0caf\\u0ca6  \\u0c97\\u0cc6\\u0cb3\\u0cc6\\u0caf",
    "url": null,
    "entities": {
      "description": {
        "urls": []
      }
    },
    "protected": false,
    "followers_count": 14,
    "friends_count": 35,
    "listed_count": 0,
    "created_at": "Fri Dec 18 07:26:49 +0000 2015",
    "favourites_count": 2,
    "utc_offset": null,
    "time_zone": null,
    "geo_enabled": false,
    "verified": false,
    "statuses_count": 90,
    "lang": "en",
    "contributors_enabled": false,
    "is_translator": false,
    "is_translation_enabled": false,
    "profile_background_color": "F5F8FA",
    "profile_background_image_url": null,
    "profile_background_image_url_https": null,
    "profile_background_tile": false,
    "profile_image_url": "http:\\/\\/pbs.twimg.com\\/profile_images\\/775656019779125248\\/0zERizOe_normal.jpg",
    "profile_image_url_https": "https:\\/\\/pbs.twimg.com\\/profile_images\\/775656019779125248\\/0zERizOe_normal.jpg",
    "profile_banner_url": "https:\\/\\/pbs.twimg.com\\/profile_banners\\/4591599690\\/1478030760",
    "profile_link_color": "1DA1F2",
    "profile_sidebar_border_color": "C0DEED",
    "profile_sidebar_fill_color": "DDEEF6",
    "profile_text_color": "333333",
    "profile_use_background_image": true,
    "has_extended_profile": true,
    "default_profile": true,
    "default_profile_image": false,
    "following": false,
    "follow_request_sent": false,
    "notifications": false,
    "translator_type": "none"
  },
  "geo": null,
  "coordinates": null,
  "place": null,
  "contributors": null,
  "retweeted_status": {
    "created_at": "Tue May 17 13:01:23 +0000 2016",
    "id": 732556621352591400,
    "id_str": "732556621352591360",
    "text": "Hi...tweepy darlings...my first tweets to my sweety tweeps.",
    "truncated": false,
    "entities": {
      "hashtags": [],
      "symbols": [],
      "user_mentions": [],
      "urls": []
    },
    "metadata": {
      "iso_language_code": "en",
      "result_type": "recent"
    },
    "in_reply_to_status_id": null,
    "in_reply_to_status_id_str": null,
    "in_reply_to_user_id": null,
    "in_reply_to_user_id_str": null,
    "in_reply_to_screen_name": null,
    "user": {
      "id": 732544292636397600,
      "id_str": "732544292636397569",
      "name": "Ritanya Askar Gowda",
      "screen_name": "ritanyaaskar",
      "location": "Bengaluru, India",
      "url": null,
      "entities": {
        "description": {
          "urls": []
        }
      },
      "protected": false,
      "followers_count": 49,
      "friends_count": 75,
      "listed_count": 1,
      "created_at": "Tue May 17 12:12:24 +0000 2016",
      "favourites_count": 175,
      "utc_offset": null,
      "time_zone": null,
      "geo_enabled": true,
      "verified": false,
      "statuses_count": 102,
      "lang": "en",
      "contributors_enabled": false,
      "is_translator": false,
      "is_translation_enabled": false,
      "profile_background_color": "F5F8FA",
      "profile_background_image_url": null,
      "profile_background_image_url_https": null,
      "profile_background_tile": false,
      "profile_image_url": "http:\\/\\/pbs.twimg.com\\/profile_images\\/782258367821590528\\/tokAIStu_normal.jpg",
      "profile_image_url_https": "https:\\/\\/pbs.twimg.com\\/profile_images\\/782258367821590528\\/tokAIStu_normal.jpg",
      "profile_banner_url": "https:\\/\\/pbs.twimg.com\\/profile_banners\\/732544292636397569\\/1474193325",
      "profile_link_color": "1DA1F2",
      "profile_sidebar_border_color": "C0DEED",
      "profile_sidebar_fill_color": "DDEEF6",
      "profile_text_color": "333333",
      "profile_use_background_image": true,
      "has_extended_profile": true,
      "default_profile": true,
      "default_profile_image": false,
      "following": false,
      "follow_request_sent": false,
      "notifications": false,
      "translator_type": "none"
    },
    "geo": null,
    "coordinates": null,
    "place": null,
    "contributors": null,
    "is_quote_status": false,
    "retweet_count": 2,
    "favorite_count": 5,
    "favorited": false,
    "retweeted": false,
    "lang": "en"
  },
  "is_quote_status": false,
  "retweet_count": 2,
  "favorite_count": 0,
  "favorited": false,
  "retweeted": false,
  "lang": "en"
}
]"""


P = MockParams.factory(querytype=0, username='username', query='query',
                       listurl='listurl', twitter_credentials={
                           'oauth_token': 'a-token',
                           'oauth_token_secret': 'a-token-secret',
                       }, accumulate=True)


def fetch(params, stored_dataframe=None):
    async def get_stored_dataframe():
        return stored_dataframe

    return async_to_sync(Twitter.fetch)(
        params,
        get_stored_dataframe=get_stored_dataframe
    )


class MockWfModule:
    def __init__(self, **kwargs):
        self.params = P(**kwargs)
        self.fetched_table = None

        for k, v in kwargs.items():
            setattr(self, k, v)

    def get_params(self):
        return self.params

    def retrieve_fetched_table(self):
        return self.fetched_table


def dt(s):
    return dateutil.parser.parse(s, ignoretz=True)


mock_statuses = json.loads(user_timeline_json)
mock_statuses2 = json.loads(user_timeline2_json)

mock_tweet_table = pd.DataFrame({
    'screen_name': ['TheTweepyTester', 'TheTweepyTester'],
    'created_at': [dt('2016-11-05T21:38:46Z'), dt('2016-11-05T21:37:13Z')],
    'text': ['Hello', 'testing 1000 https://t.co/3vt8ITRQ3w'],
    'retweet_count': [0, 0],
    'favorite_count': [0, 0],
    'in_reply_to_screen_name': [None, None],
    'retweeted_status_screen_name': [None, None],
    'source': ['Twitter Web Client', 'Tweepy dev'],
    'id': [795017539831103489, 795017147651162112],
})

mock_tweet_table2 = pd.DataFrame({
    'screen_name': ['TheTweepyTester', 'LoySujan'],
    'created_at': [dt('2016-11-05T21:44:24Z'), dt('2016-11-05T18:20:40Z')],
    'text': [
        'testing 1000 https://t.co/HFZNy7Fz9o',
        ('RT @ritanyaaskar: Hi...tweepy darlings...my first tweets to my '
         'sweety tweeps.'),
    ],
    'retweet_count': [0, 2],
    'favorite_count': [0, 0],
    'in_reply_to_screen_name': [None, None],
    'retweeted_status_screen_name': [None, 'ritanyaaskar'],
    'source': ['Tweepy dev', 'Twitter Web Client'],
    'id': [795018956507582465, 794967685113188400],
})


def Err(error):
    return ProcessResult(error=error)


class TwitterTests(unittest.TestCase):
    def test_fetch_empty_query_and_secret(self):
        result = fetch(P(querytype=1, query='', twitter_credentials=None))
        self.assertIsNone(result)

    def test_fetch_empty_query(self):
        result = fetch(P(querytype=1, query=''))
        self.assertEqual(result, Err('Please enter a query'))

    def test_fetch_empty_secret(self):
        result = fetch(P(twitter_credentials=None))
        self.assertEqual(result, Err('Please sign in to Twitter'))

    def test_fetch_invalid_username(self):
        result = fetch(P(querytype=0, username='@@batman'))
        self.assertEqual(result, Err('Not a valid Twitter username'))

    def test_invalid_list(self):
        result = fetch(P(querytype=2,
                         listurl='https://twitter.com/a/lists/@b'))
        self.assertEqual(result, Err('Not a valid Twitter list URL'))

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_fetch_user_timeline_accumulate(self, session):
        session.return_value = mock_session = MockAiohttpSession([
            mock_statuses2,
            []
        ])

        params = P(querytype=0, username='foouser', accumulate=True)

        result = fetch(params, mock_tweet_table)
        expected = pd.concat([mock_tweet_table2, mock_tweet_table],
                             ignore_index=True, sort=False)
        self.assertEqual(result.error, '')
        assert_frame_equal(result.dataframe, expected)

        # query should start where we left off
        self.assertEqual(
            mock_session.requests[0].url,
            (
                'https://api.twitter.com/1.1/statuses/user_timeline.json'
                '?screen_name=foouser&tweet_mode=extended&count=200'
                '&since_id=795017539831103489'
            )
        )
        self.assertEqual(
            mock_session.requests[1].url,
            (
                'https://api.twitter.com/1.1/statuses/user_timeline.json'
                '?screen_name=foouser&tweet_mode=extended&count=200'
                '&since_id=795017539831103489&max_id=794967685113188399'
            )
        )

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_fetch_accumulate_from_None(self, session):
        # https://www.pivotaltracker.com/story/show/160258591
        # Empty dataframe shouldn't change types
        session.return_value = MockAiohttpSession([
            mock_statuses,
            []
        ])

        result = fetch(P(accumulate=True), None)
        self.assertEqual(result.error, '')
        assert_frame_equal(result.dataframe, mock_tweet_table)

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_fetch_accumulate_from_empty(self, session):
        # https://www.pivotaltracker.com/story/show/160258591
        # Empty dataframe shouldn't change types
        session.return_value = MockAiohttpSession([
            mock_statuses,
            []
        ])

        result = fetch(P(accumulate=True), pd.DataFrame())  # missing columns
        self.assertEqual(result.error, '')
        assert_frame_equal(result.dataframe, mock_tweet_table)

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_fetch_accumulate_all_empty(self, session):
        # https://www.pivotaltracker.com/story/show/160258591
        # Empty dataframe shouldn't change types
        session.return_value = MockAiohttpSession([
            []
        ])

        result = fetch(P(accumulate=True), pd.DataFrame())  # missing columns
        self.assertEqual(result.error, '')
        expected = mock_tweet_table[0:0].reset_index(drop=True)  # empty table
        assert_frame_equal(result.dataframe, expected)

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_fetch_accumulate_empty_upon_data(self, session):
        # https://www.pivotaltracker.com/story/show/160258591
        # Empty dataframe shouldn't change types
        session.return_value = MockAiohttpSession([
            []
        ])

        result = fetch(P(accumulate=True), mock_tweet_table)  # missing columns
        self.assertEqual(result.error, '')
        assert_frame_equal(result.dataframe, mock_tweet_table)

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_accumulate_recover_after_bug_160258591(self, session):
        # https://www.pivotaltracker.com/story/show/160258591
        # 'id', 'retweet_count' and 'favorite_count' had wrong type after
        # accumulating an empty table. Now the bad data is in our database;
        # let's convert back to the type we want.
        session.return_value = MockAiohttpSession([
            # Fix it _no matter what_ -- even if we aren't adding any data
            []
        ])

        # Simulate the bug: convert everything to str
        bad_table = mock_tweet_table.copy()
        nulls = bad_table.isna()
        bad_table = bad_table.astype(str)
        bad_table[nulls] = None

        result = fetch(P(accumulate=True), bad_table)
        self.assertEqual(result.error, '')
        assert_frame_equal(result.dataframe, mock_tweet_table)

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_twitter_search(self, session):
        session.return_value = mock_session = MockAiohttpSession([
            mock_statuses,
            []
        ])

        # Actually fetch!
        result = fetch(P(querytype=1, query='cat'))
        self.assertEqual(result.error, '')
        self.assertEqual([req.url for req in mock_session.requests], [
            (
                'https://api.twitter.com/1.1/search/tweets.json'
                '?q=cat&tweet_mode=extended&count=100'
            ),
            (
                'https://api.twitter.com/1.1/search/tweets.json'
                '?q=cat&tweet_mode=extended&count=100'
                '&max_id=795017147651162111'
            )
        ])

        # Check that render output is right
        assert_frame_equal(result.dataframe, mock_tweet_table)

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_twitter_list(self, session):
        session.return_value = mock_session = MockAiohttpSession([
            mock_statuses,
            []
        ])

        # Actually fetch!
        result = fetch(
            P(querytype=2,
              listurl='https://twitter.com/thatuser/lists/theirlist')
        )
        self.assertEqual([req.url for req in mock_session.requests], [
            (
                'https://api.twitter.com/1.1/lists/statuses.json'
                '?owner_screen_name=thatuser&slug=theirlist'
                '&tweet_mode=extended&count=200'
            ),
            (
                'https://api.twitter.com/1.1/lists/statuses.json'
                '?owner_screen_name=thatuser&slug=theirlist'
                '&tweet_mode=extended&count=200&max_id=795017147651162111'
            )
        ])

        # Check that render output is right
        self.assertEqual(result.error, '')
        assert_frame_equal(result.dataframe, mock_tweet_table)

    def test_render_empty_no_query(self):
        # When we haven't fetched, we shouldn't show any columns (for
        # consistency with other modules)
        result = Twitter.render(P(querytype=1, query=''), pd.DataFrame(),
                                fetch_result=None)
        assert_frame_equal(result.dataframe, pd.DataFrame())

    def test_render_empty_search_result(self):
        # An empty table might be stored as zero-column. This is a bug, but we
        # must handle it because we have actual data like this. We want to
        # output all the same columns as a tweet table.
        result = Twitter.render(P(querytype=1, query='cat'), pd.DataFrame(),
                                fetch_result=ProcessResult(pd.DataFrame()))
        assert_frame_equal(result.dataframe, mock_tweet_table[0:0])

    @patch('server.oauth.OAuthService.lookup_or_none', mock_auth)
    @patch('aiohttp.ClientSession')
    def test_add_retweet_status_screen_name(self, session):
        # Migration: what happens when we accumulate tweets
        # where the old stored table does not have retweet_status_screen_name?
        # We should consider those to have just None in that column
        session.return_value = MockAiohttpSession([
            # add tweets which are not duplicated (mocking max_id)
            mock_statuses2,
            []
        ])

        # Simulate old format by deleting retweet screen name column
        old_format_table = mock_tweet_table.copy(deep=True) \
            .drop('retweeted_status_screen_name', axis=1)

        result = fetch(P(accumulate=True), old_format_table)

        expected = pd.concat([mock_tweet_table2, mock_tweet_table],
                             ignore_index=True, sort=False)
        expected.loc[3:5, 'retweeted_status_screen_name'] = None
        self.assertEqual(result.error, '')
        assert_frame_equal(result.dataframe, expected)
