# -*- coding: utf-8 -*-

import os
import sys
import re
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import requests
import simplecache
import time
import unicodedata
import StringIO
from datetime import datetime, timedelta
from urlparse import parse_qs
from zipfile import ZipFile

addon = xbmcaddon.Addon()
video_info = xbmc.InfoTagVideo()

author = addon.getAddonInfo('author')
script_id = addon.getAddonInfo('id')
script_name = addon.getAddonInfo('name')
version = addon.getAddonInfo('version')
get_string = addon.getLocalizedString

script_dir = xbmc.translatePath(addon.getAddonInfo('path')).decode("utf-8")
profile = xbmc.translatePath(addon.getAddonInfo('profile')).decode("utf-8")
libs_dir = xbmc.translatePath(os.path.join(script_dir, 'resources', 'lib')).decode("utf-8")
temp_dir = xbmc.translatePath(os.path.join(profile, 'temp', '')).decode("utf-8")

player = xbmc.Player()

sys.path.append(libs_dir)

base_plugin_url = sys.argv[0]

plugin_handle = int(sys.argv[1])

api_url = 'https://kodi.titlovi.com/api/subtitles'

if not xbmcvfs.exists(temp_dir):
    xbmcvfs.mkdirs(temp_dir)

addon_cache = simplecache.SimpleCache()


def logger(message):
    xbmc.log(u"{0} - {1}".format(__name__, message).encode('utf-8'))


def show_notification(message):
    xbmc.executebuiltin('Notification({0}, {1})'.format(script_name, message))


def normalize_string(_string):
    return unicodedata.normalize('NFKD', unicode(_string, 'utf-8')).encode('ascii', 'ignore')


def parse_season_episode(_string):
    """
    Function used for parsing season and episode numbers from string.
    If season and episode are found they are stripped from original string.
    Allowed format is 'S01E01'. Allowed number range is 00-99.
    Returns three-tuple.
    """

    if not _string:
        return _string, None, None
    results = re.findall('[sS](\d{2})[eE](\d{2})', _string)
    if not results:
        return _string, None, None
    try:
        season = int(results[0][0])
        if season < 0 or season > 99:
            season = None
    except Exception as e:
        logger(e)
        season = None

    try:
        episode = int(results[0][1])
        if episode < 0 or episode > 99:
            episode = None
    except Exception as e:
        logger(e)
        episode = None

    if season is not None and episode is not None:
        _string = _string.lower().replace('s{0}e{1}'.format(results[0][0], results[0][1]), '')

    return _string, season, episode


language_mapping = {
    'English': 'English',
    'Croatian': 'Hrvatski',
    'Serbian': 'Srpski',
    'Slovenian': 'Slovenski',
    'Macedonian': 'Makedonski',
    'Bosnian': 'Bosanski'
}

language_icon_mapping = {
    'English': 'en',
    'Hrvatski': 'hr',
    'Srpski': 'sr',
    'Slovenski': 'sl',
    'Makedonski': 'mk',
    'Bosanski': 'bs'
}


