#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import stat
import shutil
import re
import time
import struct
import zipfile
import lhafile
import operator
import threading
import hashlib
import subprocess
import StringIO
import io
import traceback
import datetime
import ctypes
import ctypes.util
import array
import unicodedata
import functools
import webbrowser
import math

if sys.platform == "win32":
    import win32api
    import win32con
    import importlib
    pythoncom = importlib.import_module("pythoncom")
    win32shell = importlib.import_module("win32com.shell.shell")
    import win32com.shell.shellcon

import wx
import wx.lib.agw.aui.tabart
import wx.lib.mixins.listctrl
import wx.richtext
import pygame
import pygame.image
from pygame.locals import KEYDOWN, KEYUP, MOUSEBUTTONDOWN, MOUSEBUTTONUP, USEREVENT

import cw


#-------------------------------------------------------------------------------
#　汎用クラス
#-------------------------------------------------------------------------------

class MusicInterface(object):
    def __init__(self, channel, mastervolume):
        self.channel = channel
        self.path = ""
        self.fpath = ""
        self.subvolume = 100
        self.loopcount = 0
        self.movie_scr = None
        self.mastervolume = mastervolume
        self._winmm = False
        self._bass = False
        self._movie = None
        self.inusecard = False

    def update_scale(self):
        if self._movie:
            self.movie_scr = pygame.Surface(cw.s(self._movie.get_size())).convert()
            rect = cw.s(pygame.Rect((0, 0), self._movie.get_size()))
            self._movie.set_display(self.movie_scr, rect)

    def play(self, path, updatepredata=True, restart=False, inusecard=False, subvolume=100, loopcount=0, fade=0):
        self._play(path, updatepredata, restart, inusecard, subvolume, loopcount, fade)

    def _play(self, path, updatepredata=True, restart=False, inusecard=False, subvolume=100, loopcount=0, fade=0):
        if threading.currentThread() <> cw.cwpy:
            cw.cwpy.exec_func(self._play, path, updatepredata, restart, inusecard, subvolume, loopcount, fade)
            return

        assert threading.currentThread() == cw.cwpy
        if cw.cwpy.ydata and cw.cwpy.is_playingscenario():
            cw.cwpy.ydata.changed()
        fpath = self.get_path(path, inusecard)
        self.path = path
        if not pygame.mixer.get_init() and not cw.bassplayer.is_alivablewithpath(path):
            return

        if cw.cwpy.rsrc:
            fpath = cw.cwpy.rsrc.get_filepath(fpath)

        if not os.path.isfile(fpath):
            self._stop(fade, stopfadeout=False, updatepredata=False)
        else:
            assert threading.currentThread() == cw.cwpy

            self.set_volume()
            if restart or self.fpath <> fpath:
                self._stop(fade, stopfadeout=False, updatepredata=False)
                self._winmm = False
                self._bass = False
                bgmtype = load_bgm(fpath)
                if bgmtype <> -1:
                    filesize = 0
                    if os.path.isfile(fpath):
                        try:
                            filesize = os.path.getsize(fpath)
                        except Exception:
                            cw.util.print_ex()

                    if bgmtype == 2:
                        volume = self._get_volumevalue(fpath) * subvolume / 100.0
                        try:
                            cw.bassplayer.play_bgm(fpath, volume, loopcount=loopcount, channel=self.channel, fade=fade)
                            self._bass = True
                        except Exception:
                            cw.util.print_ex()
                    elif bgmtype == 1:
                        if sys.platform == "win32":
                            name = "cwbgm_" + str(self.channel)
                            mciSendStringW = ctypes.windll.winmm.mciSendStringW
                            mciSendStringW(u'open "%s" alias %s' % (fpath, name), 0, 0, 0)
                            volume = int(cw.cwpy.setting.vol_bgm * 1000)
                            volume = volume * subvolume / 100
                            mciSendStringW(u"setaudio %s volume to %s" % (name, volume), 0, 0, 0)
                            mciSendStringW(u"play %s" % (name), 0, 0, 0)
                            self._winmm = True
                        elif cw.util.splitext(fpath)[1].lower() in (".mpg", ".mpeg"):
                            try:
                                if pygame.mixer.get_init():
                                    pygame.mixer.quit()
                                encoding = sys.getfilesystemencoding()
                                self._movie = pygame.movie.Movie(fpath.encode(encoding))
                                volume = self._get_volumevalue(fpath) * subvolume / 100.0
                                self._movie.set_volume(volume)
                                self.movie_scr = pygame.Surface(cw.s(self._movie.get_size())).convert()
                                rect = cw.s(pygame.Rect((0, 0), self._movie.get_size()))
                                self._movie.set_display(self.movie_scr, rect)
                                self._movie.play()
                            except Exception:
                                cw.util.print_ex()
                    elif filesize == 57 and cw.util.get_md5(fpath) == "d11be4c76fc63a6ba299c2f3bd3880b0":
                        # FIXME: reset.mid
                        # 繰り返し流すとハングアップ pygame 1.9.1
                        if pygame.mixer.get_init():
                            pygame.mixer.music.play(0)
                    elif filesize == 737 and cw.util.get_md5(fpath) == "41b0a6aaa8ffefa9ce6742e80e393075":
                        # FIXME: DefReset.mid
                        # 繰り返し流すとシステムが不安定になる pygame 1.9.1
                        if pygame.mixer.get_init():
                            pygame.mixer.music.play(0)
                    elif cw.util.splitext(fpath)[1].lower() == ".mp3":
                        # 互換動作: 1.28以前はMP3がループ再生されない
                        if pygame.mixer.get_init():
                            volume = self._get_volumevalue(fpath) * subvolume / 100.0
                            pygame.mixer.music.set_volume(volume)
                            if cw.cwpy.sct.lessthan("1.28", cw.cwpy.sdata.get_versionhint()):
                                pygame.mixer.music.play(0)
                            else:
                                pygame.mixer.music.play(loopcount-1)
                    elif pygame.mixer.get_init():
                        pygame.mixer.music.play(-1)
            else:
                if self.subvolume <> subvolume:
                    self.subvolume = subvolume
                    self.set_volume(fade=fade)
                if self._bass:
                    # ループ回数は常に設定する
                    cw.bassplayer.set_bgmloopcount(loopcount, channel=self.channel)

            self.fpath = fpath
            self.subvolume = subvolume
            self.loopcount = loopcount
            self.path = path

        if updatepredata and cw.cwpy.sdata and cw.cwpy.sdata.pre_battleareadata and cw.cwpy.sdata.pre_battleareadata[1][3] == self.channel:
            areaid, bgmpath, battlebgmpath = cw.cwpy.sdata.pre_battleareadata
            bgmpath = (path, subvolume, loopcount, self.channel)
            cw.cwpy.sdata.pre_battleareadata = (areaid, bgmpath, battlebgmpath)

    def stop(self, fade=0):
        if threading.currentThread() <> cw.cwpy:
            cw.cwpy.exec_func(self.stop, fade)
            return
        self._stop(fade=fade, stopfadeout=True, updatepredata=True)

    def _stop(self, fade, stopfadeout, updatepredata=True):
        if threading.currentThread() <> cw.cwpy:
            cw.cwpy.exec_func(self._stop, fade, stopfadeout)
            return

        assert threading.currentThread() == cw.cwpy

        if cw.bassplayer.is_alivablewithpath(self.path):
            # フェードアウト中のBGMも停止する必要があるため、
            # self._bass == Falseの時も停止処理を行う
            cw.bassplayer.stop_bgm(channel=self.channel, fade=fade, stopfadeout=stopfadeout)
            self._bass = False

        if self._winmm:
            name = "cwbgm_" + str(self.channel)
            mciSendStringW = ctypes.windll.winmm.mciSendStringW
            mciSendStringW(u"stop %s" % (name), 0, 0, 0)
            mciSendStringW(u"close %s" % (name), 0, 0, 0)
            self._winmm = False
        elif self._movie:
            assert self.movie_scr
            self._movie.stop()
            self._movie = None
            self.movie_scr = None
            cw.util.sdlmixer_init()
        elif pygame.mixer.get_init():
            if 0 < fade:
                pygame.mixer.music.fadeout(fade)
            else:
                pygame.mixer.music.stop()
        remove_soundtempfile("Bgm")
        self.fpath = ""
        self.path = ""
        # pygame.mixer.musicで読み込んだ音楽ファイルを解放する
        if cw.cwpy.rsrc:
            path = "DefReset"
            path = find_resource(join_paths(cw.cwpy.setting.skindir, "Bgm", path), cw.cwpy.rsrc.ext_bgm)
            load_bgm(path)

        if updatepredata and cw.cwpy.sdata and cw.cwpy.sdata.pre_battleareadata and cw.cwpy.sdata.pre_battleareadata[1][3] == self.channel:
            areaid, bgmpath, battlebgmpath = cw.cwpy.sdata.pre_battleareadata
            bgmpath = (u"", 100, 0, self.channel)
            cw.cwpy.sdata.pre_battleareadata = (areaid, bgmpath, battlebgmpath)

    def _get_volumevalue(self, fpath):
        if not cw.cwpy.setting.play_bgm:
            return 0

        ext = cw.util.splitext(fpath)[1].lower()

        if ext == ".mid" or ext == ".midi":
            volume = cw.cwpy.setting.vol_midi * cw.cwpy.setting.vol_bgm
        else:
            volume = cw.cwpy.setting.vol_bgm

        return volume * self.mastervolume / 100

    def set_volume(self, volume=None, fade=0):
        if threading.currentThread() <> cw.cwpy:
            cw.cwpy.exec_func(self.set_volume, volume)
            return

        if volume is None:
            volume = self._get_volumevalue(self.fpath)
        volume = volume * self.subvolume / 100.0

        assert threading.currentThread() == cw.cwpy
        if self._bass:
            cw.bassplayer.set_bgmvolume(volume, channel=self.channel, fade=fade)
        elif self._movie:
            self._movie.set_volume(volume)
        elif pygame.mixer.get_init():
            pygame.mixer.music.set_volume(volume)

    def set_mastervolume(self, volume):
        if threading.currentThread() <> cw.cwpy:
            cw.cwpy.exec_func(self.set_mastervolume, volume)
            return

        self.mastervolume = volume
        self.set_volume()

    def get_path(self, path, inusecard=False):
        if inusecard:
            path = cw.util.join_yadodir(path)
            self.inusecard = True
        else:
            inusepath = cw.util.get_inusecardmaterialpath(path, cw.M_MSC)
            if os.path.isfile(inusepath):
                path = inusepath
                self.inusecard = True
            else:
                path = get_materialpath(path, cw.M_MSC)
                self.inusecard = False

        return path

class SoundInterface(object):
    def __init__(self, sound=None, path=""):
        self._sound = sound
        self._path = path
        self.subvolume = 100
        self.channel = -1
        self._type = -1
        self.mastervolume = 0

    def get_path(self):
        return self._path

    def _play_before(self, from_scenario, channel, fade):
        if from_scenario:
            if cw.cwpy.lastsound_scenario[channel]:
                cw.cwpy.lastsound_scenario[channel]._stop(from_scenario, fade=fade, stopfadeout=False)
                cw.cwpy.lastsound_scenario[channel] = None
            cw.cwpy.lastsound_scenario[channel] = self
            return "Sound"
        else:
            if cw.cwpy.lastsound_system:
                cw.cwpy.lastsound_system._stop(from_scenario, fade=fade, stopfadeout=False)
                cw.cwpy.lastsound_system = None
            cw.cwpy.lastsound_system = self
            return "SystemSound"

    def play(self, from_scenario=False, subvolume=100, loopcount=1, channel=0, fade=0):
        self._type = -1
        self.mastervolume = cw.cwpy.music[0].mastervolume
        if self._sound and 0 <= channel and channel < cw.bassplayer.MAX_SOUND_CHANNELS:
            self.channel = channel
            self.subvolume = subvolume

            if cw.cwpy.setting.play_sound:
                volume = (cw.cwpy.setting.vol_sound * cw.cwpy.music[0].mastervolume) / 100.0 * subvolume / 100.0
            else:
                volume = 0

            if cw.bassplayer.is_alivablewithpath(self._path):
                if threading.currentThread() <> cw.cwpy:
                    cw.cwpy.exec_func(self.play, from_scenario, subvolume, loopcount, channel, fade)
                    return
                assert threading.currentThread() == cw.cwpy
                tempbasedir = self._play_before(from_scenario, channel, fade)
                try:
                    path = get_soundfilepath(tempbasedir, self._sound)
                    cw.bassplayer.play_sound(path, volume, from_scenario, loopcount=loopcount, channel=channel, fade=fade)
                    self._type = 0
                except Exception:
                    cw.util.print_ex()
            elif sys.platform == "win32" and isinstance(self._sound, (str, unicode)):
                if threading.currentThread() == cw.cwpy:
                    cw.cwpy.frame.exec_func(self.play, from_scenario, subvolume, loopcount, channel, fade)
                    return
                assert threading.currentThread() <> cw.cwpy
                tempbasedir = self._play_before(from_scenario, channel, fade)
                if from_scenario:
                    name = "cwsnd1_" + str(channel)
                else:
                    name = "cwsnd2"

                mciSendStringW = ctypes.windll.winmm.mciSendStringW
                path = get_soundfilepath(tempbasedir, self._sound)
                mciSendStringW(u'open "%s" alias %s' % (path, name), 0, 0, 0)
                volume = int(volume * 1000)
                mciSendStringW(u"setaudio %s volume to %s" % (name, volume), 0, 0, 0)
                mciSendStringW(u"play %s" % (name), 0, 0, 0)
                self._type = 1
            else:
                if threading.currentThread() <> cw.cwpy:
                    cw.cwpy.exec_func(self.play, from_scenario, subvolume, loopcount, channel, fade)
                    return
                assert threading.currentThread() == cw.cwpy
                tempbasedir = self._play_before(from_scenario, channel, fade)
                if pygame.mixer.get_init():
                    if from_scenario:
                        chan = pygame.mixer.Channel(channel+1)
                    else:
                        chan = pygame.mixer.Channel(0)

                    self._sound.set_volume(volume)
                    chan.play(self._sound, loopcount-1, fade_ms=fade)
                    self._type = 2

    def stop(self, from_scenario, fade=0):
        self._stop(from_scenario, fade=fade, stopfadeout=True)

    def _stop(self, from_scenario, fade, stopfadeout):
        self.mastervolume = 0
        if self._type <> -1 and self._sound and 0 <= self.channel and self.channel < cw.bassplayer.MAX_SOUND_CHANNELS:
            if from_scenario:
                tempbasedir = "Sound"
            else:
                tempbasedir = "SystemSound"

            if self._type == 0:
                if threading.currentThread() <> cw.cwpy:
                    cw.cwpy.exec_func(self._stop, from_scenario, fade, stopfadeout)
                    return
                assert threading.currentThread() == cw.cwpy
                try:
                    cw.bassplayer.stop_sound(from_scenario, channel=self.channel, fade=fade, stopfadeout=stopfadeout)
                    remove_soundtempfile(tempbasedir)
                except Exception:
                    cw.util.print_ex()
            elif self._type == 1:
                if threading.currentThread() == cw.cwpy:
                    cw.cwpy.frame.exec_func(self._stop, from_scenario, fade, stopfadeout)
                    return
                assert threading.currentThread() <> cw.cwpy
                if from_scenario:
                    name = "cwsnd1_" + str(self.channel)
                else:
                    name = "cwsnd2"

                mciSendStringW = ctypes.windll.winmm.mciSendStringW
                mciSendStringW(u"stop %s" % (name), 0, 0, 0)
                mciSendStringW(u"close %s" % (name), 0, 0, 0)
                remove_soundtempfile(tempbasedir)
            else:
                if threading.currentThread() <> cw.cwpy:
                    cw.cwpy.exec_func(self._stop, from_scenario, fade, stopfadeout)
                    return
                assert threading.currentThread() == cw.cwpy
                if pygame.mixer.get_init():
                    if from_scenario:
                        chan = pygame.mixer.Channel(self.channel+1)
                    else:
                        chan = pygame.mixer.Channel(0)

                    if 0 < fade:
                        chan.fadeout(fade)
                    else:
                        chan.stop()

    def _get_volumevalue(self, fpath):
        if not cw.cwpy.setting.play_sound:
            return 0

        ext = cw.util.splitext(fpath)[1].lower()

        if ext == ".mid" or ext == ".midi":
            volume = cw.cwpy.setting.vol_midi * cw.cwpy.setting.vol_sound
        else:
            volume = cw.cwpy.setting.vol_sound

        return volume * self.mastervolume / 100.0

    def set_mastervolume(self, from_scenario, volume):
        if threading.currentThread() <> cw.cwpy:
            cw.cwpy.exec_func(self.set_mastervolume, from_scenario, volume)
            return

        self.mastervolume = volume
        self.set_volume(from_scenario)

    def set_volume(self, from_scenario, volume=None):
        if threading.currentThread() <> cw.cwpy:
            cw.cwpy.exec_func(self.set_volume, from_scenario, volume)
            return
        if self._type == -1:
            return

        if volume is None:
            volume = self._get_volumevalue(self._path)
        volume = volume * self.subvolume / 100.0

        assert threading.currentThread() == cw.cwpy
        if self._type == 0:
            cw.bassplayer.set_soundvolume(volume, from_scenario, channel=self.channel, fade=0)
        elif self._type == 1:
            volume = int(volume * 1000)
            mciSendStringW = ctypes.windll.winmm.mciSendStringW
            if from_scenario:
                name = "cwsnd1_" + str(self.channel)
            else:
                name = "cwsnd2"
            mciSendStringW(u"setaudio %s volume to %s" % (name, volume), 0, 0, 0)
        elif self._type == 2:
            self._sound.set_volume(volume)

