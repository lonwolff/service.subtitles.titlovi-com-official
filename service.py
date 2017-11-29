# -*- coding: utf-8 -*-

import os
import shutil
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import requests
import simplecache
import time
import unicodedata
from datetime import datetime
from urlparse import parse_qs
from os.path import basename
from zipfile import ZipFile
from datetime import timedelta

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
                if language_mapping[lang] not in lang_list:
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
            elif resp_json.status_code == requests.codes.unauthorized:
                show_notification('Unauthorized, please check your login information!')
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
                show_notification(u'Titlovi.com login error, try again')
                return False
            self.set_login_data(login_data)
            return True
        
        logger('user login data found in cache: {0}'.format(titlovi_com_login_data))
        expiration_date_string = titlovi_com_login_data.get('ExpirationDate')
        expiration_date = datetime(*(time.strptime(expiration_date_string,  '%Y-%m-%dT%H:%M:%S.%f')[0:6]))
        #expiration_date = datetime.strptime(expiration_date_string, '%Y-%m-%dT%H:%M:%S.%f')
        date_delta = expiration_date - datetime.now()
        if date_delta.days <= 1:
            login_data = self.handle_login()
            if login_data is None:
                show_notification(u'Titlovi.com login error, try again')
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
        search_params = dict(token=self.login_token, userid=self.user_id, json=True)

        if self.action == 'manualsearch':
            search_string = self.params.get('searchstring')
            if not search_string:
                show_notification(u'Please enter search text!')
                return
            search_params['query'] = search_string
        else:
            imdb_id = video_info.getIMDBNumber()
            if imdb_id:
                search_params['imdbID'] = imdb_id

            season = str(xbmc.getInfoLabel("VideoPlayer.Season"))
            episode = str(xbmc.getInfoLabel("VideoPlayer.Episode"))
            tv_show_title = normalize_string(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))
            if tv_show_title:
                search_params['query'] = tv_show_title
                if season:
                    search_params['season'] = season 
                if episode:
                    search_params['episode'] = episode
            else:
                title = normalize_string(xbmc.getInfoLabel("VideoPlayer.OriginalTitle"))
                if not title:
                    title = normalize_string(xbmc.getInfoLabel("VideoPlayer.Title"))
                
                if title:
                    search_params['query'] = title
                else:
                    try:
                        current_video_name, year = xbmc.getCleanMovieTitle(player.getPlayingFile())
                    except Exception as e:
                        logger(e)
                        show_notification(u'Video not playing!')
                        return
                    search_params['query'] = current_video_name

        search_language = self.get_prepared_language_param()
        if search_language:
            search_params['lang'] = search_language

        logger('search params: {0}'.format(search_params))

        sorted_search_params = sorted(search_params.items())
        hashable_search_params = tuple(temp for tuple_param in sorted_search_params for temp in tuple_param)
        logger('hashable_search_params: {0}'.format(hashable_search_params))
        params_hash = unicode(hash(hashable_search_params))
        logger('params_hash: {0}'.format(params_hash))
        result_list = addon_cache.get(params_hash)
        if result_list:
            logger('results loaded from cache')

        if not result_list:
            logger('results not found in cache, getting results from API')
            result_list_page = 1
            result_list = []
            while True:
                search_params['pageNum'] = result_list_page
                try:
                    response = requests.get('{0}/search'.format(api_url), params=search_params)
                    logger('Response status code: {0}'.format(response.status_code))
                    if response.status_code == requests.codes.ok:
                        resp_json = response.json()
                    elif resp_json.status_code == requests.codes.unauthorized:
                        # force user login in case of Unauthorized response
                        is_loggedin = self.user_login()
                        if not is_loggedin:
                            logger('Force login failed, exiting!')
                            return
                    else:
                        logger('Invalid response status code, exiting!')
                        return 
                    
                    if resp_json['SubtitleResults']:
                        result_list.extend(resp_json['SubtitleResults'])

                    if resp_json['PagesAvailable'] > resp_json['CurrentPage']:
                        result_list_page = resp_json['CurrentPage'] + 1
                    else:
                        break
                except Exception as e:
                    logger(e)
                    return
            logger('Search response data: {0}'.format(result_list))

            if result_list:
                addon_cache.set(params_hash, result_list, expiration=timedelta(days=3))

        for result_item in result_list:
            listitem = xbmcgui.ListItem(
                label=result_item['Lang'], 
                label2=result_item['Title'], 
                iconImage='5',
                thumbnailImage=language_icon_mapping[result_item['Lang']]
            )
            url = "plugin://{0}/?action=download&media_id={1}&type={2}"\
                .format(script_id, result_item['Id'], result_item['Type'])

            xbmcplugin.addDirectoryItem(handle=plugin_handle, url=url, listitem=listitem, isFolder=False)

    def handle_download_action(self):
        download_url = "https://titlovi.com/download/?type={0}&mediaid={1}"\
            .format(self.params['type'], self.params['media_id'])

        zip_file_location = '/home/tomislav/python_projects/kodi_titlovi_com/test_subtitle.zip'
        if not os.path.exists(zip_file_location) or not os.path.isfile(zip_file_location):
            show_notification(u'Subtitle file not found')
            return

        xbmc.sleep(500)
        xbmc.executebuiltin(('XBMC.Extract("%s","%s")' % (zip_file_location, temp_dir,)).encode('utf-8'), True)
        subtitle_file = xbmcvfs.listdir(zip_file_location)[1][0]
        subtitle_file = os.path.join(temp_dir, subtitle_file)
        if xbmcvfs.exists(subtitle_file):
            list_item = xbmcgui.ListItem(label=subtitle_file)
            xbmcplugin.addDirectoryItem(handle=plugin_handle, url=subtitle_file, listitem=list_item, isFolder=False)

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
