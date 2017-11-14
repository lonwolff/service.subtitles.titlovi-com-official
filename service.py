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
from urlparse import parse_qs
from os.path import basename
from zipfile import ZipFile
from datetime import timedelta

addon = xbmcaddon.Addon()
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

api_url = 'temp_url'

if not xbmcvfs.exists(temp_dir):
    xbmcvfs.mkdirs(temp_dir)

addon_cache = simplecache.SimpleCache()


def logger(message):
    xbmc.log(u"%{0} - %{1}".format(__name__, message).encode('utf-8'))


def show_notification(header, message):
    xbmc.executebuiltin('Notification({0}, {1})'.format(header, message))

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
        self.login_cookie = None

    def validate_params(self):
        """
        Method used for validating required parameters: 'username', 'password' and 'action'.
        """
        if not self.username or not self.password:
            show_notification(script_name, get_string(32005))
            return False
        if self.action not in ('search', 'manualsearch', 'download'):
            show_notification(script_name, get_string(2103))
            return False
        return True
    
    def user_login(self):
        """
        Method used for logging in with titlovi.com username and password.
        After successful login cookie is stored in cache.
        """
        resp_cookies = addon_cache.get('titlovi_com_cookie')
        if not resp_cookies:
            login_params = dict(username=self.username, password=self.password)
            response = requests.get('{0}/login'.format(api_url), login_params)
            if response.status_code == requests.codes.ok:
                resp_cookies = response.cookies
                addon_cache.set('titlovi_com_cookie', resp_cookies, expiration=timedelta(hours=24))
                self.login_cookie = resp_cookies
                return True
            else:
                show_notification(script_name, u'Titlovi.com login error, try again')
                return False
        self.login_cookie = resp_cookies
        return True

    def handle_action(self):
        """
        Method used for calling other action methods depending on 'action' parameter.
        """

        if self.action == 'search':
            self.handle_search_action()
        elif self.action == 'manualsearch':
            self.handle_manual_search_action()
        elif self.action == 'download':
            self.handle_download_action()
        else:
            logger(u'Invalid action')
            show_notification(script_name, get_string(2103))

    def handle_search_action(self):
        """
        Method used for searching
        """
        logger('handling action: search')
    	
        try:
            current_video_name = player.getPlayingFile()
        except Exception as e:
            logger(e)
            show_notification(script_name, u'Video not playing!')
            return

        parsed_name = basename(current_video_name).rsplit('.', 1)
        if not parsed_name:
            show_notification(script_name, u'Invalid video name!')
            return

        parsed_name = parsed_name[0]

        request_params = dict(search_string=parsed_name, languages=self.params['languages'])
        try:
            response = requests.get(api_url, request_params)
            response_data = response.json()
        except Exception as e:
            logger(e)
            return
        
        listitem = xbmcgui.ListItem(label='English',
                                    label2='test_subtitle.en.srt'
                                    )
        url = "plugin://%s/?action=download" % script_id

        xbmcplugin.addDirectoryItem(handle=plugin_handle, url=url, listitem=listitem, isFolder=False)

    # TODO def handle_manual_search_action
    
    def handle_download_action(self):
        zip_file_location = '/home/tomislav/python_projects/kodi_titlovi_com/test_subtitle.zip'
        if not os.path.exists(zip_file_location) or not os.path.isfile(zip_file_location):
            show_notification(script_name, u'Subtitle file not found')
            return

        xbmc.sleep(500)
        xbmc.executebuiltin(('XBMC.Extract("%s","%s")' % (zip_file_location, temp_dir,)).encode('utf-8'), True)
        subtitle_file = xbmcvfs.listdir(zip_file_location)[1][0]
        subtitle_file = os.path.join(temp_dir, subtitle_file)
        if xbmcvfs.exists(subtitle_file):
            list_item = xbmcgui.ListItem(label=subtitle_file)
            xbmcplugin.addDirectoryItem(handle=plugin_handle, url=subtitle_file, listitem=list_item, isFolder=False)

"""
{'action': 'manualsearch', 'languages': 'English', 'searchstring': 'test', 'preferredlanguage': 'English'}
"""
params_dict = parse_qs(sys.argv[2])
logger(params_dict)
action_handler = ActionHandler(params_dict)
if action_handler.validate_params():
    is_user_loggedin = action_handler.user_login()
    if is_user_loggedin:
        action_handler.handle_action()

xbmcplugin.endOfDirectory(plugin_handle)