#-------------------------------------------------------------------------------
#　汎用関数
#-------------------------------------------------------------------------------

def init(size_noscale=None, title="", fullscreen=False, soundfonts=None, fullscreensize=(0, 0)):
    """pygame初期化。"""
    if sys.platform == "win32":
        # FIXME: SDLがWindowsの言語設定に勝手にUSキーボード設定を追加してしまうので
        #        キーボードレイアウトが増えていた場合に限り除去
        #        おそらくSDL2では発生しないので、更新した時には以下のコードを取り除けるはず
        active = win32api.GetKeyboardLayout(0)
        hkls = set()
        for hkl in win32api.GetKeyboardLayoutList():
            hkls.add(hkl)

        pygame.display.init()

        for hkl in win32api.GetKeyboardLayoutList():
            if not hkl in hkls:
                p = ctypes.c_void_p(hkl)
                ctypes.windll.user32.UnloadKeyboardLayout(p)
    else:
        pygame.display.init()

    pygame.font.init()
    #pygame.joystick.init()
    flags = 0
    size = cw.s(size_noscale)
    if fullscreen:
        scr_fullscreen = pygame.display.set_mode(fullscreensize, flags)
        scr = pygame.Surface(size).convert()
        scr_draw = scr
    else:
        scr_fullscreen = None
        scr = pygame.display.set_mode(cw.wins(size_noscale), flags)
        if cw.UP_WIN == cw.UP_SCR:
            scr_draw = scr
        else:
            scr_draw = pygame.Surface(size).convert()
    clock = pygame.time.Clock()

    if title:
        pygame.display.set_caption(title)

    pygame.event.set_blocked(None)
    pygame.event.set_allowed([KEYDOWN, KEYUP, MOUSEBUTTONDOWN, MOUSEBUTTONUP, USEREVENT])

    # BASS Audioを初期化(使用できない事もある)
    if soundfonts is None:
        soundfonts = [(cw.DEFAULT_SOUNDFONT, True)]
    soundfonts = [sfont[0] for sfont in soundfonts if sfont[1]]
    if not cw.bassplayer.init_bass(soundfonts):
        # BASS Audioが使用できない場合に限りpygame.mixerを初期化
        # (BASSとpygame.mixerを同時に初期化した場合、
        # 環境によっては音が出なくなるなどの不具合が出る)
        sdlmixer_init()

    return scr, scr_draw, scr_fullscreen, clock

def sdlmixer_init():
    try:
        pygame.mixer.init(44100, -16, 2, 1024)
        pygame.mixer.set_num_channels(2)
    except:
        cw.util.print_ex(file=sys.stderr)

def convert_maskpos(maskpos, width, height):
    """maskposが座標ではなくキーワード"center"または"right"
    であった場合、それぞれ画像の中央、右上の座標を返す。
    """
    if isinstance(maskpos, str):
        if maskpos == "center":
            maskpos = (width / 2, height / 2)
        elif maskpos == "right":
            maskpos = (width - 1, 0)
        else:
            raise Exception("Invalid maskpos: %s" % (maskpos))
    return maskpos


def get_scaledimagepaths(path, can_loaded_scaledimage):
    """(スケーリングされたファイル名, スケール)のlistを返す。
    listには1倍スケールを示す(path, 1)が必ず含まれる。
    """
    seq = [(path, 1)]
    if can_loaded_scaledimage:
        spext = os.path.splitext(path)
        for scale in cw.SCALE_LIST:
            fname = u"%s.x%d%s" % (spext[0], scale, spext[1])
            seq.append((fname, scale))
    return seq

def copy_scaledimagepaths(frompath, topath, can_loaded_scaledimage):
    """frompathをtopathへコピーする。
    その後、ファイル名に".xN"をつけたイメージを探し、
    実際に存在するファイルであればコピーする。
    """
    shutil.copy2(frompath, topath)
    fromspext = os.path.splitext(frompath)
    if can_loaded_scaledimage and fromspext[1].lower() in cw.EXTS_IMG:
        tospext = os.path.splitext(topath)
        for scale in cw.SCALE_LIST:
            fname = u"%s.x%d%s" % (fromspext[0], scale, fromspext[1])
            fname = cw.cwpy.rsrc.get_filepath(fname)
            if os.path.isfile(fname):
                fname2 = u"%s.x%d%s" % (tospext[0], scale, tospext[1])
                shutil.copy2(fname, fname2)

def find_scaledimagepath(path, up_scr, can_loaded_scaledimage, noscale):
    """ファイル名に".xN"をつけたイメージを探して(ファイル名, スケール値)を返す。
    例えば"file.bmp"に対する"file.x2.bmp"を探す。
    """
    scale = 1
    path = cw.util.join_paths(path)
    if not noscale and (can_loaded_scaledimage or path.startswith(cw.util.join_paths(cw.tempdir, u"ScenarioLog/TempFile/"))):
        scale =  int(math.pow(2, int(math.log(up_scr, 2))))
        spext = os.path.splitext(path)
        while 2 <= scale:
            fname = u"%s.x%d%s" % (spext[0], scale, spext[1])
            fname = cw.cwpy.rsrc.get_filepath(fname)
            if os.path.isfile(fname):
                path = fname
                break
            scale /= 2
    return path, scale


def find_noscalepath(path):
    """pathが"file.x2.bmp"のようなスケール付きイメージのものであれば
    ".xN"の部分を取り除いて返す。
    ただし取り除いた後のファイルが実在しない場合はそのまま返す。
    """
    scales = u"|".join(map(lambda s: str(s), cw.SCALE_LIST))
    exts = u"|".join(map(lambda s: s.replace(".", "\\."), cw.EXTS_IMG))
    result = re.match(u"\\A(.+)\.x(%s)(%s)\\Z" % (scales, exts), path, re.IGNORECASE)
    if result:
        fpath = result.group(1) + result.group(3)
        if os.path.isfile(fpath):
            path = fpath
    return path


def load_image(path, mask=False, maskpos=(0, 0), f=None, retry=True, isback=False, can_loaded_scaledimage=True,
               noscale=False, up_scr=None):
    """pygame.Surface(読み込めなかった場合はNone)を返す。
    path: 画像ファイルのパス。
    mask: True時、(0,0)のカラーを透過色に設定する。透過画像の場合は無視される。
    """
    #assert threading.currentThread() == cw.cwpy
    if cw.cwpy.rsrc:
        path = cw.cwpy.rsrc.get_filepath(path)

    if up_scr is None:
        up_scr = cw.UP_SCR
    path, up_scr = find_scaledimagepath(path, up_scr, can_loaded_scaledimage, noscale)

    bmpdepth = 0
    try:
        if f:
            try:
                pos = f.tell()
                ispng = get_imageext(f.read(16)) == ".png"
                f.seek(pos)
                image = pygame.image.load(f, "")
            except:
                image = pygame.image.load(f, path)
        elif cw.binary.image.path_is_code(path):
            data = cw.binary.image.code_to_data(path)
            ext = get_imageext(data)
            ispng = ext == ".png"
            if ext == ".bmp":
                data = cw.image.patch_rle4bitmap(data)
                bmpdepth = cw.image.get_bmpdepth(data)
            with io.BytesIO(data) as f2:
                image = pygame.image.load(f2)
                f2.close()
            if ext == ".bmp":
                image = cw.imageretouch.patch_alphadata(image)
        else:
            if not os.path.isfile(path):
                return pygame.Surface((0, 0)).convert()
            ext = os.path.splitext(path)[1].lower()
            ispng = ext == ".png"
            if ext == ".bmp":
                with open(path, "rb") as f2:
                    data = f2.read()
                    f2.close()
                bmpdepth = cw.image.get_bmpdepth(data)
                data = cw.image.patch_rle4bitmap(data)
                with io.BytesIO(data) as f2:
                    image = pygame.image.load(f2)
                    f2.close()
                if ext == ".bmp":
                    image = cw.imageretouch.patch_alphadata(image)
            else:
                with io.BufferedReader(io.FileIO(path)) as f2:
                    image = pygame.image.load(f2)
                    f2.close()
    except:
        print_ex()
        #print u"画像が読み込めません(load_image)。リトライします", path
        if retry:
            try:
                if f:
                    f.seek(0)
                    data = f.read()
                elif cw.binary.image.path_is_code(path):
                    data = cw.binary.image.code_to_data(path)
                else:
                    if not os.path.isfile(path):
                        return pygame.Surface((0, 0)).convert()
                    with open(path, "rb") as f2:
                        data = f2.read()
                        f2.close()
                bmpdepth = cw.image.get_bmpdepth(data)
                data, _ok = cw.image.fix_cwnext16bitbitmap(data)
                with io.BytesIO(data) as f2:
                    r = load_image(path, mask, maskpos, f2, False, isback=isback, can_loaded_scaledimage=can_loaded_scaledimage,
                                   noscale=noscale)
                    f2.close()
                return r
            except:
                print_ex()
                #print u"画像が読み込めません(リトライ後)", path
        return pygame.Surface((0, 0)).convert()

    # アルファチャンネルを持った透過画像を読み込んだ場合は
    # SRCALPHA(0x00010000)のフラグがONになっている
    if image.get_flags() & pygame.locals.SRCALPHA:
        image = image.convert_alpha()
    else:
        imageb = image
        image = image.convert()

        # カード画像がPNGの場合はマスクカラーを無視する(CardWirth 1.50の実装)
        if image.get_colorkey() and ispng and not isback:
            image.set_colorkey(None)

        # GIFなどアルファチャンネルを持たない透過画像を読み込んだ場合は
        # すでにマスクカラーが指定されているので注意
        if mask and image.get_colorkey():
            # 255色GIFなどでパレットに存在しない色が
            # マスク色に設定されている事があるので、
            # その場合は通常通り左上の色をマスク色とする
            # 将来、もしこの処理の結果問題が起きた場合は
            # このif文以降の処理を削除する必要がある
            if imageb.get_bitsize() <= 8:
                mask = image.get_masks()
                maskok = False
                for pixel in imageb.get_palette():
                    if pixel == mask:
                        maskok = True
                        break
                if not maskok:
                    maskpos = convert_maskpos(maskpos, image.get_width(), image.get_height())
                    image.set_colorkey(image.get_at(maskpos), pygame.locals.RLEACCEL)
        elif mask and not image.get_colorkey():
            maskpos = convert_maskpos(maskpos, image.get_width(), image.get_height())
            image.set_colorkey(image.get_at(maskpos), pygame.locals.RLEACCEL)

    if bmpdepth == 1 and mask and not isback or up_scr <> 1:
        image = Depth1Surface(image, up_scr, bmpdepth)
    return image

class Depth1Surface(pygame.Surface):
    def __init__(self, surface, scr_scale, bmpdepth=24):
        pygame.Surface.__init__(self, surface.get_size(), surface.get_flags(), surface.get_bitsize(), surface.get_masks())
        self.blit(surface, (0, 0), special_flags=pygame.locals.BLEND_RGBA_ADD)
        colorkey = surface.get_colorkey()
        self.set_colorkey(colorkey, pygame.locals.RLEACCEL)
        self.bmpdepthis1 = surface.bmpdepthis1 if hasattr(surface, "bmpdepthis1") else (bmpdepth == 1)
        self.scr_scale = scr_scale

    def copy(self):
        bmp = Depth1Surface(pygame.Surface.copy(self), self.scr_scale)
        bmp.bmpdepthis1 = self.bmpdepthis1
        return bmp

def put_number(image, num):
    """アイコンサイズの画像imageの上に
    numの値を表示する。
    """
    image = image.convert_alpha()
    s = str(num)
    if len(s) == 1:
        font = cw.cwpy.rsrc.fonts["statusimg1"]
    elif len(s) == 2:
        font = cw.cwpy.rsrc.fonts["statusimg2"]
    else:
        font = cw.cwpy.rsrc.fonts["statusimg3"]
    h = font.get_height()
    w = (h+1) / 2
    subimg = pygame.Surface((len(s)*w, h)).convert_alpha()
    subimg.fill((0, 0, 0, 0))
    x = image.get_width() - subimg.get_width() - cw.s(1)
    y = image.get_height() - subimg.get_height()
    pos = (x, y)
    for i, c in enumerate(s):
        cimg = font.render(c, 2 <= cw.UP_SCR, (0, 0, 0))
        image.blit(cimg, (pos[0]+1 + i*w, pos[1]+1))
        image.blit(cimg, (pos[0]+1 + i*w, pos[1]-1))
        image.blit(cimg, (pos[0]-1 + i*w, pos[1]+1))
        image.blit(cimg, (pos[0]-1 + i*w, pos[1]-1))
        image.blit(cimg, (pos[0]+1 + i*w, pos[1]))
        image.blit(cimg, (pos[0]-1 + i*w, pos[1]))
        image.blit(cimg, (pos[0] + i*w, pos[1]+1))
        image.blit(cimg, (pos[0] + i*w, pos[1]-1))
        cimg = font.render(c, 2 <= cw.UP_SCR, (255, 255, 255))
        image.blit(cimg, (pos[0] + i*w, pos[1]))
    return image

def get_imageext(b):
    """dataが画像であれば対応する拡張子を返す。"""
    if 22 < len(b) and 'B' == b[0] and 'M' == b[1]:
        return ".bmp"
    if 25 <= len(b) and 0x89 == ord(b[0]) and 'P' == b[1] and 'N' == b[2] and 'G' == b[3]:
        return ".png"
    if 10 <= len(b) and 'G' == b[0] and 'I' == b[1] and 'F' == b[2]:
        return ".gif"
    if 6 <= len(b) and 0xFF == ord(b[0]) and 0xD8 == ord(b[1]):
        return ".jpg"
    if 10 <= len(b):
        if 'M' == b[0] and 'M' == b[1] and 42 == ord(b[3]):
            return ".tiff"
        elif 'I' == b[0] and 'I' == b[1] and 42 == ord(b[2]):
            return ".tiff"
    return ""

def get_facepaths(sexcoupon, agecoupon, adddefaults=True):
    """sexとageに対応したFaceディレクトリ内の画像パスを辞書で返す。
    辞書の内容は、(ソートキー, ディレクトリ, ディレクトリ表示名)をキーにした
    当該ディレクトリ内のファイルパスのlistとなる。
    sexcoupon: 性別クーポン。
    agecoupon: 年代クーポン。
    adddefaults: 1件もなかった場合、Resource/Image/Cardにある
                 FATHERまたはMOTHERを使用する。
    """
    imgpaths = {}

    sex = ""
    for f in cw.cwpy.setting.sexes:
        if sexcoupon == u"＿" + f.name:
            sex = f.subname

    age = ""
    for f in cw.cwpy.setting.periods:
        if agecoupon == u"＿" + f.name:
            age = f.abbr

    dpaths = [] # (実際のパス, 表示するパス)
    facedir1 = cw.util.join_paths(cw.cwpy.skindir, u"Face") # スキン付属
    facedir2 = u"Data/Face" # 全スキン共通

    for i, facedir in enumerate((facedir1, facedir2)):
        def add(weight, dpath1):
            dpath = join_paths(facedir, dpath1)
            if i == 0:
                name = cw.cwpy.setting.skinname
            else:
                name = cw.cwpy.msgs["common"]
            dpaths.append((i * 10 + weight, u"<%s> %s" % (name, dpath1), dpath))
        # 性別・年代限定
        if sex and age:
            add(0, sex + u"-" + age)
        # 性別限定
        if sex:
            add(1, sex)
        # 年代限定
        if age:
            add(2, u"Common-" + age)
        # 汎用
        add(3, u"Common")

    passed = set()
    _get_facepaths(facedir, imgpaths, dpaths, passed)
    if not imgpaths and adddefaults:
        seq = []
        dpath = join_paths(cw.cwpy.skindir, u"Resource/Image/Card")
        for sex in cw.cwpy.setting.sexes:
            if u"＿" + sex.name == sexcoupon:
                if sex.father:
                    fpath = join_paths(dpath, "FATHER")
                    fpath = find_resource(fpath, cw.M_IMG)
                    seq.append(fpath)
                if sex.mother:
                    fpath = join_paths(dpath, "MOTHER")
                    fpath = find_resource(fpath, cw.M_IMG)
                    seq.append(fpath)
                break
        if seq:
            imgpaths[(dpath, u"Resource/Image/Card")] = seq
    return imgpaths