class ActionHandler(object):
    def __init__(self, params):
        """
        :param params:
            {
                'action': string, one of: 'search', 'manualsearch', 'download',
                'languages': comma separated list of strings,
                'preferredlanguage': string,
                'searchstring': string, exists if 'action' param is 'manualsearch'
            }
        """

        self.params = params
        self.username = addon.getSetting("titlovi-username")
        self.password = addon.getSetting("titlovi-password")
        self.action = self.params['?action'][0]
        self.login_token = None
        self.user_id = None

    def validate_params(self):
        """
        Method used for validating required parameters: 'username', 'password' and 'action'.
        """
        if not self.username or not self.password:
            show_notification(get_string(32005))
            return False
        if self.action not in ('search', 'manualsearch', 'download'):
            show_notification(get_string(2103))
            return False
        return True

    def get_prepared_language_param(self):
        """
        Method used for parsing chosen subtitle languages and formatting them in format accepted by Titlovi.com API.
        """

        if not self.params['languages']:
            return None

        lang_list = []
        for lang in self.params['languages'][0].split(','):
            if lang == 'Serbo-Croatian':
                if language_mapping['Serbian'] not in lang_list:
                    lang_list.append(language_mapping['Serbian'])
                if language_mapping['Croatian'] not in lang_list:
                    lang_list.append(language_mapping['Croatian'])
            else:
                if lang in language_mapping and language_mapping[lang] not in lang_list:
                    lang_list.append(language_mapping[lang])

        lang_string = '|'.join(lang_list)

        return lang_string

    def handle_login(self):
        """
        Method used for sending user login request.

        OK return:
            {
                "ExpirationDate": datetime string (format: '%Y-%m-%dT%H:%M:%S.%f'),
                "Token": string,
                "UserId": integer,
                "UserName": string
            }

        Error return: None
        """
        logger('starting user login')
        login_params = dict(username=self.username, password=self.password, json=True)
        try:
            response = requests.post('{0}/gettoken'.format(api_url), params=login_params)
            logger('Response status: {0}'.format(response.status_code))
            if response.status_code == requests.codes.ok:
                resp_json = response.json()
                logger('login response data: {0}'.format(resp_json))
                return resp_json
            elif response.status_code == requests.codes.unauthorized:
                show_notification(get_string(32006))
                return None
            else:
                return None
        except Exception as e:
            logger(e)
            return None

    def set_login_data(self, login_data):
        addon_cache.set('titlovi_com_login_data', login_data, expiration=timedelta(days=7))
        self.login_token = login_data.get('Token')
        self.user_id = login_data.get('UserId')

    def user_login(self):
        """
        Method used for logging in with titlovi.com username and password.
        After successful login data is stored in cache.
        """
        titlovi_com_login_data = addon_cache.get('titlovi_com_login_data')
        if not titlovi_com_login_data:
            logger('login data not found in cache')
            login_data = self.handle_login()
            if login_data is None:
                show_notification(get_string(32007))
                return False
            self.set_login_data(login_data)
            return True

        logger('user login data found in cache: {0}'.format(titlovi_com_login_data))
        expiration_date_string = titlovi_com_login_data.get('ExpirationDate')
        expiration_date = datetime(*(time.strptime(expiration_date_string, '%Y-%m-%dT%H:%M:%S.%f')[0:6]))
        # expiration_date = datetime.strptime(expiration_date_string, '%Y-%m-%dT%H:%M:%S.%f')
        date_delta = expiration_date - datetime.now()
        if date_delta.days <= 1:
            login_data = self.handle_login()
            if login_data is None:
                show_notification(get_string(32007))
                return False
            self.set_login_data(login_data)
            return True

        self.set_login_data(titlovi_com_login_data)
        return True

    def handle_action(self):
        """
        Method used for calling other action methods depending on 'action' parameter.
        """

        if self.action in ('search', 'manualsearch'):
            self.handle_search_action()
        elif self.action == 'download':
            self.handle_download_action()
        else:
            logger(u'Invalid action')
            show_notification(get_string(2103))

    def handle_search_action(self):
        """
        Method used for searching
        """
        logger('starting search')
        search_params = {}
        if self.action == 'manualsearch':
            logger('starting manualsearch')
            search_string = self.params.get('searchstring')
            if not search_string:
                show_notification(get_string(32008))
                return

            search_string = search_string[0]
            if not search_string:
                show_notification(get_string(32008))
                return
            logger('search_string {0}'.format(search_string))

            search_string, season, episode = parse_season_episode(search_string)

            if season is not None:
                search_params['season'] = season
            if episode is not None:
                search_params['episode'] = episode
            clean_title, year = xbmc.getCleanMovieTitle(search_string)
            search_params['query'] = clean_title
            logger(search_params)

        else:
            imdb_id = video_info.getIMDBNumber()
            if imdb_id:
                search_params['imdbID'] = imdb_id

            season = str(xbmc.getInfoLabel("VideoPlayer.Season"))
            episode = str(xbmc.getInfoLabel("VideoPlayer.Episode"))
            tv_show_title = normalize_string(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))
            if tv_show_title:
                search_params['query'] = tv_show_title
                if season is not None:
                    search_params['season'] = season
                if episode is not None:
                    search_params['episode'] = episode
            else:
                title = normalize_string(xbmc.getInfoLabel("VideoPlayer.OriginalTitle"))
                if not title:
                    title = normalize_string(xbmc.getInfoLabel("VideoPlayer.Title"))
                # TODO parse season/epizode info
                if title:
                    title, season, episode = parse_season_episode(title)
                    if season is not None:
                        search_params['season'] = season
                    if episode is not None:
                        search_params['episode'] = episode

                    clean_title, year = xbmc.getCleanMovieTitle(title)
                    search_params['query'] = clean_title
                else:
                    current_video_name = player.getPlayingFile()
                    current_video_name, season, episode = parse_season_episode(current_video_name)
                    if season is not None:
                        search_params['season'] = season
                    if episode is not None:
                        search_params['episode'] = episode

                    try:
                        clean_video_name, year = xbmc.getCleanMovieTitle(current_video_name)
                    except Exception as e:
                        logger(e)
                        show_notification(get_string(32009))
                        return
                    search_params['query'] = clean_video_name

        search_language = self.get_prepared_language_param()
        if search_language:
            search_params['lang'] = search_language

        sorted_search_params = sorted(search_params.items())
        hashable_search_params = tuple(temp for tuple_param in sorted_search_params for temp in tuple_param)
        params_hash = unicode(repr(hashable_search_params))
        result_list = addon_cache.get(params_hash)
        if result_list:
            logger('results loaded from cache')

        if not result_list:
            logger('results not found in cache, getting results from API')
            search_params['token'] = self.login_token
            search_params['userid'] = self.user_id
            search_params['json'] = True
            result_list_page = 1
            result_list = []
            logger('search params: {0}'.format(search_params))
            try:
                response = requests.get('{0}/search'.format(api_url), params=search_params)
                logger('Response status code: {0}'.format(response.status_code))
                if response.status_code == requests.codes.ok:
                    resp_json = response.json()
                elif response.status_code == requests.codes.unauthorized:
                    """
                    Force user login in case of Unauthorized response
                    and retry search with new login token
                    """
                    is_loggedin = self.user_login()
                    if not is_loggedin:
                        logger('Force login failed, exiting!')
                        return
                    search_params['token'] = self.login_token
                    search_params['userid'] = self.user_id
                    response = requests.get('{0}/search'.format(api_url), params=search_params)
                    if response.status_code == requests.codes.ok:
                        resp_json = response.json()
                    else:
                        show_notification(get_string(32001))
                        logger('Invalid response status code, exiting!')
                        return
                else:
                    logger('Invalid response status code, exiting!')
                    show_notification(get_string(32001))
                    return

                if resp_json['SubtitleResults']:
                    result_list.extend(resp_json['SubtitleResults'])

            except Exception as e:
                logger(e)
                show_notification(get_string(32001))
                return

            if result_list:
                addon_cache.set(params_hash, result_list, expiration=timedelta(days=3))

        for result_item in result_list:
            title = result_item['Title']
            if result_item['Season'] and result_item['Episode']:
                title = u'{0} S{1}E{2}'.format(title, result_item['Season'], result_item['Episode'])

            if result_item['Release']:
                title = u'{0} {1}'.format(title, result_item['Release'])

            listitem = xbmcgui.ListItem(
                label=result_item['Lang'],
                label2=title,
                iconImage=str(int(result_item['Rating'])),
                thumbnailImage=language_icon_mapping[result_item['Lang']]
            )
            url = "plugin://{0}/?action=download&media_id={1}&type={2}" \
                .format(script_id, result_item['Id'], result_item['Type'])

            xbmcplugin.addDirectoryItem(handle=plugin_handle, url=url, listitem=listitem, isFolder=False)

    def handle_download_action(self):
        """
        Method used for downloading subtitle zip file and extracting it.
        If subtitle file is already downloaded it is reused.
        """
        subtitle_exists = False
        cache_key = 'titlovi_com_subtitle_{0}_{1}'.format(self.params['media_id'], self.params['type'])
        subtitle_file = addon_cache.get(cache_key)
        if subtitle_file:
            subtitle_file_path = os.path.join(temp_dir, subtitle_file)
            if os.path.exists(subtitle_file_path) and os.path.isfile(subtitle_file_path):
                subtitle_exists = True
                logger('subtitle_file found in cache')

        if not subtitle_exists:
            logger('subtitle_file not found in cache, starting download')
            download_url = "https://titlovi.com/download/?type={0}&mediaid={1}" \
                .format(self.params['type'][0], self.params['media_id'][0])
            try:
                logger(download_url)
                user_agent = "User-Agent=Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.2.3) \
                             Gecko/20100401 Firefox/3.6.3 ( .NET CLR 3.5.30729)"
                headers = {'User-Agent': user_agent, 'Referer': 'www.titlovi.com'}
                response = requests.get(download_url, headers=headers)
                if response.status_code != requests.codes.ok:
                    show_notification(get_string(32010))
                    return
            except Exception as e:
                logger(e)
                show_notification(get_string(32010))
                return

            zip_file = ZipFile(StringIO.StringIO(response.content))
            zip_contents = zip_file.namelist()
            if not zip_contents:
                show_notification(get_string(32010))
                return

            subtitle_file = zip_contents[0]
            logger('subtitle_file: {0}'.format(subtitle_file))
            zip_file.extractall(temp_dir)
            subtitle_file_path = os.path.join(temp_dir, subtitle_file)
            addon_cache.set(cache_key, subtitle_file, expiration=timedelta(days=3))

        list_item = xbmcgui.ListItem(label=subtitle_file)
        xbmcplugin.addDirectoryItem(handle=plugin_handle, url=subtitle_file_path, listitem=list_item, isFolder=False)


"""
params_dict:
{'action': ['manualsearch'], 'languages': ['English,Croatian'], 'searchstring': ['test'], 'preferredlanguage': ['English']}
"""

params_dict = parse_qs(sys.argv[2])
logger(params_dict)
action_handler = ActionHandler(params_dict)
if action_handler.validate_params():
    is_user_loggedin = action_handler.user_login()
    if is_user_loggedin:
        logger(u'user is logged in')
        action_handler.handle_action()

xbmcplugin.endOfDirectory(plugin_handle)