def _get_facepaths(facedir, imgpaths, dpaths, passed):
    for sortkey, showdpath, dpath in dpaths:
        if not os.path.isdir(dpath):
            continue
        abs = os.path.abspath(dpath)
        abs = os.path.normpath(abs)
        abs = os.path.normcase(abs)
        if abs in passed:
            continue
        passed.add(abs)

        dpaths2 = [][:]
        seq = []
        scales = u"|".join(map(lambda s: str(s), cw.SCALE_LIST))
        re_xn = re.compile(u"\\A.+\.x(%s)\\Z" % (scales), re.IGNORECASE)
        for fname in os.listdir(dpath):
            path1 = join_paths(dpath, fname)
            path = get_linktarget(path1)
            if os.path.isfile(path):
                spext = os.path.splitext(path)
                ext = spext[1].lower()
                if ext in cw.EXTS_IMG and not re_xn.match(spext[0]):
                    seq.append(path)
            elif os.path.isdir(path):
                showpath = join_paths(showdpath, fname)
                if sys.platform == "win32" and path1 <> path and showpath.lower().endswith(".lnk"):
                    showpath = os.path.splitext(showpath)[0]
                dpaths2.append((sortkey, showpath, path))

        if seq:
            p = join_paths(relpath(dpath, facedir))
            if p.startswith("../"):
                p = dpath
            imgpaths[(sortkey, showdpath, join_paths(p))] = seq
        if dpaths2:
            _get_facepaths(facedir, imgpaths, dpaths2, passed)

def load_bgm(path):
    """Pathの音楽ファイルをBGMとして読み込む。
    リピートして鳴らす場合は、cw.audio.MusicInterface参照。
    pygame.mixer.music.load()が成功した場合は0、
    winmm.dllを利用して再生する場合は1(Windowsのみ)、
    bass.dllを利用して再生する場合は2、
    失敗した場合は-1を返す。
    path: 音楽ファイルのパス。
    """
    if threading.currentThread() <> cw.cwpy:
        raise Exception()

    if cw.cwpy.rsrc:
        path = cw.cwpy.rsrc.get_filepath(path)

    if not os.path.isfile(path) or (not pygame.mixer.get_init() and not cw.bassplayer.is_alivablewithpath(path)):
        return

    if cw.util.splitext(path)[1].lower() in (".mpg", ".mpeg"):
        return 1

    if cw.bassplayer.is_alivablewithpath(path):
        return 2

    if not pygame.mixer.get_init():
        return -1

    path = get_soundfilepath("Bgm", path)

    try:
        assert threading.currentThread() == cw.cwpy
        # ファイルパスを渡して読込
        encoding = sys.getfilesystemencoding()
        pygame.mixer.music.load(path.encode(encoding))
        return 0
    except Exception:
        cw.util.print_ex()
        try:
            # ストリームからの読込を試みる
            f = io.BufferedReader(io.FileIO(path))
            pygame.mixer.music.load(f)
            return 0
        except Exception:
            cw.util.print_ex()
            print u"BGMが読み込めません", path
            return -1

def load_sound(path):
    """効果音ファイルを読み込み、SoundInterfaceを返す。
    読み込めなかった場合は、無音で再生するSoundInterfaceを返す。
    path: 効果音ファイルのパス。
    """
    if threading.currentThread() <> cw.cwpy:
        raise Exception()

    if cw.cwpy.rsrc:
        path = cw.cwpy.rsrc.get_filepath(path)

    if not os.path.isfile(path) or (not pygame.mixer.get_init() and not cw.bassplayer.is_alivablewithpath(path)):
        return SoundInterface()

    if cw.cwpy.is_playingscenario() and path in cw.cwpy.sdata.resource_cache:
        return cw.cwpy.sdata.resource_cache[path]

    try:
        assert threading.currentThread() == cw.cwpy
        if cw.bassplayer.is_alivablewithpath(path):
            # BASSが使用できる場合
            sound = SoundInterface(path, path)
        elif sys.platform == "win32" and (path.lower().endswith(".wav") or\
                                        path.lower().endswith(".mp3")):
            # WinMMを使用する事でSDL_mixerの問題を避ける
            # FIXME: mp3効果音をWindows環境でしか再生できない
            sound = SoundInterface(path, path)
        elif pygame.mixer.get_init():
            with open(path, "rb") as f:
                sound = pygame.mixer.Sound(f)
                f.close()
            sound = SoundInterface(sound, path)
        else:
            return SoundInterface()
    except:
        print u"サウンドが読み込めません", path
        return SoundInterface()

    if cw.cwpy.is_playingscenario():
        cw.cwpy.sdata.resource_cache[path] = sound

    return sound

def get_soundfilepath(basedir, path):
    """宿のフォルダにある場合は問題が出るため、
    再生用のコピーを生成する。
    """
    if path and cw.cwpy.ydata and (path.startswith(cw.cwpy.ydata.yadodir) or\
                                   path.startswith(cw.cwpy.ydata.tempdir)):
        dpath = join_paths(cw.tempdir, u"Playing", basedir)
        fpath = os.path.basename(path)
        fpath = join_paths(dpath, fpath)
        fpath = cw.binary.util.check_duplicate(fpath)
        if not os.path.isdir(dpath):
            os.makedirs(dpath)
        shutil.copyfile(path, fpath)
        path = fpath
    return path

def remove_soundtempfile(basedir):
    """再生用のコピーを削除する。
    """
    dpath = join_paths(cw.tempdir, u"Playing", basedir)
    if os.path.isdir(dpath):
        remove(dpath)
        if not os.listdir(join_paths(cw.tempdir, u"Playing")):
            remove(dpath)

def _sorted_by_attr_impl(d, seq, *attr):
    if attr:
        get = operator.attrgetter(*attr)
    else:
        get = lambda a: a
    re_num = re.compile(u"( *[0-9]+ *)| +")
    str_table = {}

    class LogicalStr(object):
        def __init__(self, s):
            self.seq = []
            if not s:
                return
            pos = 0
            self.s = s
            while s <> u"":
                m = re_num.search(s, pos=pos)
                if m is None:
                    self.seq.append(s[pos:].lower())
                    break
                si = m.start()
                ei = m.end()
                self.seq.append(s[pos:si].lower())
                ss = s[si:ei]
                if ss.isspace():
                    self.seq.append((0, ss))
                else:
                    self.seq.append((int(ss), ss))
                pos = ei

        def __cmp__(self, other):
            r = cmp(self.seq, other.seq)
            if r:
                return r
            return cmp(self.s, other.s)

    def logical_cmp_str(a, b):
        if not (isinstance(a, (str, unicode)) and isinstance(b, (str, unicode))):
            return cmp(a, b)
        if a in str_table:
            al = str_table[a]
        else:
            al = LogicalStr(a)
            str_table[a] = al
        if b in str_table:
            bl = str_table[b]
        else:
            bl = LogicalStr(b)
            str_table[b] = bl
        return cmp(al, bl)

    def logical_cmp_impl(a, b):
        if (isinstance(a, tuple) and isinstance(b, tuple)) or\
                (isinstance(a, list) and isinstance(b, list)):
            r = 0
            for i in xrange(max(len(a), len(b))):
                if len(a) <= i:
                    return -1
                if len(b) <= i:
                    return 1
                aval = a[i]
                bval = b[i]
                r = logical_cmp_impl(aval, bval)
                if r <> 0:
                    break
            return r
        else:
            r = logical_cmp_str(a, b)
            return r

    def logical_cmp(aobj, bobj):
        a = get(aobj)
        b = get(bobj)
        return logical_cmp_impl(a, b)

    if d:
        seq.sort(key=functools.cmp_to_key(logical_cmp))
        return seq
    else:
        return sorted(seq, key=functools.cmp_to_key(logical_cmp))

def sorted_by_attr(seq, *attr):
    """非破壊的にオブジェクトの属性でソートする。
    seq: リスト
    attr: 属性名
    """
    return _sorted_by_attr_impl(False, seq, *attr)

def sort_by_attr(seq, *attr):
    """破壊的にオブジェクトの属性でソートする。
    seq: リスト
    attr: 属性名
    """
    return _sorted_by_attr_impl(True, seq, *attr)

assert sort_by_attr(["a1234b", "a12b", "a1234b"]) == ["a12b", "a1234b", "a1234b"]
assert sort_by_attr(["a12b", "a1234b", "a1b", "a9b", "a01234b", "a1234b", "a-."]) == ["a1b", "a9b", "a12b", "a01234b", "a1234b", "a1234b", "a-."]
assert sort_by_attr([(1, "a"), None, (0, "b"), (0, "c")]) == [None, (0, "b"), (0, "c"), (1, "a")]

def new_order(seq, mode=1):
    """order属性を持つアイテムのlistを
    走査して新しいorderを返す。
    必要であれば、seq内のorderを振り直す。
    mode: 0=最大order。1=最小order。orderの振り直しが発生する
    """
    if mode == 0:
        order = -1
        for item in seq:
            order = max(item.order, order)
        return order + 1
    else:
        for item in seq:
            item.order += 1
        return 0

def join_paths(*paths):
    """パス結合。ディレクトリの区切り文字はプラットホームに関わらず"/"固定。
    セキュリティ上の問題を避けるため、あえて絶対パスは取り扱わない。
    *paths: パス結合する文字列
    """
    return "/".join(filter(lambda a: a, paths)).replace("\\", "/").rstrip("/")

# FIXME: パスによって以下のような警告が標準エラー出力に出るようだが、詳細が分からない。
#        ***\ntpath.py:533: UnicodeWarning: Unicode unequal comparison failed to convert both arguments to Unicode - interpreting them as being unequal
#        おそらく実際的な問題は発生しないので、とりあえず警告を無効化する。
import warnings
warnings.filterwarnings("ignore", category=UnicodeWarning)

def relpath(path, start):
    if len(start) < len(path) and path.startswith(start):
        path2 = path[len(start):]
        if path2[0] == '/' or (sys.platform == "win32" and path2[0] == '\\'):
            return path2[1:]
    try:
        return os.path.relpath(path, start)
    except:
        return path
assert relpath("Data/abc", "Data") == "abc"
assert relpath("Data/abc/def", "Data").replace("\\", "/") == "abc/def"
assert relpath("Data/abc/def", "Data/abc/").replace("\\", "/") == "def"
assert relpath("Data/abc/def", "Data/abc") == os.path.relpath("Data/abc/def", "Data/abc")
assert relpath("Data/abc/def", "..").replace("\\", "/") == os.path.relpath("Data/abc/def", "..").replace("\\", "/")
assert relpath(".", "..").replace("\\", "/") == os.path.relpath(".", "..").replace("\\", "/")
assert relpath("/a", "..").replace("\\", "/") == os.path.relpath("/a", "..").replace("\\", "/")
assert relpath("a", "../bcde").replace("\\", "/") == os.path.relpath("a", "../bcde").replace("\\", "/")
assert relpath("../a", "../bcde").replace("\\", "/") == os.path.relpath("../a", "../bcde").replace("\\", "/")
assert relpath("../a", "../").replace("\\", "/") == os.path.relpath("../a", "../").replace("\\", "/")

def splitext(p):
    """パスの拡張子以外の部分と拡張子部分の分割。
    os.path.splitext()との違いは、".ext"のような
    拡張子部分だけのパスの時、(".ext", "")ではなく
    ("", ".ext")を返す事である。
    """
    p = os.path.splitext(p)
    if p[0].startswith(".") and not p[1]:
        return (p[1], p[0])
    return p

def str2bool(s):
    """特定の文字列をbool値にして返す。
    s: bool値に変換する文字列(true, false, 1, 0など)。
    """
    if isinstance(s, bool):
        return s
    else:
        s = s.lower()

        if s == "true":
            return True
        elif s == "false":
            return False
        elif s == "1":
            return True
        elif s == "0":
            return False
        else:
            raise ValueError("%s is incorrect value!" % (s))

def numwrap(n, nmin, nmax):
    """最小値、最大値の範囲内でnの値を返す。
    n: 範囲内で調整される値。
    nmin: 最小値。
    nmax: 最大値。
    """
    if n < nmin:
        n = nmin
    elif n > nmax:
        n = nmax

    return n

def div_vocation(value):
    """能力判定のために能力値を2で割る。
    0以上の場合とマイナス値の場合で式が異なる。
    """
    if value < 0:
        return (value+2) // 2
    else:
        return (value+1) // 2

def get_truetypefontname(path):
    """引数のTrueTypeFontファイルを読み込んで、フォントネームを返す。
    ref http://mail.python.org/pipermail/python-list/2008-September/508476.html
    path: TrueTypeFontファイルのパス。
    """
    #customize path
    with open(path, "rb") as f:

        #header
        shead= struct.Struct( ">IHHHH" )
        fhead= f.read( shead.size )
        dhead= shead.unpack_from( fhead, 0 )

        #font directory
        stable= struct.Struct( ">4sIII" )
        ftable= f.read( stable.size* dhead[ 1 ] )
        for i in xrange( dhead[1] ): #directory records
            dtable= stable.unpack_from(
                    ftable, i* stable.size )
            if dtable[0]== "name": break
        assert dtable[0]== "name"

        #name table
        f.seek( dtable[2] ) #at offset
        fnametable= f.read( dtable[3] ) #length
        snamehead= struct.Struct( ">HHH" ) #name table head
        dnamehead= snamehead.unpack_from( fnametable, 0 )

        sname= struct.Struct( ">HHHHHH" )
        fontname = ""

        for i in xrange( dnamehead[1] ): #name table records
            dname= sname.unpack_from(fnametable, snamehead.size+ i* sname.size )

            if dname[3]== 4: #key == 4: "full name of font"
                s= struct.unpack_from(
                        '%is'% dname[4], fnametable,
                        dnamehead[2]+ dname[5] )[0]
                if dname[:3] == (1, 0, 0):
                    fontname = s
                elif dname[:3] == (3, 1, 1033):
                    s = s.split("\x00")
                    fontname = "".join(s)
        f.close()

    return fontname

def get_md5(path):
    """MD5を使ったハッシュ値を返す。
    path: ハッシュ値を求めるファイルのパス。
    """
    m = hashlib.md5()
    with open(path, "rb") as f:

        while True:
            data = f.read(32768)

            if not data:
                break

            m.update(data)
        f.close()

    return m.hexdigest()

def number_normalization(value, fromvalue, tovalue):
    """数値を範囲内の値に正規化する。
    value: 正規化対象の数値。
    fromvalue: 範囲の最小値。
    tovalue: 範囲の最大値+1。
    """
    if 0 == tovalue:
        return value
    if tovalue <= value or value < fromvalue:
        value -= (value // tovalue) * tovalue
    if value < fromvalue:
        value += tovalue
    return value

def print_ex(file=None):
    """例外の内容を標準出力に書き足す。
    """
    if file is None:
        file = sys.stdout
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=file)
    file.write("\n")
    return

def screenshot_title(titledic):
    """スクリーンショットタイトルの書き出し。
    """
    title = format_title(cw.cwpy.setting.ssinfoformat, titledic)
    return title

def screenshot_header(title, w):
    """スクリーンショット情報の書き出し。
    """
    fore = cw.cwpy.setting.ssinfofontcolor
    font = cw.cwpy.rsrc.fonts["screenshot"]
    fh = font.size("#")[1]
    lh = fh + 2
    subimg = font.render(title, True, fore)
    swmax = w - cw.s(10)*2
    if swmax < subimg.get_width():
        size = (swmax, subimg.get_height())
        subimg = cw.image.smoothscale(subimg, size)
    return subimg, fh, lh

def screenshot():
    """スクリーンショットをファイルへ書き出す。
    """
    cw.cwpy.play_sound("screenshot")
    titledic, titledicfn = cw.cwpy.get_titledic(with_datetime=True, for_fname=True)
    filename = create_screenshotfilename(titledicfn)
    try:
        dpath = os.path.dirname(filename)
        if os.path.isdir(dpath):
            fpath = dupcheck_plus(filename, yado=False)
        else:
            os.makedirs(dpath)
        bmp, y = create_screenshot(titledic)
        encoding = sys.getfilesystemencoding()
        pygame.image.save(bmp, filename.encode(encoding))
    except:
        s = u"スクリーンショットの保存に失敗しました。\n%s" % (filename)
        cw.cwpy.call_modaldlg("ERROR", text=s)

def create_screenshotfilename(titledic):
    """スクリーンショット用のファイルパスを作成する。
    """
    fpath = format_title(cw.cwpy.setting.ssfnameformat, titledic)
    if not os.path.splitext(fpath)[1].lower() in cw.EXTS_IMG:
        fpath += ".png"
    return fpath

def create_screenshot(titledic):
    """スクリーンショットを作成する。
    """
    title = screenshot_title(titledic)
    scr = pygame.Surface(cw.cwpy.scr_draw.get_size()).convert()
    cw.cwpy.draw_to(scr, False)
    if title:
        back = cw.cwpy.setting.ssinfobackcolor
        w = cw.s(cw.SIZE_GAME[0])
        subimg, fh, lh = screenshot_header(title, w)
        h = cw.s(cw.SIZE_GAME[1]) + lh
        bmp = pygame.Surface((w, h)).convert()
        bmp.fill(back, rect=pygame.Rect(cw.s(0), cw.s(0), w, lh))
        bmp.blit(scr, (cw.s(0), lh))
        y = (lh - fh) / 2
        bmp.blit(subimg, (cw.s(10), y))
        y = lh
    else:
        bmp = scr
        y = cw.s(0)

    return bmp, y

def card_screenshot():
    """ パーティー所持カードのスクリーンショットをファイルへ書き出す。
    """
    if cw.cwpy.ydata:
        if cw.cwpy.ydata.party:
            cw.cwpy.play_sound("screenshot")
            titledic, titledicfn = cw.cwpy.get_titledic(with_datetime=True, for_fname=True)
            filename = create_cardscreenshotfilename(titledicfn)
            try:
                dpath = os.path.dirname(filename)
                if os.path.isdir(dpath):
                    fpath = dupcheck_plus(filename, yado=False)
                else:
                    os.makedirs(dpath)
                bmp = create_cardscreenshot(titledic)
                encoding = sys.getfilesystemencoding()
                pygame.image.save(bmp, filename.encode(encoding))
            except:
                s = u"スクリーンショットの保存に失敗しました。\n%s" % (filename)
                cw.cwpy.call_modaldlg("ERROR", text=s)
            return True
    return False

def create_cardscreenshotfilename(titledic):
    """パーティー所持カードスクリーンショット用のファイルパスを作成する。
    """
    fpath = format_title(cw.cwpy.setting.cardssfnameformat, titledic)
    if not os.path.splitext(fpath)[1].lower() in cw.EXTS_IMG:
        fpath += ".png"
    return fpath

def create_cardscreenshot(titledic):
    """パーティー所持カードスクリーンショットを作成する。
    """

    pcards = [i for i in cw.cwpy.get_pcards()]
    if pcards:
        max_card = [2, 2, 2]
        margin = 2
        # 背景のタイル色
        # タイトルバーに馴染む色にする
        back = [map(lambda n: min(255, max(0, n / 2 + 88)), cw.cwpy.setting.ssinfobackcolor),
                map(lambda n: min(255, max(0, n / 2 + 40)), cw.cwpy.setting.ssinfobackcolor)]

        # カード数によってタイルのサイズを決定
        for pcard in pcards:
            for index in (cw.POCKET_SKILL, cw.POCKET_ITEM, cw.POCKET_BEAST):
                max_card[index] = max(len(pcard.cardpocket[index]), max_card[index])

        w = cw.s(95 + 80 * sum(max_card) + margin * (5 + sum(max_card)))
        h = cw.s((130 + 2 * margin) * len(pcards))
        title = screenshot_title(titledic)
        if title:
            subimg, fh, lh = screenshot_header(title, w)
            h += lh
        bmp = pygame.Surface((w, h)).convert()
        bmp.fill(cw.cwpy.setting.ssinfobackcolor, rect=pygame.Rect(cw.s(0), cw.s(0), w, h))

        # イメージの作成
        sy = cw.s(0)
        if title:
            bmp.blit(subimg, (cw.s(10), (lh - fh) / 2))
            sy += lh

        for i in range(len(pcards)):
            backindex = (1 + i) % 2
            bmp.fill(back[backindex], rect=pygame.Rect(cw.s(0), sy, cw.s(95 + 2 * margin), cw.s(130 + 2 * margin)))
            bmp.blit(pcards[i].cardimg.image, (cw.s(margin), sy + cw.s(margin)))

            def blit_card(headers, x, sy):
                for header in headers:
                    bmp.blit(header.cardimg.get_cardimg(header), (cw.s(x), sy + cw.s(10 + margin)))
                    x += 80 + margin

            current_x = 95 + 2 * margin
            next_x = 0
            for index in (cw.POCKET_SKILL, cw.POCKET_ITEM, cw.POCKET_BEAST):
                current_x += next_x
                next_x = 80 * max_card[index] + margin * (max_card[index] + 1)
                backindex = (index + i) % 2
                bmp.fill(back[backindex], rect=pygame.Rect(cw.s(current_x), sy, cw.s(next_x), cw.s(130 + 2 * margin)))
                adjust_x = (max_card[index] - len(pcards[i].cardpocket[index]))
                x = current_x + adjust_x * 40 + margin * (2 + adjust_x) / 2
                blit_card(pcards[i].cardpocket[index], x, sy)

            sy += cw.s(130 + 2 * margin)

    else:
        raise

    return bmp

def to_clipboard(s):
    """テキストsをクリップボードへ転写する。"""
    tdo = wx.TextDataObject()
    tdo.SetText(s)
    if wx.TheClipboard.Open():
        wx.TheClipboard.SetData(tdo)
        wx.TheClipboard.Close()
        wx.TheClipboard.Flush()


#-------------------------------------------------------------------------------
#　ファイル操作関連
#-------------------------------------------------------------------------------

def dupcheck_plus(path, yado=True):
    """パスの重複チェック。引数のパスをチェックし、重複していたら、
    ファイル・フォルダ名の後ろに"(n)"を付加して重複を回避する。
    宿のファイルパスの場合は、"Data/Temp/Yado"ディレクトリの重複もチェックする。
    """

    tempyado = cw.util.join_paths(cw.tempdir, u"Yado")
    dpath, basename = os.path.split(path)
    fname, ext = cw.util.splitext(basename)
    fname = cw.binary.util.check_filename(fname.strip())
    ext = ext.strip()
    basename = fname + ext
    path = join_paths(dpath, basename)

    if yado:
        if path.startswith("Yado"):
            temppath = path.replace("Yado", tempyado, 1)
        elif path.startswith(tempyado):
            temppath = path.replace(tempyado, "Yado", 1)
        else:
            print u"宿パスの重複チェック失敗", path
            temppath = ""

    else:
        temppath = ""

    count = 2

    while os.path.exists(path) or os.path.exists(temppath):
        basename = "%s(%d)%s" % (fname, count, ext)
        path = join_paths(dpath, basename)

        if yado:
            if path.startswith("Yado"):
                temppath = path.replace("Yado", tempyado, 1)
            elif path.startswith(tempyado):
                temppath = path.replace(tempyado, "Yado", 1)
            else:
                print u"宿パスの重複チェック失敗", path
                temppath = ""

        count += 1

    return join_paths(dpath, basename)

def repl_dischar(fname):
    """
    ファイル名使用不可文字を代替文字に置換し、
    両端に空白があった場合は削除する。
    """
    d = {'\\': u'￥', '/': u'／', ':': u'：', ',': u'，', ';': u'；',
         '*': u'＊', '?': u'？','"': u'”', '<': u'＜', '>': u'＞',
         '|': u'｜'}

    for key, value in d.iteritems():
        fname = fname.replace(key, value)

    fname = fname.strip()
    if fname == "":
        fname = "noname"
    return fname

def check_dischar(s):
    """
    ファイル名使用不可文字を含んでいるかチェックする。
    """
    seq = ('\\', '/', ':', ',', ';', '*', '?','"', '<', '>', '|', '"')

    for i in seq:
        if s.find(i) >= 0:
            return True

    return False

def join_yadodir(path):
    """
    引数のpathを現在読み込んでいる宿ディレクトリと結合させる。
    "Data/Temp/Yado"にパスが存在すれば、そちらを優先させる。
    """
    temppath = join_paths(cw.cwpy.tempdir, path)
    yadopath = join_paths(cw.cwpy.yadodir, path)

    if os.path.exists(temppath):
        return temppath
    else:
        return yadopath

def get_yadofilepath(path):
    """"Data/Yado"もしくは"Data/Temp/Yado"のファイルパスの存在チェックをかけ、
    存在しているパスを返す。存在していない場合は""を返す。
    "Data/Temp/Yado"にパス優先。
    """
    if not cw.cwpy.ydata:
        return ""
    elif path.startswith(cw.cwpy.tempdir):
        temppath = path
        yadopath = path.replace(cw.cwpy.tempdir, cw.cwpy.yadodir, 1)
    elif path.startswith(cw.cwpy.yadodir):
        temppath = path.replace(cw.cwpy.yadodir, cw.cwpy.tempdir, 1)
        yadopath = path
    else:
        return ""

    if yadopath in cw.cwpy.ydata.deletedpaths:
        return ""
    elif os.path.isfile(temppath):
        return temppath
    elif os.path.isfile(yadopath):
        return yadopath
    else:
        return ""

def find_resource(path, mtype):
    """pathとmtypeに該当する素材を拡張子の優先順に沿って探す。"""
    imgpath = ""
    if mtype == cw.M_IMG:
        t = (".png", ".bmp", ".gif", ".jpg")
    elif mtype == cw.M_MSC:
        t = (".ogg", ".mp3", ".mid", ".wav")
    elif mtype == cw.M_SND:
        t = (".wav", ".ogg", ".mp3", ".mid")
    else:
        assert False, mtype

    if os.path.normcase("A") <> os.path.normcase("a"):
        seq = []
        for t2 in t[:]:
            seq.append(t2)
            seq.append(t2.upper())
        t = seq

    for ext in t:
        path2 = path + ext
        if cw.cwpy:
            path2 = cw.cwpy.rsrc.get_filepath(path2)
        if os.path.isfile(path2):
            return path2
    return u""

def get_inusecardmaterialpath(path, mtype, inusecard=None, findskin=True):
    """pathが宿からシナリオへ持ち込んだカードの
    素材を指していればそのパスを返す。
    そうでない場合は空文字列を返す。"""
    imgpath = ""
    if cw.cwpy.event.in_inusecardevent:
        if inusecard or (cw.cwpy.is_runningevent() and cw.cwpy.event.get_inusecard()):
            if not inusecard:
                inusecard = cw.cwpy.event.get_inusecard()
            if not inusecard.carddata.getbool(".", "scenariocard", False) or\
               inusecard.carddata.gettext("Property/Materials", ""):
                imgpath = cw.util.join_yadodir(path)
                imgpath = get_materialpathfromskin(imgpath, mtype, findskin=findskin)
    return imgpath

def get_materialpath(path, mtype, scedir="", system=False, findskin=True):
    """pathが指す素材を、シナリオプレイ中はシナリオ内から探し、
    プレイ中でない場合や存在しない場合はスキンから探す。
    path: 素材の相対パス。
    type: 素材のタイプ。cw.M_IMG, cw.M_MSC, cw.M_SNDのいずれか。
    """
    if mtype == cw.M_IMG and cw.binary.image.path_is_code(path):
        return path
    if not system and (cw.cwpy.is_playingscenario() or scedir):
        tpath = cw.util.join_paths(cw.tempdir, u"ScenarioLog/TempFile", path)
        tpath = cw.cwpy.rsrc.get_filepath(tpath)
        if os.path.isfile(tpath):
            path = tpath
        else:
            if not scedir:
                scedir = cw.cwpy.sdata.scedir
            path = cw.util.join_paths(scedir, path)
            path = cw.cwpy.rsrc.get_filepath(path)
    else:
        path = cw.cwpy.rsrc.get_filepath(path)
        if not os.path.isfile(path):
            path = cw.util.join_paths(cw.cwpy.skindir, path)
    return get_materialpathfromskin(path, mtype, findskin=findskin)

def get_materialpathfromskin(path, mtype, findskin=True):
    if not os.path.isfile(path):
        if not findskin:
            path = ""
        elif path.startswith(cw.cwpy.skindir):
            fname = cw.util.splitext(path)[0]
            if mtype == cw.M_IMG:
                path = cw.util.find_resource(fname, cw.cwpy.rsrc.ext_img)
            elif mtype == cw.M_MSC:
                path = cw.util.find_resource(fname, cw.cwpy.rsrc.ext_bgm)
            elif mtype == cw.M_SND:
                path = cw.util.find_resource(fname, cw.cwpy.rsrc.ext_snd)
        else:
            fname = os.path.basename(path)
            fname = cw.util.splitext(fname)[0]
            dpaths = [cw.cwpy.skindir]
            if os.path.isdir(u"Data/Materials"):
                dpaths.extend(map(lambda d: cw.util.join_paths(u"Data/Materials", d), os.listdir(u"Data/Materials")))
            for dpath in dpaths:
                if mtype == cw.M_IMG:
                    path = cw.util.find_resource(cw.util.join_paths(dpath, "Table", fname), cw.cwpy.rsrc.ext_img)
                elif mtype == cw.M_MSC:
                    path = cw.util.find_resource(cw.util.join_paths(dpath, "Bgm", fname), cw.cwpy.rsrc.ext_bgm)
                    if not path:
                        path = cw.util.find_resource(cw.util.join_paths(dpath, "BgmAndSound", fname), cw.cwpy.rsrc.ext_bgm)
                elif mtype == cw.M_SND:
                    path = cw.util.find_resource(cw.util.join_paths(dpath, "Sound", fname), cw.cwpy.rsrc.ext_snd)
                    if not path:
                        path = cw.util.find_resource(cw.util.join_paths(dpath, "BgmAndSound", fname), cw.cwpy.rsrc.ext_snd)
                if path:
                    break

    return path

def remove_temp():
    """
    一時ディレクトリを空にする。
    """
    dpath = cw.tempdir

    if not os.path.exists(dpath):
        os.makedirs(dpath)

    removeall = True
    for name in os.listdir(dpath):
        if name in ("Scenario", "LockFiles"):
            removeall = False
        else:
            path = join_paths(dpath, name)
            try:
                remove(path)
            except:
                print_ex()
                remove_treefiles(path)

    if removeall and cw.tempdir <> cw.tempdir_init:
        try:
            remove(cw.tempdir)
        except:
            print_ex()
            remove_treefiles(cw.tempdir)

    try:
        remove(u"Data/Temp/Global/Deleted")
    except:
        pass

def remove(path, trashbox=False):
    if os.path.isfile(path):
        remove_file(path, trashbox=trashbox)
    elif os.path.isdir(path):
        if join_paths(path).lower().startswith("data/temp/"):
            # Tempフォルダは、フォルダの内容さえ消えていれば
            # 空フォルダが残っていてもほとんど無害
            try:
                remove_treefiles(path, trashbox=trashbox)
                remove_tree(path, noretry=True, trashbox=trashbox)
            except:
                # まれにフォルダ削除に失敗する環境がある
                #print_ex(file=sys.stderr)
                print_ex()
                remove_treefiles(path, trashbox=trashbox)
        else:
            if trashbox:
                try:
                    remove_tree(path, trashbox=trashbox)
                except:
                    print_ex()
                    remove_treefiles(path, trashbox=trashbox)
                    remove_tree(path, trashbox=trashbox)
            else:
                remove_treefiles(path, trashbox=trashbox)
                remove_tree(path, trashbox=trashbox)

def remove_file(path, retry=0, trashbox=False):
    try:
        if trashbox:
            send_trashbox(path)
        else:
            os.remove(path)
    except WindowsError, err:
        if err.errno == 13 and retry < 5:
            os.chmod(path, stat.S_IWRITE|stat.S_IREAD)
            remove_file(path, retry + 1, trashbox=trashbox)
        elif retry < 5:
            time.sleep(1)
            remove_tree(path, retry + 1, trashbox=trashbox)
        else:
            raise err

def add_winauth(file):
    if os.path.isfile(file) and sys.platform == "win32":
        os.chmod(file, stat.S_IWRITE|stat.S_IREAD)

def remove_tree(treepath, retry=0, noretry=False, trashbox=False):
    try:
        if trashbox:
            send_trashbox(treepath)
        else:
            shutil.rmtree(treepath)
    except WindowsError, err:
        if err.errno == 13 and retry < 5 and not noretry:
            for dpath, dnames, fnames in os.walk(treepath):
                for dname in dnames:
                    path = join_paths(dpath, dname)
                    if os.path.isdir(path):
                        try:
                            os.chmod(path, stat.S_IWRITE|stat.S_IREAD)
                        except WindowsError, err:
                            time.sleep(1)
                            remove_tree2(treepath, trashbox=trashbox)
                            return

                for fname in fnames:
                    path = join_paths(dpath, fname)
                    if os.path.isfile(path):
                        try:
                            os.chmod(path, stat.S_IWRITE|stat.S_IREAD)
                        except WindowsError, err:
                            time.sleep(1)
                            remove_tree2(treepath, trashbox=trashbox)
                            return

            remove_tree(treepath, retry + 1, trashbox=trashbox)
        elif retry < 5 and not noretry:
            time.sleep(1)
            remove_tree(treepath, retry + 1, trashbox=trashbox)
        else:
            remove_tree2(treepath, trashbox=trashbox)

def remove_tree2(treepath, trashbox=False):
    # shutil.rmtree()で権限付与時にエラーになる事があるので
    # 削除方法を変えてみる
    for dpath, dnames, fnames in os.walk(treepath, topdown=False):
        for dname in dnames:
            path = join_paths(dpath, dname)
            if os.path.isdir(path):
                os.rmdir(path)
        for fname in fnames:
            path = join_paths(dpath, fname)
            if os.path.isfile(path):
                if trashbox:
                    send_trashbox(path)
                else:
                    os.remove(path)
    os.rmdir(treepath)

def remove_treefiles(treepath, trashbox=False):
    # remove_tree2()でもたまにエラーになる環境があるらしいので、
    # せめてディレクトリだけでなくファイルだけでも削除を試みる
    for dpath, dnames, fnames in os.walk(treepath, topdown=False):
        for fname in fnames:
            path = join_paths(dpath, fname)
            if os.path.isfile(path):
                add_winauth(path)
                if trashbox:
                    send_trashbox(path)
                else:
                    os.remove(path)

def rename_file(path, dstpath, trashbox=False):
    """pathをdstpathへ移動する。
    すでにdstpathがある場合は上書きされる。
    """
    if not os.path.isdir(os.path.dirname(dstpath)):
        os.makedirs(os.path.dirname(dstpath))
    if os.path.isfile(dstpath):
        remove_file(dstpath, trashbox=trashbox)
    try:
        shutil.move(path, dstpath)
    except OSError:
        # ファイルシステムが異なっていると失敗する
        # 可能性があるのでコピー&削除を試みる
        print_ex()
        with open(path, "rb") as f1:
            with open(dstpath, "wb") as f2:
                f2.write(f1.read())
                f2.flush()
                f2.close()
            f1.close()
        remove_file(path, trashbox=trashbox)

def send_trashbox(path):
    """
    可能であればpathをゴミ箱へ送る。
    """
    if sys.platform == "win32":
        path = os.path.normpath(os.path.abspath(path))
        ope = win32com.shell.shellcon.FO_DELETE
        flags = win32com.shell.shellcon.FOF_NOCONFIRMATION |\
                win32com.shell.shellcon.FOF_ALLOWUNDO |\
                win32com.shell.shellcon.FOF_SILENT
        win32com.shell.shell.SHFileOperation((None, ope, path + '\0\0', None, flags, None, None))
    elif os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


#-------------------------------------------------------------------------------
#　ZIPファイル関連
#-------------------------------------------------------------------------------

class _LhafileWrapper(lhafile.Lhafile):
    def __init__(self, path, mode):
        # 十六進数のファイルサイズを表す文字列+Windows改行コードが
        # 冒頭に入っていることがある。
        # その場合は末尾にも余計なデータもあるため、冒頭で指定された
        # サイズにファイルを切り詰めなくてはならない。
        f = open(path, "rb")
        b = str(f.read(1))
        strnum = []
        while b in ("0123456789abcdefABCDEF"):
            strnum.append(b)
            b = str(f.read(1))
        if strnum and b == '\r' and f.read(1) == '\n':
            strnum = "".join(strnum)
            num = int(strnum, 16)
            data = f.read(num)
            f.close()
            f = io.BytesIO(data)
            lhafile.Lhafile.__init__(self, f)
            self.f = f
        else:
            f.seek(0)
            lhafile.Lhafile.__init__(self, f)
            self.f = f

    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    def close(self):
        self.f.close()

def zip_file(path, mode):
    """zipfile.ZipFileのインスタンスを生成する。
    FIXME: Python 2.7のzipfile.ZipFileはアーカイブ内の
    ファイル名にあるディレクトリセパレータを'/'に置換してしまうため、
    「ソ」などのいわゆるShift JISの0x5C問題に引っかかって
    正しいファイル名が得られなくなってしまう。
    まったくスレッドセーフではない悪い方法だが、
    それを回避するには一時的にos.sepを'/'にして凌ぐしかない。"""
    if path.lower().endswith(".lzh"):
        return _LhafileWrapper(path, mode)
    else:
        sep = os.sep
        os.sep = "/"
        try:
            return zipfile.ZipFile(path, mode)
        finally:
            os.sep = sep

def compress_zip(path, zpath, unicodefilename=False):
    """pathのデータをzpathで指定したzipファイルに圧縮する。
    path: 圧縮するディレクトリパス
    """
    if not unicodefilename:
        encoding = sys.getfilesystemencoding()
    dpath = os.path.dirname(zpath)

    if dpath and not os.path.isdir(dpath):
        os.makedirs(dpath)

    z = zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED)
    rpl_dir = path + "/"

    for dpath, dnames, fnames in os.walk(unicode(path)):
        for dname in dnames:
            fpath = join_paths(dpath, dname)
            if os.path.isdir(fpath):
                mtime = time.localtime(os.path.getmtime(fpath))[:6]
                zname = fpath.replace(rpl_dir, "", 1) + "/"
                zinfo = zipfile.ZipInfo(zname, mtime)
                if unicodefilename:
                    zinfo.flag_bits |= 0x800
                z.writestr(zinfo, "")

        for fname in fnames:
            fpath = join_paths(dpath, fname)
            if os.path.isfile(fpath):
                zname = fpath.replace(rpl_dir, "", 1)
                if unicodefilename:
                    z.write(fpath, zname)
                else:
                    z.write(fpath, zname.encode(encoding))

    z.close()
    return zpath

def decompress_zip(path, dstdir, dname="", startup=None, progress=None, overwrite=False):
    """zipファイルをdstdirに解凍する。
    解凍したディレクトリのpathを返す。
    """
    try:
        z = zip_file(path, "r")
    except:
        return None

    if not dname:
        dname = splitext(os.path.basename(path))[0]

    if overwrite:
        paths = set()
    else:
        dstdir = join_paths(dstdir, dname)
        dstdir = dupcheck_plus(dstdir, False)

    seq = z.infolist()
    if startup:
        startup(len(seq))
    for i, (zname, info) in enumerate(zip(z.namelist(), z.infolist())):

        if progress and i % 10 == 0:
            if progress(i):
                if overwrite:
                    break
                else:
                    z.close()
                    remove(dstdir)
                    return
        name = decode_zipname(zname).replace('\\', '/')
        normpath = os.path.normpath(name)
        if os.path.isabs(normpath):
            continue
        if normpath == ".." or normpath.startswith(".." + os.path.sep):
            continue

        if name.endswith("/"):
            name = name.rstrip("/")
            dpath = join_paths(dstdir, name)

            if dpath and not os.path.isdir(dpath):
                os.makedirs(dpath)

        else:
            fpath = join_paths(dstdir, name)
            dpath = os.path.dirname(fpath)

            if dpath and not os.path.isdir(dpath):
                os.makedirs(dpath)

            if isinstance(info.date_time, datetime.datetime):
                mtime = time.mktime(time.strptime(info.date_time.strftime("%Y/%m/%d %H:%M:%S"), "%Y/%m/%d %H:%M:%S"))
            else:
                mtime = time.mktime(time.strptime("%d/%02d/%02d %02d:%02d:%02d" % (info.date_time), "%Y/%m/%d %H:%M:%S"))

            if overwrite:
                # 上書き展開時は一部ファイルでエラーが出た場合に
                # 上書き先を改名して対処する
                # (再生中のBGMが上書きできない場合など)
                paths.add(os.path.normcase(os.path.normpath(os.path.abspath(fpath))))
                if not os.path.isfile(fpath) or os.path.getmtime(fpath) <> mtime:
                    data = z.read(zname)
                    try:
                        with open(fpath, "wb") as f:
                            f.write(data)
                            f.flush()
                            f.close()
                    except:
                        # 改名してリトライ
                        if os.path.isfile(fpath):
                            dst = join_paths(u"Data/Temp/Global/Deleted", os.path.basename(fpath))
                            dst = dupcheck_plus(dst, False)
                            if not os.path.isdir(u"Data/Temp/Global/Deleted"):
                                os.makedirs(u"Data/Temp/Global/Deleted")
                            rename_file(fpath, dst)
                        with open(fpath, "wb") as f:
                            f.write(data)
                            f.flush()
                            f.close()
                else:
                    continue
            else:
                data = z.read(zname)
                with open(fpath, "wb") as f:
                    f.write(data)
                    f.flush()
                    f.close()

            os.utime(fpath, (os.path.getatime(fpath), mtime))

    z.close()

    if overwrite:
        for dpath, _dnames, fnames in os.walk(dstdir):
            for fname in fnames:
                path = join_paths(dpath, fname)
                path = os.path.normcase(os.path.normpath(os.path.abspath(path)))
                if not path in paths:
                    remove(path)

    if progress:
        progress(len(seq))

    return dstdir

def decode_zipname(name):
    if not isinstance(name, unicode):
        try:
            name = name.decode("utf_8_sig")
        except UnicodeDecodeError:
            try:
                name = name.decode(cw.MBCS)
            except UnicodeDecodeError:
                try:
                    name = name.decode("euc-jp")
                except UnicodeDecodeError:
                    try:
                        name = name.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            name = name.decode("utf-16")
                        except UnicodeDecodeError:
                            try:
                                name = name.decode("utf-32")
                            except UnicodeDecodeError:
                                name = name

    return name

def decode_text(name):
    if not isinstance(name, unicode):
        try:
            name = name.decode("utf_8_sig")
        except UnicodeDecodeError:
            try:
                name = name.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    name = name.decode("utf-16")
                except UnicodeDecodeError:
                    try:
                        name = name.decode("utf-32")
                    except UnicodeDecodeError:
                        try:
                            name = name.decode(cw.MBCS)
                        except UnicodeDecodeError:
                            try:
                                name = name.decode("euc-jp")
                            except UnicodeDecodeError:
                                name = name

    return name

def read_zipdata(zfile, name):
    try:
        data = zfile.read(name)
    except KeyError:
        try:
            data = zfile.read(name.encode(cw.MBCS))
        except KeyError:
            try:
                data = zfile.read(name.encode("euc-jp"))
            except KeyError:
                try:
                    data = zfile.read(name.encode("utf-8"))
                except KeyError:
                    data = ""

    return data

def get_elementfromzip(zpath, name, tag=""):
    with zip_file(zpath, "r") as z:
        data = read_zipdata(z, name)
        z.close()
    f = StringIO.StringIO(data)
    try:
        element = cw.data.xml2element(name, tag, stream=f)
    finally:
        f.close()
    return element

def decompress_cab(path, dstdir, dname="", startup=None, progress=None, overwrite=False):
    """cabファイルをdstdirに解凍する。
    解凍したディレクトリのpathを返す。
    """
    if not dname:
        dname = splitext(os.path.basename(path))[0]

    if not overwrite:
        dstdir = join_paths(dstdir, dname)
        dstdir = dupcheck_plus(dstdir, False)

    if overwrite and os.path.isdir(dstdir):
        # 強制的に全てのファイルを展開するため、
        # 元々あったファイルを削除するか、削除予定地へ転送する
        for dpath, _dnames, fnames in os.walk(dstdir):
            for fname in fnames:
                fpath = join_paths(dpath, fname)
                dst = join_paths(u"Data/Temp/Global/Deleted", fname)
                if not os.path.isdir(u"Data/Temp/Global/Deleted"):
                    os.makedirs(u"Data/Temp/Global/Deleted")
                dst = dupcheck_plus(dst)
                rename_file(fpath, dst)
                remove(dst)

    if startup or progress:
        filenum = cab_filenum(path)

    if startup:
        startup(filenum)

    try:
        if not os.path.isdir(dstdir):
            os.makedirs(dstdir)
        ss = []
        if sys.platform == "win32" and sys.getwindowsversion().major <= 5:
            # バージョン5以前の`expand.exe`は`-f:*`でディレクトリ構造を無視してしまう
            for dname in cab_dpaths(path):
                if not dname:
                    continue
                dstdir2 = cw.util.join_paths(dstdir, dname)
                if not os.path.isdir(dstdir2):
                    os.makedirs(dstdir2)
                ss.append("expand \"%s\" -f:\"%s\\*\" \"%s\"" % (path, dname, dstdir2))
            ss.append("expand \"%s\" -f:\"*\" \"%s\"" % (path, dstdir))
        else:
            ss.append("expand \"%s\" -f:* \"%s\"" % (path, dstdir))
        encoding = sys.getfilesystemencoding()
        if progress:
            class Progress(object):
                def __init__(self):
                    self.result = None
                    self.cancel = False

                def run(self):
                    for s in ss:
                        p = subprocess.Popen(s.encode(encoding), shell=True)
                        r = p.poll()
                        while r is None:
                            if self.cancel:
                                p.kill()
                            time.sleep(0.001)
                            r = p.poll()
                        if r <> 0:
                            return # 失敗
                    self.result = dstdir

            prog = Progress()
            thr = threading.Thread(target=prog.run)
            thr.start()
            count = 0
            while thr.is_alive():
                # ファイル数カウント
                last_count = count
                count = 0
                for dpath, _dnames, fnames in os.walk(dstdir):
                    count += len(fnames)
                if last_count <> count:
                    if progress(count):
                        prog.cancel = True
                p = time.time() + 0.1
                while thr.is_alive() and time.time() < p:
                    time.sleep(0.001)
            if prog.cancel and not overwrite:
                remove(dstdir)
                return None
        else:
            for s in ss:
                if subprocess.call(s.encode(encoding), shell=True) <> 0:
                    return None
    except Exception:
        cw.util.print_ex()
        return None

    if progress:
        progress(filenum)

    return dstdir

def cab_filenum(cab):
    """CABアーカイブに含まれるファイル数を返す。"""
    word = struct.Struct("<h")
    try:
        with io.BufferedReader(io.FileIO(cab, "rb")) as f:
            # ヘッダ
            buf = f.read(36)
            f.close()
            if buf[:4] <> "MSCF":
                return 0

            cfiles = word.unpack(buf[28:30])[0]
            return cfiles
    except Exception:
        cw.util.print_ex()
    return 0

def cab_hasfile(cab, fname):
    """CABアーカイブに指定された名前のファイルが含まれているか判定する。"""
    if not os.path.isfile(cab):
        return ""

    dword = struct.Struct("<l")
    word = struct.Struct("<h")
    if isinstance(fname, (str, unicode)):
        fname = os.path.normcase(fname)
    else:
        s = set()
        for name in fname:
            s.add(os.path.normcase(name))
        fname = s

    encoding = "cp932"
    try:
        with io.BufferedReader(io.FileIO(cab, "rb")) as f:
            # ヘッダ
            buf = f.read(36)
            if buf[:4] <> "MSCF":
                f.close()
                return ""

            cofffiles = dword.unpack(buf[16:20])[0]
            cfiles = word.unpack(buf[28:30])[0]
            f.seek(cofffiles)

            for _i in xrange(cfiles):
                buf = f.read(16)
                attribs = word.unpack(buf[14:16])[0]
                name = []
                while True:
                    c = str(f.read(1))
                    if c == '\0':
                        break
                    name.append(c)
                name = "".join(name)
                _A_NAME_IS_UTF = 0x80
                if not (attribs & _A_NAME_IS_UTF):
                    name = unicode(name, encoding)
                if isinstance(fname, (str, unicode)):
                    if fname == os.path.normcase(os.path.basename(name)):
                        f.close()
                        return name
                else:
                    if os.path.normcase(os.path.basename(name)) in fname:
                        f.close()
                        return name
            f.close()
    except Exception:
        cw.util.print_ex()
    return ""

def cab_dpaths(cab):
    """CABアーカイブ内のディレクトリのsetを返す。"""
    if not os.path.isfile(cab):
        return ""

    dword = struct.Struct("<l")
    word = struct.Struct("<h")

    r = set()

    encoding = "cp932"
    try:
        with io.BufferedReader(io.FileIO(cab, "rb")) as f:
            # ヘッダ
            buf = f.read(36)
            if buf[:4] <> "MSCF":
                f.close()
                return ""

            cofffiles = dword.unpack(buf[16:20])[0]
            cfiles = word.unpack(buf[28:30])[0]
            f.seek(cofffiles)

            for _i in xrange(cfiles):
                buf = f.read(16)
                attribs = word.unpack(buf[14:16])[0]
                name = []
                while True:
                    c = str(f.read(1))
                    if c == '\0':
                        break
                    name.append(c)
                name = "".join(name)
                _A_NAME_IS_UTF = 0x80
                if not (attribs & _A_NAME_IS_UTF):
                    name = unicode(name, encoding)
                i = name.rfind(u"\\")
                if i == -1:
                    r.add(u"")
                else:
                    dname = name[:i]
                    r.add(dname)
            f.close()
    except Exception:
        cw.util.print_ex()
    return r

def cab_scdir(cab):
    """CABアーカイブ内でSummary.wsmまたは
    Summary.xmlが含まれるフォルダを返す。
    """
    fpath = cab_hasfile(cab, ("Summary.xml", "Summary.wsm"))
    return os.path.dirname(fpath)

#-------------------------------------------------------------------------------
#　テキスト操作関連
#-------------------------------------------------------------------------------

def encodewrap(s):
    """改行コードを\nに置換する。"""
    r = []
    if not s:
        return u""
    for c in s:
        if c == '\\':
            r.append("\\\\")
        elif c == '\n':
            r.append("\\n")
        elif c == '\r':
            pass
        else:
            r.append(c)
    return "".join(r)

def decodewrap(s, code="\n"):
    """\nを改行コードに戻す。"""
    if not s:
        return u""
    r = []
    bs = False
    for c in s:
        if bs:
            if c == 'n':
                r.append(code)
            elif c == '\\':
                r.append('\\')
            else:
                r.append(c)
            bs = False
        elif c == '\\':
            bs = True
        else:
            r.append(c)
    return "".join(r)

def encodetextlist(arr):
    """arrを\n区切りの文字列にする。"""
    return encodewrap("\n".join(arr))

def decodetextlist(s):
    """\n区切りの文字列を文字配列にする。"""
    if not s:
        return []
    return decodewrap(s).split("\n")

def is_hw(unichr):
    """unichrが半角文字であればTrueを返す。"""
    return not unicodedata.east_asian_width(unichr) in ('F', 'W', 'A')

def get_strlen(s):
    return reduce(lambda a, b: a + b, map(lambda c: 1 if cw.util.is_hw(c) else 2, s))

def rjustify(s, length, c):
    slen = cw.util.get_strlen(s)
    if slen < length:
        s += c * (length - slen)
    return s

def ljustify(s, length, c):
    slen = cw.util.get_strlen(s)
    if slen < length:
        s = (c * (length - slen)) + s
    return s

WRAPS_CHARS = u"｡|､|，|、|。|．|）|」|』|〕|｝|】"

def txtwrap(s, mode, width=30, wrapschars="", encodedtext=True, spcharinfo=None):
    """引数の文字列を任意の文字数で改行する(全角は2文字として数える)。
    mode=1: カード解説。
    mode=2: 画像付きメッセージ（台詞）用。
    mode=3: 画像なしメッセージ用。
    mode=4: キャラクタ情報ダイアログの解説文・張り紙説明用。
    mode=5: 素質解説文用。
    mode=6: メッセージダイアログ用。
    """
    if mode == 1:
        wrapschars = WRAPS_CHARS
        width = 37
    elif mode == 2:
        wrapschars = ""
        width = 32
    elif mode == 3:
        wrapschars = ""
        width = 42
    elif mode == 4:
        wrapschars = WRAPS_CHARS
        width = 37
    elif mode == 5:
        wrapschars = WRAPS_CHARS
        width = 24
    elif mode == 6:
        wrapschars = WRAPS_CHARS
        width = 48

    if encodedtext:
        # \\nを改行コードに戻す
        s = cw.util.decodewrap(s)
    # 行頭禁止文字集合
    r_wchar = re.compile(wrapschars) if not mode in (2, 3) and wrapschars else None
    # 特殊文字記号集合
    re_color = "&[\x20-\x7E]"
    r_spchar = re.compile("#.|" + re_color) if mode in (2, 3) else None
    if spcharinfo:
        spcharinfo2 = []
    cnt = 0
    asciicnt = 0
    wraped = False
    skip = False
    spchar = False
    defspchar = False
    wrapafter = False
    seq = []
    seqlen = 0

    def seq_insert(index, char):
        if index < 0:
            index = len(seq) + index
        seq.insert(index, char)
        if spcharinfo:
            for i in reversed(xrange(len(spcharinfo2))):
                spi = spcharinfo2[i]
                if spi < index:
                    break
                else:
                    spcharinfo2[i] += len(char)

    for index, char in enumerate(s):
        spchar2 = spchar
        spchar = False
        width2 = width
        wrapafter2 = wrapafter
        defspchar2 = defspchar
        defspchar = False

        if r_spchar and not defspchar2:
            if skip:
                if spcharinfo and index in spcharinfo:
                    spcharinfo2.append(seqlen)
                seq.append(char)
                seqlen += len(char)
                skip = False
                continue

            chars = char + get_char(s, index + 1)

            if r_spchar.match(chars.lower()):
                if spcharinfo and index in spcharinfo:
                    spcharinfo2.append(seqlen)
                if not chars.startswith("#") or\
                   not chars[:2].lower() in cw.cwpy.rsrc.specialchars or\
                   cw.cwpy.rsrc.specialchars[chars[:2].lower()][1]:
                    seq.append(char)
                    seqlen += len(char)
                    skip = True
                    continue
                spchar = True
                if not chars.startswith("&"):
                    wrapafter = False
                    defspchar = True

        # 行頭禁止文字
        if cnt == 0 and not wraped and r_wchar and r_wchar.match(char):
            seq_insert(-1, char)
            seqlen += len(char)
            asciicnt = 0
            wraped = True
        # 改行記号
        elif char == "\n":
            if not wrapafter:
                seq.append(char)
                seqlen += len(char)
            cnt = 0
            asciicnt = 0
            wraped = False
            wrapafter = False
        # 半角文字
        elif is_hw(char):
            seq.append(char)
            seqlen += len(char)
            cnt += 1
            if not (mode in (2, 3)) and not (mode == 1 and index+1 < len(s) and not is_hw(s[index+1])):
                asciicnt += 1
            if spchar2 or not (mode in (2, 3)) or len(s) <= index+1 or is_hw(s[index+1]):
                width2 += 1
            wrapafter = False

        # 行頭禁止文字・改行記号・半角文字以外
        else:
            seq.append(char)
            seqlen += len(char)
            cnt += 2
            asciicnt = 0
            wrapafter = False
            if mode in (1, 2, 3) and index+1 < len(s) and is_hw(s[index+1]):
                width2 += 1

        # 互換動作: 1.28以降は行末に半角スペースがあると折り返し位置が変わる
        #           (イベントによるメッセージのみ)
        if cw.cwpy.sdata and not cw.cwpy.sct.lessthan("1.20", cw.cwpy.sdata.get_versionhint()):
            if not wrapafter2 and index+1 < len(s) and s[index+1] == " " and mode in (2, 3):
                width2 += 1
                asciicnt = 0

        # 行折り返し処理
        if not spchar and cnt > width2:
            if defspchar2 and width2+1 < cnt:
                index = -(cnt - (width+1))
                if seq[-index] <> "\n":
                    seq_insert(index, "\n")
                    seqlen += len("\n")
                cnt = 1
            elif width2 >= asciicnt > 0 and not defspchar2:
                if not get_char(s, index + 1) == "\n" and seq[-asciicnt] <> "\n":
                    seq_insert(-asciicnt, "\n")
                    seqlen += len("\n")
                cnt = asciicnt
            elif index + 1 <= len(s) or not get_char(s, index + 1) == "\n":
                if index + 2 <= len(s) or not get_char(s, index + 2) == "\n":
                    seq.append("\n")
                    seqlen += len("\n")
                    wrapafter = True
                cnt = 0
                asciicnt = 0
                wraped = False

    if spcharinfo:
        spcharinfo.clear()
        spcharinfo.update(spcharinfo2)

    return "".join(seq).rstrip()

def wordwrap(s, width, get_width, wrapschars=WRAPS_CHARS):
    """
    sをwidthの幅で折り返す。
    テキストの長さをは計る時にget_width(s)を使用する。
    """
    r_wchar = re.compile(wrapschars)
    lines = []
    text = u""
    for i, c in enumerate(s):
        text2 = text + c
        if width < get_width(text2):
            if r_wchar.match(c.lower()):
                if text:
                    lines.append(text[:-1])
                    text = text[-1] + c
                else:
                    lines.append(text2)
                    text = u""
            else:
                lines.append(text)
                text = c
        else:
            text = text2

    lines.append(text)
    return u"\n".join(lines)

assert wordwrap("ABC.DEFG.H,IKLM?", 3, lambda s: len(s), "\\.|,|\\?") == "AB\nC.D\nEF\nG.\nH,I\nKL\nM?"



def get_char(s, index):
    try:
        if 0 <= index and index < len(s):
            return s[index]
        return ""
    except:
        return ""

def format_title(fmt, d):
    """foobar2000の任意フォーマット文字列のような形式で
    文字列の構築を行う。
     * %%で囲われた文字列は変数となり、辞書dから得られる値に置換される。
     * []で囲われた文字列は、その内側で使用された変数がなければ丸ごと無視される。
     * \の次の文字列は常に通常文字となる。

    例えば次のようになる:
        d = { "application":"CardWirthPy", "skin":"スキン名", "yado":"宿名" }
        s = format_title("%application% %skin%[ - %yado%[ %scenario%]]", d)
        assert s == "CardWirthPy スキン名 - 宿名"
    """
    class _FormatPart(object):
        """フォーマット内の変数。"""
        def __init__(self, name):
            self.name = name

    def eat_parts(fmt, subsection):
        """formatを文字列とFormatPartのリストに分解。
        []で囲われた部分はサブリストとする。
        """
        seq = []
        bs = False
        while fmt:
            c = fmt[0]
            fmt = fmt[1:]
            if bs:
                seq.append(c)
                bs = False
            elif c == "\\":
                bs = True
            elif c == "]" and subsection:
                return fmt, seq
            elif c == "%":
                ci = fmt.find("%")
                if ci <> -1:
                    seq.append(_FormatPart(fmt[:ci]))
                    fmt = fmt[ci+1:]
            elif c == "[":
                fmt, list2 = eat_parts(fmt, True)
                seq.append(list2)
            else:
                seq.append(c)
        return fmt, seq

    fmt, l = eat_parts(fmt, False)
    assert not fmt
    def do_format(l):
        """フォーマットを実行する。"""
        seq = []
        use = False
        for sec in l:
            if isinstance(sec, _FormatPart):
                name = d.get(sec.name, "")
                if name:
                    seq.append(name)
                    use = True
            elif isinstance(sec, list):
                text, use2 = do_format(sec)
                if use2:
                    seq.append(text)
                    use = True
            else:
                seq.append(sec)
        return "".join(seq), use

    return do_format(l)[0]

#-------------------------------------------------------------------------------
# wx汎用関数
#-------------------------------------------------------------------------------

def load_wxbmp(name="", mask=False, image=None, maskpos=(0, 0), f=None, retry=True, can_loaded_scaledimage=True,
               noscale=False, up_scr=None):
    """pos(0,0)にある色でマスクしたwxBitmapを返す。"""
    if sys.platform <> "win32":
        assert threading.currentThread() <> cw.cwpy
    if not f and (not cw.binary.image.code_to_data(name) and not os.path.isfile(name)) and not image:
        return wx.EmptyBitmap(0, 0)

    if cw.cwpy and cw.cwpy.rsrc:
        name = cw.cwpy.rsrc.get_filepath(name)

    if up_scr is None:
        up_scr = cw.UP_SCR # ゲーム画面と合わせるため、ダイアログなどでも描画サイズのイメージを使用する
    name, up_scr = find_scaledimagepath(name, up_scr, can_loaded_scaledimage, noscale)

    bmpdepth = 0
    maskcolour = None
    if mask:
        if not image:
            try:
                if f:
                    data = f.read()
                elif cw.binary.image.path_is_code(name):
                    data = cw.binary.image.code_to_data(name)
                else:
                    if not os.path.isfile(name):
                        return wx.EmptyBitmap(0, 0)
                    with open(name, "rb") as f2:
                        data = f2.read()
                        f2.close()
                if not data:
                    return wx.EmptyBitmap(0, 0)
                
                bmpdepth = cw.image.get_bmpdepth(data)
                data, ok = cw.image.fix_cwnext16bitbitmap(data)
                if name and ok and not cw.binary.image.path_is_code(name):
                    # BUG: io.BytesIO()を用いてのwx.ImageFromStream()は、
                    #      二重にファイルを読む処理よりなお10倍も遅い
                    image = wx.Image(name)
                else:
                    with io.BytesIO(data) as f2:
                        image = wx.ImageFromStream(f2, wx.BITMAP_TYPE_ANY, -1)
                        f2.close()
            except:
                print_ex()
                print u"画像が読み込めません(load_wxbmp)", name
                return wx.EmptyBitmap(0, 0)

        def set_mask(image, maskpos):
            maskpos = convert_maskpos(maskpos, image.Width, image.Height)
            r = image.GetRed(maskpos[0], maskpos[1])
            g = image.GetGreen(maskpos[0], maskpos[1])
            b = image.GetBlue(maskpos[0], maskpos[1])
            image.SetMaskColour(r, g, b)
            return (r, g, b)

        if not image.HasAlpha() and not image.HasMask():
            maskcolour = set_mask(image, maskpos)

        wxbmp = image.ConvertToBitmap()

        # 255色GIFなどでパレットに存在しない色が
        # マスク色に設定されている事があるので、
        # その場合は通常通り左上の色をマスク色とする
        # 将来、もしこの処理の結果問題が起きた場合は
        # このif文以降の処理を削除する必要がある
        if mask and image.HasMask() and image.CountColours() <= 255:
            palette = wxbmp.GetPalette()
            if not palette is None:
                mask = (image.GetMaskRed(), image.GetMaskGreen(), image.GetMaskBlue())
                maskok = False
                for pixel in xrange(palette.GetColoursCount()):
                    if palette.GetRGB(pixel) == mask:
                        maskok = True
                        break
                if not maskok:
                    maskcolour = set_mask(image, maskpos)
                    wxbmp = image.ConvertToBitmap()

    elif image:
        wxbmp = image.ConvertToBitmap()
    else:
        try:
            wxbmp = wx.Bitmap(name)
        except:
            print u"画像が読み込めません(load_wxbmp)", name
            return wx.EmptyBitmap(0, 0)

    if bmpdepth == 1 and mask:
        wxbmp.bmpdepthis1 = True
    if maskcolour:
        wxbmp.maskcolour = maskcolour

    wxbmp.scr_scale = up_scr

    return wxbmp

def copy_wxbmp(bmp):
    """wx.Bitmapのコピーを生成する。"""
    w = bmp.GetWidth()
    h = bmp.GetHeight()
    return bmp.GetSubBitmap((0, 0, w, h))

def convert_to_image(bmp):
    """wx.Bitmapをwx.Imageに変換する。
    FIXME: 直接bmp.ConvertToImage()を使用すると
           画像が化ける事がある
    """
    w = bmp.GetWidth()
    h = bmp.GetHeight()
    buf = array.array('B', [0] * (w*h * 3))
    bmp.CopyToBuffer(buf)
    img = wx.ImageFromBuffer(w, h, buf)
    if hasattr(bmp, "bmpdepthis1"):
        img.bmpdepthis1 = bmp.bmpdepthis1
    if hasattr(bmp, "maskcolour"):
        r, g, b = bmp.maskcolour
        img.SetMaskColour(r, g, b)
    return img

def fill_bitmap(dc, bmp, csize, ctrlpos=(0, 0)):
    """引数のbmpを敷き詰める。"""
    imgsize = bmp.GetSize()
    w, h = imgsize

    startx = -(ctrlpos[0] % w)
    starty = -(ctrlpos[1] % h)

    x = startx
    while x < csize[0]:
        y = starty
        while y < csize[1]:
            dc.DrawBitmap(bmp, x, y, False)
            y += h
        x += w

def get_centerposition(size, targetpos, targetsize=(1, 1)):
    """中央取りのpositionを計算して返す。"""
    top, left = targetsize[0] / 2 , targetsize[1] / 2
    top, left = targetpos[0] + top, targetpos[1] + left
    top, left = top - size[0] / 2, left - size[1] /2
    return (top, left)

def draw_center(dc, target, pos, mask=True):
    """指定した座標にBitmap・テキストの中央を合わせて描画。
    target: wx.Bitmapかstrかunicode
    """
    if isinstance(target, (str, unicode)):
        size = dc.GetTextExtent(target)
        pos = get_centerposition(size, pos)
        dc.DrawText(target, pos[0], pos[1])
    elif isinstance(target, wx.Bitmap):
        size = target.GetSize()
        pos = get_centerposition(size, pos)
        dc.DrawBitmap(target, pos[0], pos[1], mask)

def draw_height(dc, target, height, mask=True):
    """高さのみ指定して、横幅は背景の中央に合わせてBitmap・テキストを描画。
    target: wx.Bitmapかstrかunicode
    """
    if isinstance(target, (str, unicode)):
        width = (dc.GetSize()[0] - dc.GetTextExtent(target)[0]) / 2
        dc.DrawText(target, width, height)
    elif isinstance(target, wx.Bitmap):
        width = (dc.GetSize()[0] - target.GetSize()[0]) / 2
        dc.DrawBitmap(target, width, height, mask)

def draw_box(dc, pos, size):
    """dcでStaticBoxの囲いを描画する。"""
    # ハイライト
    colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DHIGHLIGHT)
    dc.SetPen(wx.Pen(colour, 1, wx.SOLID))
    box = get_boxpointlist((pos[0] + 1, pos[1] + 1), size)
    dc.DrawLineList(box)
    # 主線
    colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
    dc.SetPen(wx.Pen(colour, 1, wx.SOLID))
    box = get_boxpointlist(pos, size)
    dc.DrawLineList(box)

def draw_witharound_simple(dc, s, x, y, aroundcolor):
    """テキストsを縁取りしながら描画する。"""
    oldcolor = dc.GetTextForeground()
    dc.SetTextForeground(aroundcolor)
    for xx in xrange(x-1, x+2):
        for yy in xrange(y-1, y+2):
            if xx <> x or yy <> y:
                dc.DrawText(s, xx, yy)
    dc.SetTextForeground(oldcolor)
    dc.DrawText(s, x, y)

def draw_witharound(dc, s, x, y, maxwidth=0):
    """テキストsを縁取りしながら描画する。
    フォントのスムージングを行う。
    """
    draw_antialiasedtext(dc, s, x, y, False, maxwidth, 0, scaledown=False, bordering=True)

def draw_antialiasedtext(dc, text, x, y, white, maxwidth, padding,
                         quality=None, scaledown=True, alpha=64,
                         bordering=False):
    if bordering:
        subimg = cw.util.render_antialiasedtext(dc, text, not white, maxwidth, padding,
                                                scaledown=scaledown, quality=quality, alpha=alpha)
        for xx in xrange(x-1, x+2):
            for yy in xrange(y-1, y+2):
                if xx <> x or yy <> y:
                    dc.DrawBitmap(subimg, xx, yy)
    subimg = cw.util.render_antialiasedtext(dc, text, white, maxwidth, padding,
                                            scaledown=scaledown, quality=quality)
    dc.DrawBitmap(subimg, x, y)

def render_antialiasedtext(basedc, text, white, maxwidth, padding,
                           quality=None, scaledown=True, alpha=255):
    """スムージングが施された、背景が透明なテキストを描画して返す。"""
    if quality is None:
        if 3 <= wx.VERSION[0]:
            quality = wx.IMAGE_QUALITY_BICUBIC
        else:
            quality = wx.IMAGE_QUALITY_NORMAL
    w, h = basedc.GetTextExtent(text)
    font = basedc.GetFont()
    upfont = 0 < maxwidth and maxwidth < w and not scaledown
    if upfont:
        scaledown = True
        basefont = font
        pixelsize = font.GetPixelSize()[1]
        family = font.GetFamily()
        style = font.GetStyle()
        weight = font.GetWeight()
        underline = font.GetUnderlined()
        facename = font.GetFaceName()
        encoding = font.GetEncoding()
        font = wx.FontFromPixelSize((0, pixelsize*2), family, style, weight, 0, facename, encoding)
        basedc.SetFont(font)
        w, h = basedc.GetTextExtent(text)
    subimg = wx.EmptyBitmap(w, h)
    dc = wx.MemoryDC(subimg)
    dc.SetFont(font)
    dc.SetBrush(wx.BLACK_BRUSH)
    dc.SetPen(wx.BLACK_PEN)
    dc.DrawRectangle(-1, -1, w + 2, h + 2)
    dc.SetTextForeground(wx.WHITE)
    dc.DrawText(text, 0, 0)
    subimg = subimg.ConvertToImage()
    if white:
        subimg.ConvertColourToAlpha(255, 255, 255)
    else:
        subimg.ConvertColourToAlpha(0, 0, 0)

    dc.SelectObject(wx.NullBitmap)

    if scaledown:
        if 0 < maxwidth and w/2 + padding*2 > maxwidth:
            size = (maxwidth - padding*2, h/2)
            subimg = subimg.Rescale(size[0], h/2, quality=quality)
        else:
            subimg = subimg.Rescale(w/2, h/2, quality=quality)
    else:
        if 0 < maxwidth and w + padding*2 > maxwidth:
            size = (maxwidth - padding*2, h)
            subimg = subimg.Rescale(size[0], h, quality=quality)

    if alpha <> 255:
        cw.imageretouch.mul_wxalpha(subimg, alpha)

    if upfont:
        font = wx.FontFromPixelSize((0, pixelsize), family, style, weight, 0, facename, encoding)
        basedc.SetFont(font)

    subimg = subimg.ConvertToBitmap()
    return subimg

def get_boxpointlist(pos, size):
    """StaticBoxの囲い描画用のposlistを返す。"""
    x, y = pos
    width, height = size
    poslist = [][:]
    poslist.append((x, y, x + width, y))
    poslist.append((x, y, x, y + height))
    poslist.append((x + width, y, x + width, y + height))
    poslist.append((x, y + height, x + width, y + height))
    return poslist

def create_fileselection(parent, target, message, wildcard="*.*", seldir=False, getbasedir=None, callback=None, winsize=False):
    """ファイルまたはディレクトリを選択する
    ダイアログを表示するボタンを生成する。
    parent: ボタンの親パネル。
    target: 選択結果を格納するコントロール。
    message: 選択時に表示されるメッセージ。
    wildcard: 選択対象の定義。
    seldir: Trueの場合はディレクトリの選択を行う。
    getbasedir: 相対パスを扱う場合は基準となるパスを返す関数。
    """
    def OnOpen(event):
        fpath = target.GetValue()
        dpath = fpath
        if getbasedir and not os.path.isabs(dpath):
            dpath = os.path.join(getbasedir(), dpath)
        if seldir:
            dlg = wx.DirDialog(parent.TopLevelParent, message, dpath, wx.DD_DIR_MUST_EXIST)
            if dlg.ShowModal() == wx.ID_OK:
                dpath = dlg.GetPath()
                if getbasedir:
                    base = getbasedir()
                    dpath2 = cw.util.relpath(dpath, base)
                    if not dpath2.startswith(".." + os.path.sep):
                        dpath = dpath2
                target.SetValue(dpath)
                if callback:
                    callback(dpath)
        else:
            dpath = os.path.dirname(fpath)
            fpath = os.path.basename(fpath)
            dlg = wx.FileDialog(parent.TopLevelParent, message, dpath, fpath, wildcard, wx.FD_OPEN)
            if dlg.ShowModal() == wx.ID_OK:
                fpath = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
                if getbasedir:
                    base = getbasedir()
                    fpath2 = cw.util.relpath(fpath, base)
                    if not fpath2.startswith(".." + os.path.sep):
                        fpath = fpath2
                target.SetValue(fpath)
                if callback:
                    callback(fpath)

    if winsize:
        size = (cw.wins(25), -1)
    else:
        size = (cw.ppis(25), -1)
    button = wx.Button(parent, size=size, label=u"...")
    parent.Bind(wx.EVT_BUTTON, OnOpen, button)
    return button

def adjust_position(frame):
    """frameの位置がいずれかのモニタ内に収まるように調節する。
    サイズ変更は行わない。
    """
    win = wx.Display.GetFromWindow(frame)
    if win == wx.NOT_FOUND: win = 0
    cax, cay, caw, cah = wx.Display(win).GetClientArea()
    caw += cax
    cah += cay
    x, y, w, h = frame.GetRect()
    if caw <= x + w: x = caw - w
    if cah <= y + h: y = cah - h
    if x < cax: x = cax
    if y < cay: y = cay
    frame.SetPosition((x, y))

class CWPyStaticBitmap(wx.Panel):
    """wx.StaticBitmapはアルファチャンネル付きの画像を
    正しく表示できない場合があるので代替する。
    複数重ねての表示にも対応。
    """
    def __init__(self, parent, cid, bmps, bmps_bmpdepthkey, size=None, infos=None, ss=None):
        if not size and bmps:
            w = 0
            h = 0
            for bmp in bmps:
                s = bmp.GetSize()
                w = max(w, s[0])
                h = max(h, s[1])
            size = (w, h)
        wx.Panel.__init__(self, parent, cid, size=size)
        self.bmps = bmps
        self.bmps_bmpdepthkey = bmps_bmpdepthkey
        self.infos = infos
        self.ss = ss
        self._bind()

    def _bind(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        for i, (bmp, bmpdepthkey) in enumerate(zip(self.bmps, self.bmps_bmpdepthkey)):
            if self.infos:
                info = self.infos[i]
                w, h = bmpdepthkey.GetSize()
                scr_scale = bmpdepthkey.scr_scale if hasattr(bmpdepthkey, "scr_scale") else 1
                w /= scr_scale
                h /= scr_scale
                baserect = info.calc_basecardposition_wx((w, h), noscale=True,
                                                         basecardtype="LargeCard",
                                                         cardpostype="NotCard")
                baserect = self.ss(baserect)
                x, y = baserect.x, baserect.y
            else:
                x, y = 0, 0
            cw.imageretouch.wxblit_2bitbmp_to_card(dc, bmp, x, y, True, bitsizekey=bmpdepthkey)

    def SetBitmap(self, bmps, bmps_bmpdepthkey, infos=None):
        self.bmps = bmps
        self.bmps_bmpdepthkey = bmps_bmpdepthkey
        self.infos = infos
        self.Refresh()

    def GetBitmap(self, bmps):
        return self.bmps

def abbr_longstr(dc, text, w):
    """ClientDCを使って長い文字列を省略して末尾に三点リーダを付ける。
    dc: ClientDC
    text: 編集対象の文字列
    w: 目標文字列長(pixel)
    """
    if w <= 0 and text:
        if dc.GetTextExtent(text)[0] <= dc.GetTextExtent(u"...")[0]:
            return text
        else:
            return u"..."
    width = dc.GetTextExtent(text)[0]
    if width > w:
        while text and dc.GetTextExtent(text + u"...")[0] > w:
            text = text[:-1]
        text += u"..."
    return text

class CheckableListCtrl(wx.ListCtrl,
                        wx.lib.mixins.listctrl.CheckListCtrlMixin,
                        wx.lib.mixins.listctrl.ListCtrlAutoWidthMixin):
    """チェックボックス付きのリスト。"""
    def __init__(self, parent, cid, size, style, colpos=0):
        wx.ListCtrl.__init__(self, parent, cid, size=size, style=style|wx.LC_NO_HEADER)
        wx.lib.mixins.listctrl.CheckListCtrlMixin.__init__(self)
        wx.lib.mixins.listctrl.ListCtrlAutoWidthMixin.__init__(self)
#        w, h = self.GetImageList(wx.IMAGE_LIST_SMALL).GetSize(0)
        for i in xrange(colpos+1):
            self.InsertColumn(i, u"")

        self.InsertImageStringItem(0, u"", 0)
        rect = self.GetItemRect(0, wx.LIST_RECT_LABEL)
        self.SetColumnWidth(0, rect.x)
        self.DeleteAllItems()

        self.resizeLastColumn(0)

class CWBackCheckBox(wx.CheckBox):
    def __init__(self, parent, id, text):
        """CAUTIONリソースを背景とするチェックボックス。"""
        wx.CheckBox.__init__(self, parent, id, text)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        dc = wx.ClientDC(self)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle", pixelsize=cw.wins(15)))
        w, h = dc.GetTextExtent(text)
        bmp = cw.wins(cw.cwpy.rsrc.debugs_noscale["NOCHECK"])
        w += cw.wins(4) + bmp.GetWidth()
        h = max(h, bmp.GetHeight())
        self.SetMinSize((w, h))
        self.SetSize((w, h))

        self._nocheck = bmp
        self._check = cw.wins(cw.cwpy.rsrc.debugs_noscale["CHECK"])

        self.background = cw.cwpy.rsrc.dialogs["CAUTION"]

        self._bind()

    def _bind(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def set_background(self, bmp):
        self.background = bmp
        self.Refresh()

    def OnPaint(self, event):
        size = self.GetSize()
        basebmp = wx.EmptyBitmap(size[0], size[1])
        dc = wx.MemoryDC(basebmp)
        # background
        bmp = self.background
        csize = self.GetClientSize()
        fill_bitmap(dc, bmp, csize, ctrlpos=self.GetPosition())
        # checkbox
        if self.GetValue():
            bmp = self._check
        else:
            bmp = self._nocheck
        dc.DrawBitmap(bmp, cw.wins(2), (csize[1]-bmp.GetHeight()) / 2, True)
        # text
        dc.SetTextForeground(wx.BLACK)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle", pixelsize=cw.wins(15)))
        s = self.GetLabel()
        tsize = dc.GetTextExtent(s)
        dc.DrawText(s, bmp.GetWidth()+cw.wins(4), (csize[1]-tsize[1]) / 2)
        dc.SelectObject(wx.NullBitmap)

        dc = wx.PaintDC(self)
        dc.DrawBitmap(basebmp, 0, 0)

def add_sideclickhandlers(toppanel, leftbtn, rightbtn):
    """toppanelの左右の領域をクリックすると
    leftbtnまたはrightbtnのイベントが実行されるように
    イベントへのバインドを行う。
    """
    def _is_cursorinleft():
        rect = toppanel.GetClientRect()
        x, _y = toppanel.ScreenToClient(wx.GetMousePosition())
        return x < rect.x + rect.width / 4 and leftbtn.IsEnabled()

    def _is_cursorinright():
        rect = toppanel.GetClientRect()
        x, _y = toppanel.ScreenToClient(wx.GetMousePosition())
        return rect.x + rect.width / 4 * 3 < x and rightbtn.IsEnabled()

    def _update_mousepos():
        if _is_cursorinleft():
            toppanel.SetCursor(cw.cwpy.rsrc.cursors["CURSOR_BACK"])
        elif _is_cursorinright():
            toppanel.SetCursor(cw.cwpy.rsrc.cursors["CURSOR_FORE"])
        else:
            toppanel.SetCursor(cw.cwpy.rsrc.cursors["CURSOR_ARROW"])

    def OnMotion(evt):
        _update_mousepos()

    def OnLeftUp(evt):
        if _is_cursorinleft():
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, leftbtn.GetId())
            leftbtn.ProcessEvent(btnevent)
        elif _is_cursorinright():
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, rightbtn.GetId())
            rightbtn.ProcessEvent(btnevent)

    _update_mousepos()
    toppanel.Bind(wx.EVT_MOTION, OnMotion)
    toppanel.Bind(wx.EVT_LEFT_UP, OnLeftUp)

def set_acceleratortable(panel, seq):
    """panelにseqから生成したAcceleratorTableを設定する。
    """
    # テキスト入力欄に限り左右キーを取り除く
    seq2 = []
    for accel in seq:
        if not (accel[0] == wx.ACCEL_NORMAL and accel[1] in ( wx.WXK_LEFT, wx.WXK_RIGHT)):
            seq2.append(accel)

    accel1 = wx.AcceleratorTable(seq)
    accel2 = wx.AcceleratorTable(seq2)
    def recurse(widget):
        if isinstance(widget, (wx.TextCtrl, wx.Dialog, wx.Panel)):
            widget.SetAcceleratorTable(accel2)
        else:
            widget.SetAcceleratorTable(accel1)
        for child in widget.GetChildren():
            recurse(child)
    recurse(panel)

def adjust_dropdownwidth(choice):
    """wx.Choiceまたはwx.ComboBoxのドロップダウンリストの
    横幅を内容に合わせて広げる。
    """
    if sys.platform == "win32":
        # スクロールバーの幅
        scwidth = win32api.GetSystemMetrics(win32con.SM_CXVSCROLL)
        w = win32api.SendMessage(choice.GetHandle(), win32con.CB_GETDROPPEDWIDTH, 0, 0)

        # 項目ごとに幅を計算
        dc = wx.ClientDC(choice)
        for s in choice.GetItems():
            w = max(w, dc.GetTextExtent(s)[0] + cw.ppis(5) + scwidth)
        dc.SetFont(choice.GetFont())

        # モニタの横幅よりは大きくしない
        d = wx.Display.GetFromWindow(choice)
        if d == wx.NOT_FOUND: d = 0
        drect = wx.Display(d).GetClientArea()
        w = min(w, drect[2])

        # 幅を設定
        win32api.SendMessage(choice.GetHandle(), win32con.CB_SETDROPPEDWIDTH, w, 0)

class CWPyRichTextCtrl(wx.richtext.RichTextCtrl):
    def __init__(self, parent, id, text="", size=(-1, -1), style=0, searchmenu=False):
        wx.richtext.RichTextCtrl.__init__(self, parent, id, text, size=size, style=style)

        # popup menu
        self.popup_menu = wx.Menu()
        self.mi_copy = wx.MenuItem(self.popup_menu, wx.ID_COPY, u"コピー(&C)")
        self.mi_selectall = wx.MenuItem(self.popup_menu, wx.ID_SELECTALL, u"すべて選択(&A)")
        self.popup_menu.AppendItem(self.mi_copy)
        self.popup_menu.AppendItem(self.mi_selectall)

        self.Bind(wx.EVT_TEXT_URL, self.OnURL)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MENU, self.OnCopy, id=wx.ID_COPY)
        self.Bind(wx.EVT_MENU, self.OnSelectAll, id=wx.ID_SELECTALL)

        self.search_engines = []
        if searchmenu:
            if os.path.isfile(u"Data/SearchEngines.xml"):
                try:
                    class SearchEngine(object):
                        def __init__(self, parent, url, name):
                            self.parent = parent
                            self.url = url
                            menuid = wx.NewId()
                            self.mi = wx.MenuItem(self.parent.popup_menu, menuid, name)
                            self.parent.popup_menu.AppendItem(self.mi)
                            self.parent.Bind(wx.EVT_MENU, self.OnSearch, id=menuid)

                        def OnSearch(self, event):
                            try:
                                self.parent.go_url(self.url % self.parent.GetStringSelection())
                            except:
                                cw.util.print_ex(file=sys.stderr)

                    data = cw.data.xml2element(u"Data/SearchEngines.xml")
                    separator = False
                    for e in data:
                        if e.tag == u"SearchEngine":
                            if not separator:
                                separator = True
                                self.popup_menu.AppendSeparator()
                            url = e.getattr(".", "url", "")
                            name = e.text
                            if url and name:
                                self.search_engines.append(SearchEngine(self, url, name))
                except:
                    cw.util.print_ex(file=sys.stderr)

    def set_text(self, value, linkurl=False):
        # ZIPアーカイブのファイルエンコーディングと
        # 読み込むテキストファイルのエンコーディングが異なる場合、
        # エラーが出るので
        try:
            # 書き込みテスト FIXME: 書き込みに頼らないスマートな方法
            self.WriteText(value)

            value2 = value
        except Exception:
            value2 = cw.util.decode_text(value)

        # FIXME: URLクリック等でキャレットがURL上にある場合に
        # テキストを削除すると、URLリンク設定が以降追加された
        # 全テキストに適用される。
        # そのため、末尾がURLではない事を前提に、キャレットを
        # テキスト末尾へ移動してからクリアを行う。
        self.MoveEnd()
        self.Clear()

        # URLを検索して取り出し、テキストをリストに分割
        def get_urls(text):
            prog = re.compile(r"http(s)?://([\w\-]+\.)+[\w]+(/[\w\-./?%&=~#!]*)?")
            list = []

            url = prog.search(text)

            while url:
                if url.start() > 0:
                    list.append((text[:url.start()], False))
                list.append((url.group(0), True))
                text = text[url.end():]

                url = prog.search(text)

            if len(text) > 0:
                list.append((text, False))

            return list

        if linkurl:
            for v, url_flag in get_urls(value2):
                if url_flag:
                    self.BeginTextColour((255, 132, 0))
                    self.BeginUnderline()
                    self.BeginURL(v)
                else:
                    self.BeginTextColour(wx.WHITE)

                self.WriteText(v)

                if url_flag:
                    self.EndURL()
                    self.EndUnderline()
                self.EndTextColour()

            self.EndTextColour()
            if len(self.GetValue()) and not self.GetValue()[-1] in ("\n", "\r"):
                # 末尾が改行でない時は改行を加える
                # 前記した全文URL化バグへの対策でもある
                self.WriteText("\n")

        self.ShowPosition(0)

    def OnMouseWheel(self, event):
        y = self.GetScrollPos(wx.VERTICAL)

        if sys.platform == "win32":
            import win32gui
            SPI_GETDESKWALLPAPER = 104
            value = win32gui.SystemParametersInfo(SPI_GETDESKWALLPAPER)
            line_height = self.GetFont().GetPixelSize()[1]
            value *= line_height
            value /= self.GetScrollPixelsPerUnit()[1]
        else:
            value = cw.wins(4)

        if get_wheelrotation(event) > 0:
            self.Scroll(0, y - value)
        else:
            self.Scroll(0, y + value)
        self.Refresh()

    def OnMotion(self, event):
        # 画面外へのドラッグによるスクロール処理だが、マウス入力の分岐は不要？
        mousey = event.GetPosition()[1]
        y = self.GetScrollPos(wx.VERTICAL)
        if mousey < cw.wins(0):
            self.Scroll(0, y - cw.wins(4))
            self.Refresh()
        elif mousey > self.GetSize()[1]:
            self.Scroll(0, y + cw.wins(4))
            self.Refresh()

        event.Skip()

    def OnContextMenu(self, event):
        self.mi_copy.Enable(self.HasSelection())
        for searchengine in self.search_engines:
            searchengine.mi.Enable(self.HasSelection())
        self.PopupMenu(self.popup_menu)

    def OnCopy(self, event):
        self.Copy()

    def OnSelectAll(self, event):
        self.SelectAll()

    def go_url(self, url):
        try:
            webbrowser.open(url)
        except:
            s = u"「%s」が開けませんでした。インターネットブラウザが正常に関連付けされているか確認して下さい。" % url
            dlg = cw.dialog.message.ErrorMessage(self, s)
            cw.cwpy.frame.move_dlg(dlg)
            dlg.ShowModal()
            dlg.Destroy()

    def OnURL(self, event):
        # 文字列選択中はブラウザ起動しない
        if not self.HasSelection():
            self.go_url(event.GetString())


def get_wheelrotation(event):
    """マウスのホイールを横に倒した場合に
    取得できる回転量の値は直感と逆転しているので
    この関数をラッパとして反転した値を取得する。
    """
    if 3 <= wx.VERSION[0] and event.GetWheelAxis() == wx.MOUSE_WHEEL_HORIZONTAL:
        return -event.GetWheelRotation()
    else:
        return event.GetWheelRotation()


class CWTabArt(wx.lib.agw.aui.tabart.AuiDefaultTabArt):
    """wx.lib.agw.aui.tabart.AuiDefaultTabArtと同じように
    wx.lib.agw.aui.AuiNotebookのタブを描画するが、
    テキストのみ左寄せから中央寄せに変更する。
    """
    def DrawTab(self, dc, wnd, page, in_rect, close_button_state, paint_control=False):
        # テキストを一旦空にして背景だけ描画させる
        caption = page.caption
        page.caption = u""
        r = super(CWTabArt, self).DrawTab(dc, wnd, page, in_rect, close_button_state, paint_control)
        page.caption = caption
        # テキストを描画
        te = dc.GetTextExtent(page.caption)
        rect = r[0]
        dc.DrawText(page.caption, rect.X + (rect.Width - te[0]) / 2, in_rect.Y + (in_rect.Height - te[1]) / 2)
        return r


#-------------------------------------------------------------------------------
#  スレッド関係
#-------------------------------------------------------------------------------

"""
@synclock(_lock)
def function():
    ...
のように、ロックオブジェクトを指定して
特定関数・メソッドの排他制御を行う。
"""
def synclock(l):
    def synclock(f):
        def acquire(*args, **kw):
            l.acquire()
            try:
                return f(*args, **kw)
            finally:
                l.release()
        return acquire
    return synclock

#-------------------------------------------------------------------------------
#  ショートカット関係
#-------------------------------------------------------------------------------

# CoInitialize()を呼び出し終えたスレッドのset
_cominit_table = set()

def _co_initialize():
    """スレッドごとにCoInitialize()を呼び出す。"""
    global _cominit_table
    if sys.platform <> "win32":
        return
    thr = threading.currentThread()
    if thr in _cominit_table:
        return # 呼び出し済み
    pythoncom.CoInitialize()
    _cominit_table.add(thr)
    # 終了したスレッドがあれば除去
    for thr2 in _cominit_table.copy():
        if not thr2.isAlive():
            _cominit_table.remove(thr2)

def get_linktarget(fpath):
    """fileがショートカットだった場合はリンク先を、
    そうでない場合はfileを返す。
    """
    if sys.platform <> "win32" or not fpath.lower().endswith(".lnk") or not os.path.isfile(fpath):
        return fpath

    _co_initialize()
    shortcut = pythoncom.CoCreateInstance(win32shell.CLSID_ShellLink, None,
                                          pythoncom.CLSCTX_INPROC_SERVER,
                                          win32shell.IID_IShellLink)
    try:
        encoding = sys.getfilesystemencoding()
        STGM_READ = 0x00000000
        shortcut.QueryInterface(pythoncom.IID_IPersistFile).Load(fpath.encode(encoding), STGM_READ)
        fpath = shortcut.GetPath(win32shell.SLGP_UNCPRIORITY)[0].decode(encoding)
    except Exception:
        print_ex()
        return fpath
    return join_paths(fpath)

def create_link(shortcutpath, targetpath):
    """targetpathへのショートカットを
    shortcutpathに作成する。
    """
    if sys.platform <> "win32":
        return
    dpath = os.path.dirname(shortcutpath)
    if not os.path.exists(dpath):
        os.makedirs(dpath)

    _co_initialize()
    targetpath = os.path.abspath(targetpath)
    shortcut = pythoncom.CoCreateInstance(win32shell.CLSID_ShellLink, None,
                                          pythoncom.CLSCTX_INPROC_SERVER,
                                          win32shell.IID_IShellLink)
    encoding = sys.getfilesystemencoding()
    shortcut.SetPath(targetpath.encode(encoding))
    shortcut.QueryInterface(pythoncom.IID_IPersistFile).Save(shortcutpath.encode(encoding), 0)

#-------------------------------------------------------------------------------
#  パフォーマンスカウンタ
#-------------------------------------------------------------------------------

dictimes = {}
times = [0.0] * 1024
timer = 0.0

def t_start():
    global timer
    timer = time.time()

def t_end(index):
    global times, timer
    times[index] += time.time() - timer
    timer = time.time()

def td_end(key):
    global dictimes, timer
    if key in dictimes:
        dictimes[key] += time.time() - timer
    else:
        dictimes[key] = time.time() - timer
    timer = time.time()

def t_reset():
    global times, dictimes
    times = map(lambda v: 0, times)
    dictimes.clear()

def t_print():
    global times, dictimes
    lines = []
    for i, t in enumerate(times):
        if 0 < t:
            s = u"time[%s] = %s" % (i, t)
            lines.append(s)
            print s
    for key, t in dictimes.iteritems():
        if 0 < t:
            s = u"time[%s] = %s" % (key, t)
            lines.append(s)
            print s
    if lines:
        with open("performance.txt", "w") as f:
            f.write(u"\n".join(lines))
            f.flush()
            f.close()

#-------------------------------------------------------------------------------
#  同時起動制御
#-------------------------------------------------------------------------------

_lock_mutex = threading.Lock()
_mutex = []
if sys.platform <> "win32":
    import fcntl

@synclock(_lock_mutex)
def create_mutex(dpath):
    global _mutex
    if not os.path.isabs(dpath):
        dpath = os.path.abspath(dpath)
    dpath = os.path.normpath(dpath)
    dpath = os.path.normcase(dpath)
    name = hashlib.md5(buffer(dpath)).hexdigest()

    # 二重起動防止 for Windows
    if sys.platform == "win32":
        name = u"CardWirthPy/%s\0" % (name)
        name = name.encode("utf-16")
        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, 1, name)
        err = kernel32.GetLastError()

        if err == ERROR_ALREADY_EXISTS or handle is None:
            if handle:
                kernel32.ReleaseMutex(handle)
                kernel32.CloseHandle(handle)
            handle = None
        else:
            _mutex.append((handle, name))
            return True
    else:
        # Posix
        name = u"Data/Temp/Global/LockFiles/%s" % (name)
        try:
            if not os.path.isfile(name):
                dpath = os.path.dirname(name)
                if not os.path.isdir(dpath):
                    os.makedirs(dpath)
            f = open(name, "wb")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _mutex.append((f, name))
            return True
        except IOError:
            return False

    return False

@synclock(_lock_mutex)
def exists_mutex(dpath):
    global _mutex
    if not os.path.isabs(dpath):
        dpath = os.path.abspath(dpath)
    dpath = os.path.normpath(dpath)
    dpath = os.path.normcase(dpath)
    name = hashlib.md5(buffer(dpath)).hexdigest()

    if sys.platform == "win32":
        name = u"CardWirthPy/%s\0" % (name)
        name = name.encode("utf-16")
        MUTEX_ALL_ACCESS = 0x001F0001
        _SYNCHRONIZE = 0x00100000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenMutexW(MUTEX_ALL_ACCESS, 0, name)
        if handle and not name in map(lambda m: m[1], _mutex):
            kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)
            return True
        elif handle:
            kernel32.CloseHandle(handle)

        return False
    else:
        # Posix
        name = u"Data/Temp/Global/LockFiles/%s" % (name)
        if name in map(lambda m: m[1], _mutex):
            return False
        try:
            if not os.path.isfile(name):
                dpath = os.path.dirname(name)
                if not os.path.isdir(dpath):
                    os.makedirs(dpath)
            with open(name, "wb") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                f.close()
            remove(name)
            return False
        except IOError:
            return True

@synclock(_lock_mutex)
def release_mutex():
    global _mutex
    if _mutex:
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(_mutex[-1][0])
            kernel32.CloseHandle(_mutex[-1][0])
        else:
            fcntl.flock(_mutex[-1][0].fileno(), fcntl.LOCK_UN)
            _mutex[-1][0].close()
            remove(_mutex[-1][1])
        del _mutex[-1]

@synclock(_lock_mutex)
def clear_mutex():
    global _mutex
    for mutex, name in _mutex:
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(mutex)
            kernel32.CloseHandle(mutex)
        else:
            f = mutex
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()
            remove(name)
    _mutex = []

def main():
    pass

if __name__ == "__main__":
    main()
