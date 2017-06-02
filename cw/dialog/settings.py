#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import itertools
import wx
import wx.grid
import pygame

import cw
import editscenariodb


# build_exe.pyによって作られる一時モジュール
# cw.versioninfoからビルド時間の情報を得る
try:
    import versioninfo
except ImportError:
    versioninfo = None

def _settings_width():
    return cw.ppis(250)


def create_versioninfo(parent):
    """バージョン情報を表示するwx.TextCtrlを生成する。"""
    s = "%s %s" % (cw.APP_NAME, ".".join(map(lambda a: str(a), cw.APP_VERSION)))
    if versioninfo:
        s = "%s\nBuild: %s" % (s, versioninfo.build_datetime)
    parent.versioninfo = wx.TextCtrl(parent, -1, s, size=(-1, -1), style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_NO_VSCROLL|wx.NO_BORDER)
    parent.versioninfo.SetBackgroundColour(parent.GetBackgroundColour())
    dc = wx.ClientDC(parent.versioninfo)
    w, h, _lh = dc.GetMultiLineTextExtent(s)
    parent.versioninfo.SetMinSize((w + cw.ppis(15), h))


def apply_levelupparams(can_levelup):
    """レベル調節に関する状況が変わった時に呼び出され、
    レベルアップ不可→可能になった時にレベル上昇処理を行う。
    """
    def check_levelup(can_levelup_old):
        if cw.cwpy.is_playingscenario():
            return

        can_levelup = not (cw.cwpy.is_debugmode() and cw.cwpy.setting.no_levelup_in_debugmode)
        if not can_levelup_old and can_levelup:
            # レベルアップが可能な設定になったので
            # レベル上昇処理を行う
            for pcard in cw.cwpy.get_pcards():
                if 0 < pcard.check_level():
                    pcard.adjust_level(False)
    cw.cwpy.exec_func(check_levelup, can_levelup)


class SettingsDialog(wx.Dialog):
    def __init__(self, parent):
        """設定ダイアログ。
        """
        cw.cwpy.frame.filter_event = self.OnFilterEvent
        self.panel = None
        wx.Dialog.__init__(self, parent, -1, cw.APP_NAME + u"の設定(F2)")
        self.panel = SettingsPanel(self)

        self.cwpy_debug = True # このダイアログではスクリーンショットの撮影を行わない

        self._bind()
        self._do_layout()

    def _bind(self):
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(self.panel, 1, wx.EXPAND, cw.ppis(0))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnFilterEvent(self, event):
        if not self:
            return False
        if event.GetEventType() in (wx.EVT_TEXT.typeId,
                                    wx.EVT_SPINCTRL.typeId,
                                    wx.EVT_COMBOBOX.typeId,
                                    wx.EVT_CHECKBOX.typeId,
                                    wx.EVT_SLIDER.typeId,
                                    wx.EVT_CHOICE.typeId,
                                    wx.EVT_COLOURPICKER_CHANGED.typeId,
                                    wx.grid.EVT_GRID_CELL_CHANGE.typeId,
                                    wx.grid.EVT_GRID_EDITOR_SHOWN.typeId):
            obj = event.GetEventObject()
            if wx.grid.EVT_GRID_EDITOR_SHOWN.typeId and isinstance(obj, wx.grid.Grid):
                editor = obj.GetCellEditor(event.GetRow(), event.GetCol())
                if isinstance(editor, wx.grid.GridCellBoolEditor):
                    self.applied()
            elif isinstance(obj, wx.Window) and obj.GetTopLevelParent() is self:
                self.applied()
        return False

    def applied(self):
        if self.panel:
            self.panel.btn_apply.Enable()

    def clear_applied(self):
        if self.panel:
            self.panel.btn_apply.Disable()

    def OnClose(self, event):
        cw.cwpy.frame.filter_event = None
        self.panel.close()
        self.Destroy()
        #ここで数秒応答不能になる(12.3でも確認)

class SettingsPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, pos=(-1024, -1024))
        self.SetDoubleBuffered(True)
        self.Hide()

        self.note = wx.Notebook(self, style=wx.NB_FIXEDWIDTH)
        self.pane_gene = GeneralSettingPanel(self.note)
        self.pane_draw = DrawingSettingPanel(self.note, for_local=False, get_localsettings=None,
                                             use_copybase=True)
        self.pane_sound = AudioSettingPanel(self.note)
        self.pane_font = FontSettingPanel(self.note, for_local=False, get_localsettings=None,
                                          use_copybase=True)
        self.pane_scenario = ScenarioSettingPanel(self.note)
        self.pane_ui = UISettingPanel(self.note)
        self.note.AddPage(self.pane_gene, u"一般")
        self.note.AddPage(self.pane_draw, u"描画")
        self.note.AddPage(self.pane_sound, u"音響")
        self.note.AddPage(self.pane_font, u"フォント")
        self.note.AddPage(self.pane_scenario, u"シナリオ")
        self.note.AddPage(self.pane_ui, u"その他")
        self.pane_gene.skin.pane_scenario = self.pane_scenario

        create_versioninfo(self)

        self.btn_dflt = wx.Button(self, wx.ID_DEFAULT, u"デフォルト")
        h = self.btn_dflt.GetBestSize()[1]

        self.btn_save = wx.BitmapButton(self, -1, cw.cwpy.rsrc.debugs["SETTINGS_SAVE"])
        self.btn_save.SetToolTipString(u"設定の保存")
        self.btn_save.SetMinSize((cw.ppis(32), h))
        self.btn_load = wx.BitmapButton(self, -1, cw.cwpy.rsrc.debugs["SETTINGS_LOAD"])
        self.btn_load.SetToolTipString(u"設定の読み込み")
        self.btn_load.SetMinSize((cw.ppis(32), h))

        self.btn_ok = wx.Button(self, wx.ID_OK, u"OK")
        self.btn_apply = wx.Button(self, wx.ID_APPLY, u"適用")
        self.btn_cncl = wx.Button(self, wx.ID_CANCEL, u"キャンセル")

        self.note.SetSelection(cw.cwpy.settingtab)

        self.load(cw.cwpy.setting)

        self.btn_apply.Disable()

        self._do_layout()
        self._bind()
        self.Show()

    def _bind(self):
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_BUTTON, self.OnOk, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnApply, id=wx.ID_APPLY)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnDefault, id=wx.ID_DEFAULT)
        self.Bind(wx.EVT_BUTTON, self.OnSave, id=self.btn_save.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnLoad, id=self.btn_load.GetId())

    def load(self, setting):
        self.pane_gene.load(setting)
        self.pane_draw.load(setting, setting.local)
        self.pane_sound.load(setting)
        self.pane_font.load(setting, setting.local)
        self.pane_scenario.load(setting)
        self.pane_ui.load(setting)

    def OnSave(self, event):
        dlg = wx.FileDialog(self.GetTopLevelParent(), u"設定ファイルの保存",
                            "", u"新規設定.wssx", u"CardWirthPy設定ファイル (*.wssx)|*.wssx|XMLドキュメント (*.xml)|*.xml|すべてのファイル (*.*)|*.*",
                            wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            fpath = dlg.GetPath()
            try:
                setting = cw.setting.Setting(init=False)
                self.apply(setting)
                cw.xmlcreater.create_settings(setting, writeplayingdata=False, fpath=fpath)
            except:
                cw.util.print_ex()
                s = u"%sの保存に失敗しました。" % (os.path.basename(fpath))
                wx.MessageBox(s, u"メッセージ", wx.OK|wx.ICON_WARNING, self.GetTopLevelParent())

    def OnLoad(self, event):
        dlg = wx.FileDialog(self.GetTopLevelParent(), u"設定ファイルの読み込み",
                            "", "", u"CardWirthPy設定ファイル (*.wssx)|*.wssx|XMLドキュメント (*.xml)|*.xml|すべてのファイル (*.*)|*.*",
                            wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            fpath = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            try:
                setting = cw.setting.Setting(loadfile=fpath)
                self.load(setting)
                self.GetTopLevelParent().applied()
            except:
                cw.util.print_ex()
                s = u"%sの読み込みに失敗しました。" % (os.path.basename(fpath))
                wx.MessageBox(s, u"メッセージ", wx.OK|wx.ICON_WARNING, self.GetTopLevelParent())

    def OnDefault(self, event):
        selpane = self.note.GetSelection()
        if selpane == 0:
            self.pane_gene.init_values(cw.cwpy.setting)
        elif selpane == 1:
            self.pane_draw.init_values(cw.cwpy.setting, cw.cwpy.setting.local)
        elif selpane == 2:
            self.pane_sound.init_values(cw.cwpy.setting)
        elif selpane == 3:
            self.pane_font.init_values(cw.cwpy.setting, cw.cwpy.setting.local)
        elif selpane == 4:
            # スキン毎のシナリオ開始位置の設定は変更しない
            self.pane_scenario.init_values(cw.cwpy.setting)
        elif selpane == 5:
            self.pane_ui.init_values(cw.cwpy.setting)

        self.GetTopLevelParent().applied()

    def OnOk(self, event):
        self.apply(cw.cwpy.setting)

        # FIXME: クローズしながらスキンを切り替えると時々エラーになる
        #        原因不明の不具合があるので、ダイアログのクローズを遅延する
        def func(self):
            def func(self):
                if self:
                    self.Parent.Close()
            cw.cwpy.frame.exec_func(func, self)
        cw.cwpy.exec_func(func, self)
        self.Parent.Disable()

    def OnApply(self, event):
        self.apply(cw.cwpy.setting)

    def apply(self, setting):
        #設定したオプションの反映
        update = (setting == cw.cwpy.setting)

        # 設定変更前はレベル上昇が可能な状態だったか
        can_levelup = not (cw.cwpy.is_debugmode() and cw.cwpy.setting.no_levelup_in_debugmode)
        updatestatusbar = False # ステータスバーの更新が必要か

        # フォント
        flag_fontupdate, updatecardimg, updatemcardimg, updatemessage = self.pane_font.apply_localsettings(setting.local)

        # 一般
        if update:
            value = self.pane_gene.cb_debug.GetValue()
            if not value == cw.cwpy.setting.debug:
                cw.cwpy.exec_func(cw.cwpy.set_debug, value)

        value = self.pane_gene.sc_initmoneyamount.GetValue()
        setting.initmoneyamount = value
        value = self.pane_gene.cb_initmoneyisinitialcash.GetValue()
        setting.initmoneyisinitialcash = value
        value = self.pane_gene.cb_autosavepartyrecord.GetValue()
        setting.autosave_partyrecord = value
        #value = self.pane_gene.cb_overwritepartyrecord.GetValue()
        #setting.overwrite_partyrecord = value
        value = self.pane_gene.tx_ssinfoformat.GetValue()
        setting.ssinfoformat = value
        value = self.pane_gene.tx_ssfnameformat.GetValue()
        setting.ssfnameformat = value
        value = self.pane_gene.tx_cardssfnameformat.GetValue()
        setting.cardssfnameformat = value
        value = self.pane_gene.ch_ssinfocolor.GetSelection()
        if value == 1:
            setting.ssinfofontcolor = (255, 255, 255)
            setting.ssinfobackcolor = (0, 0, 0)
        else:
            setting.ssinfofontcolor = (0, 0, 0)
            setting.ssinfobackcolor = (255, 255, 255)
        value = self.pane_gene.tx_ssinfobackimage.GetValue()
        setting.ssinfobackimage = value
        value = self.pane_gene.ch_messagelog_type.GetSelection()
        if value == 0:
            value = cw.setting.LOG_SINGLE
        elif value == 1:
            value = cw.setting.LOG_LIST
        elif value == 2:
            value = cw.setting.LOG_COMPRESS
        setting.messagelog_type = value
        value = self.pane_gene.ch_startupscene.GetSelection()
        if value == 0:
            value = cw.setting.OPEN_TITLE
        elif value == 1:
            value = cw.setting.OPEN_LAST_BASE
        setting.startupscene = value
        value = self.pane_gene.sc_backlogmax.GetValue()
        if value <> setting.backlogmax:
            if update:
                def func(backlogmax):
                    cw.cwpy.set_backlogmax(backlogmax)
                cw.cwpy.exec_func(func, value)
                updatestatusbar = True
            else:
                setting.backlogmax = value

        # 拡大倍率
        self.pane_gene.expand.apply_expand(setting)

        # 描画
        updatebg = False
        value = self.pane_draw.cb_smooth_bg.GetValue()
        if setting.smoothscale_bg <> value:
            updatebg = True
            setting.smoothscale_bg = value

        value = self.pane_draw.cb_smoothing_card_up.GetValue()
        if setting.smoothing_card_up <> value:
            updatemcardimg = True
            updatecardimg = True
            setting.smoothing_card_up = value
        value = self.pane_draw.cb_smoothing_card_down.GetValue()
        if setting.smoothing_card_down <> value:
            updatemcardimg = True
            updatecardimg = True
            setting.smoothing_card_down = value

        self.pane_draw.speed.apply_speed(setting)

        # オーディオ
        value = self.pane_sound.cb_playbgm.GetValue()
        setting.play_bgm = value
        value = self.pane_sound.cb_playsound.GetValue()
        setting.play_sound = value
        value = self.pane_sound.sl_master.GetValue()
        value = cw.setting.Setting.wrap_volumevalue(value)
        setting.vol_master = value
        value = self.pane_sound.sl_sound.GetValue()
        value = cw.setting.Setting.wrap_volumevalue(value)
        setting.vol_sound = value
        value = self.pane_sound.sl_midi.GetValue()
        value = cw.setting.Setting.wrap_volumevalue(value)
        setting.vol_midi = value
        value = self.pane_sound.sl_music.GetValue()
        value = cw.setting.Setting.wrap_volumevalue(value)
        setting.vol_bgm = value
        value = self.pane_sound.sl_master.GetValue()
        value = cw.setting.Setting.wrap_volumevalue(value)
        setting.vol_master = value
        if update:
            volume = int(setting.vol_master*100)
            for music in cw.cwpy.music:
                if not cw.cwpy.frame.IsIconized():
                    music.set_mastervolume(volume)
                music.set_volume()
            for sound in cw.cwpy.lastsound_scenario:
                if sound:
                    sound.set_mastervolume(True, volume)
                    sound.set_volume(True)
            if cw.cwpy.lastsound_system:
                cw.cwpy.lastsound_system.set_mastervolume(False, volume)
                cw.cwpy.lastsound_system.set_volume(False)
        soundfonts = []
        for index in xrange(self.pane_sound.list_soundfont.GetItemCount()):
            soundfont = self.pane_sound.list_soundfont.GetItemText(index)
            use = self.pane_sound.list_soundfont.IsChecked(index)
            soundfonts.append((soundfont, use))
        if setting.soundfonts <> soundfonts:
            sfonts1 = [sfont[0] for sfont in soundfonts if sfont[1]]
            sfonts2 = [sfont[0] for sfont in setting.soundfonts if sfont[1]]
            setting.soundfonts = soundfonts
            if update and sfonts1 <> sfonts2:
                def func():
                    if cw.bassplayer.is_alivable():
                        cw.bassplayer.dispose_bass()
                    if pygame.mixer.get_init():
                        pygame.mixer.quit()

                    if sfonts1:
                        cw.bassplayer.init_bass(sfonts1)
                    else:
                        cw.util.sdlmixer_init()

                    if bool(sfonts1) <> bool(sfonts2):
                        cw.cwpy.init_sounds()
                    for music in cw.cwpy.music:
                        music.play(music.path, updatepredata=False, restart=True)

                cw.cwpy.exec_func(func)

        # 配色(メッセージ)
        r_updatemessage, updatecurtain, updatefullscreen = self.pane_draw.apply_localsettings(setting.local)
        updatemessage |= r_updatemessage

        if update and updatemessage:
            cw.cwpy.exec_func(cw.cwpy.update_messagestyle)

        if update and updatecurtain:
            cw.cwpy.exec_func(cw.cwpy.update_curtainstyle)

        if update and updatefullscreen:
            def func1():
                cw.cwpy.update_fullscreenbackground()

            cw.cwpy.exec_func(func1)

        # スキン
        if update:
            if self.pane_gene.skin.apply_skin(flag_fontupdate):
                updatecardimg = False
                updatemcardimg = False
                updatebg = False

        # レベル調節
        if update:
            apply_levelupparams(can_levelup)

        # シナリオ
        value = self.pane_scenario.tx_editor.GetValue()
        setting.editor = value
        value = self.pane_scenario.cb_selectscenariofromtype.GetValue()
        setting.selectscenariofromtype = value
        value = self.pane_scenario.cb_show_paperandtree.GetValue()
        setting.show_paperandtree = value
        if setting.show_paperandtree:
            setting.show_scenariotree = False
        value = self.pane_scenario.cb_write_playlog.GetValue()
        if value <> setting.write_playlog:
            setting.write_playlog = value
            def func():
                cw.cwpy.advlog.enable(setting.write_playlog)
            cw.cwpy.exec_func(func)
        value = self.pane_scenario.tx_filer_dir.GetValue()
        setting.filer_dir = value
        value = self.pane_scenario.tx_filer_file.GetValue()
        setting.filer_file = value

        setting.folderoftype = []
        for row in xrange(self.pane_scenario.grid_folderoftype.GetNumberRows() - 1):
            skintype = self.pane_scenario.grid_folderoftype.GetCellValue(row, 0)
            folder = self.pane_scenario.grid_folderoftype.GetCellValue(row, 1)
            setting.folderoftype.append((skintype, folder))
        value = self.pane_scenario.cb_show_debuglogdialog.GetValue()
        setting.show_debuglogdialog = value
        value = self.pane_scenario.cb_open_lastscenario.GetValue()
        setting.open_lastscenario = value
        value = self.pane_scenario.cb_oldf9.GetValue()
        setting.enable_oldf9 = value

        # 詳細
        value = self.pane_ui.cb_can_skipwait.GetValue()
        setting.can_skipwait = value
        value = self.pane_ui.cb_can_skipanimation.GetValue()
        setting.can_skipanimation = value
        value = self.pane_ui.cb_can_skipwait_with_wheel.GetValue()
        setting.can_skipwait_with_wheel = value
        value = self.pane_ui.cb_can_forwardmessage_with_wheel.GetValue()
        setting.can_forwardmessage_with_wheel = value
        value = self.pane_ui.cb_wheel_movefocus.GetValue()
        setting.wheel_movefocus = value

        value = self.pane_ui.cb_can_repeatlclick.GetValue()
        setting.can_repeatlclick = value
        value = self.pane_ui.cb_autoenter_on_sprite.GetValue()
        setting.autoenter_on_sprite = value

        value = self.pane_ui.ch_quickdeal.GetSelection()
        if value == 2:
            setting.quickdeal = setting.all_quickdeal = False
        elif value == 0:
            setting.quickdeal = setting.all_quickdeal = True
        else:
            setting.quickdeal = True
            setting.all_quickdeal = False
        value = self.pane_ui.cb_showallselectedcards.GetValue()
        setting.show_allselectedcards = value
        value = self.pane_ui.cb_showstatustime.GetValue()
        if setting.show_statustime <> value:
            setting.show_statustime = value
            updatecardimg = True
        value = self.pane_ui.cb_show_cardkind.GetValue()
        if setting.show_cardkind <> value:
            setting.show_cardkind = value
            updatemcardimg = True
        value = self.pane_ui.cb_show_premiumicon.GetValue()
        if setting.show_premiumicon <> value:
            setting.show_premiumicon = value
            updatemcardimg = True

        value = self.pane_ui.cb_showlogwithwheelup.GetValue()
        if value:
            setting.wheelup_operation = cw.setting.WHEEL_SHOWLOG
        else:
            setting.wheelup_operation = cw.setting.WHEEL_SELECTION

        value = self.pane_ui.cb_show_btndesc.GetValue()
        setting.show_btndesc = value
        value = self.pane_ui.cb_statusbarmask.GetValue()
        if value <> setting.statusbarmask:
            setting.statusbarmask = value
            updatestatusbar = True
        value = self.pane_ui.cb_blink_statusbutton.GetValue()
        setting.blink_statusbutton = value
        value = self.pane_ui.cb_blink_partymoney.GetValue()
        setting.blink_partymoney = value

        value = self.pane_ui.cb_show_addctrlbtn.GetValue()
        setting.show_addctrlbtn = value
        value = self.pane_ui.cb_show_experiencebar.GetValue()
        setting.show_experiencebar = value
        value = self.pane_ui.cb_cautionbeforesaving.GetValue()
        setting.caution_beforesaving = value

        value = self.pane_ui.ch_showbackpackcard.GetSelection()
        if value == 2:
            setting.show_backpackcard = setting.show_backpackcardatend = False
        elif value == 1:
            setting.show_backpackcard = setting.show_backpackcardatend = True
        else:
            setting.show_backpackcard = True
            setting.show_backpackcardatend = False
        value = self.pane_ui.cb_can_clicksidesofcardcontrol.GetValue()
        setting.can_clicksidesofcardcontrol = value
        value = self.pane_ui.cb_revertcardpocket.GetValue()
        setting.revert_cardpocket = value
        value = self.pane_ui.ch_confirm_beforesaving.GetSelection()
        if value == 2:
            setting.confirm_beforesaving = cw.setting.CONFIRM_BEFORESAVING_NO
        elif value == 1:
            setting.confirm_beforesaving = cw.setting.CONFIRM_BEFORESAVING_BASE
        else:
            setting.confirm_beforesaving = cw.setting.CONFIRM_BEFORESAVING_YES
        value = self.pane_ui.cb_showsavedmessage.GetValue()
        setting.show_savedmessage = value
        value = self.pane_ui.cb_confirmbeforeusingcard.GetValue()
        setting.confirm_beforeusingcard = value
        value = self.pane_ui.cb_confirm_dumpcard.GetValue()
        setting.confirm_dumpcard = value
        value = self.pane_ui.cb_noticeimpossibleaction.GetValue()
        setting.noticeimpossibleaction = value
        value = self.pane_ui.cb_showroundautostartbutton.GetValue()
        if setting.show_roundautostartbutton <> value:
            setting.show_roundautostartbutton = value
            updatestatusbar = True
            if update and not setting.show_roundautostartbutton:
                def func():
                    if cw.cwpy.is_playingscenario():
                        cw.cwpy.sdata.autostart_round = False
                cw.cwpy.exec_func(func)
        value = self.pane_ui.cb_showautobuttoninentrydialog.GetValue()
        setting.show_autobuttoninentrydialog = value
        #value = self.pane_ui.cb_protect_staredcard.GetValue()
        #setting.protect_staredcard = value
        value = self.pane_ui.cb_protect_premiercard.GetValue()
        setting.protect_premiercard = value

        # 背景の更新
        if update and updatebg:
            def func():
                if cw.cwpy.is_playingscenario():
                    cw.cwpy.sdata.resource_cache = {}
                cw.cwpy.background.reload()
            cw.cwpy.exec_func(func)

        # イメージの更新
        if update and (updatecardimg or updatemcardimg):
            def func():
                for ccard in cw.cwpy.get_pcards("unreversed"):
                    ccard.update_image()
                if updatemcardimg:
                    for mcard in itertools.chain(cw.cwpy.get_mcards()):
                        if mcard.is_initialized():
                            mcard.update_scale()
                else:
                    for mcard in itertools.chain(cw.cwpy.get_ecards("unreversed"),\
                                                  cw.cwpy.get_fcards("unreversed")):
                        if mcard.is_initialized():
                            mcard.update_image()
            cw.cwpy.exec_func(func)

        # ステータスバーの更新
        if update and updatestatusbar:
            def func():
                cw.cwpy.statusbar.change(cw.cwpy.statusbar.showbuttons)
            cw.cwpy.exec_func(func)

        if update and cw.cwpy.is_showingdebugger() and cw.cwpy.frame.debugger:
            cw.cwpy.frame.debugger.refresh_tools()

        self.GetTopLevelParent().clear_applied()

    def OnClose(self, event):
        self.Parent.Close()

    def close(self):
        cw.cwpy.settingtab = self.note.GetSelection()

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)

        sizer_btn.Add(self.versioninfo, 0, wx.ALIGN_CENTER, cw.ppis(0))
        sizer_btn.AddStretchSpacer(1)
        sizer_btn.Add(self.btn_dflt, 0, wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER, cw.ppis(5))
        sizer_btn.Add(cw.ppis((10, 0)), 0, 0, cw.ppis(0))
        sizer_btn.Add(self.btn_save, 0, wx.ALIGN_CENTER, cw.ppis(0))
        sizer_btn.Add(self.btn_load, 0, wx.LEFT|wx.ALIGN_CENTER, cw.ppis(2))
        sizer_btn.Add(cw.ppis((10, 0)), 0, 0, cw.ppis(0))
        sizer_btn.Add(self.btn_ok, 0, wx.ALIGN_CENTER, cw.ppis(0))
        sizer_btn.Add(self.btn_apply, 0, wx.LEFT|wx.ALIGN_CENTER, cw.ppis(5))
        sizer_btn.Add(self.btn_cncl, 0, wx.LEFT|wx.ALIGN_CENTER, cw.ppis(5))

        sizer.Add(self.note, 0, wx.EXPAND, cw.ppis(0))
        sizer.Add(sizer_btn, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, cw.ppis(5))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

class SkinPanel(wx.Panel):
    def __init__(self, parent, editbuttons):
        """スキンの選択と編集を行う。"""
        wx.Panel.__init__(self, parent)
        self.editbuttons = editbuttons
        self.pane_scenario = None

        # スキン
        self.ch_skin = wx.Choice(self, -1, size=(-1, -1))
        self.st_skin = wx.StaticText(self, -1, u"")

        if self.editbuttons:
            self.btn_convertskin = wx.Button(self, -1, u"自動生成...")
            self.btn_editskin = wx.Button(self, -1, u"編集...")
            self.btn_deleteskin = wx.Button(self, -1, u"削除")

        prop = cw.header.GetProperty(u"Data/SkinBase/Skin.xml")
        self.basecash = int(prop.properties.get(u"InitialCash", "4000"))
        self.update_skins(cw.cwpy.setting.skindirname)

        self._do_layout()
        self._bind()

    def _bind(self):
        self.ch_skin.Bind(wx.EVT_CHOICE, self.OnSkinChoice)
        if self.editbuttons:
            self.btn_convertskin.Bind(wx.EVT_BUTTON, self.OnConvertSkin)
            self.btn_editskin.Bind(wx.EVT_BUTTON, self.OnEditSkin)
            self.btn_deleteskin.Bind(wx.EVT_BUTTON, self.OnDeleteSkin)

    def update_skins(self, skindirname, applied=True):
        self.skins = []
        self.skindirs = []
        self.skin_summarys = {}

        for name in os.listdir(u"Data/Skin"):
            path = cw.util.join_paths(u"Data/Skin", name)
            skinpath = cw.util.join_paths(u"Data/Skin", name, "Skin.xml")

            if os.path.isdir(path) and os.path.isfile(skinpath):
                try:
                    prop = cw.header.GetProperty(skinpath)
                    if prop.attrs.get(None, {}).get("dataVersion") in cw.SUPPORTED_SKIN:
                        self.skins.append(prop.properties.get("Name", name))
                        self.skindirs.append(name)                    
                except:
                    # エラーのあるスキンは無視
                    cw.util.print_ex()

        self.ch_skin.SetItems(self.skins)
        n = self.skindirs.index(skindirname)
        self.ch_skin.SetSelection(n)
        self._choice_skin(applied=applied)

    def load_allskins(self):
        for skin in self.skindirs:
            self._load_skinproperties(skin)

    def _load_skinproperties(self, name):
        if name in self.skin_summarys:
            return
        skinpath = cw.util.join_paths(u"Data/Skin", name, "Skin.xml")
        try:
            prop = cw.header.GetProperty(skinpath)
            skintype = prop.properties.get("Type", "")
            skinname = prop.properties.get("Name", "")
            author = prop.properties.get("Author", "")
            desc = prop.properties.get("Description", "")
            vocation120 = cw.util.str2bool(prop.properties.get("CW120VocationLevel", "False"))
            initialcash = int(prop.properties.get("InitialCash", str(self.basecash)))
            self.skin_summarys[name] = (skintype, skinname, author, desc, vocation120, initialcash)
        except Exception:
            # エラーのあるスキン
            cw.util.print_ex()
            skintype = u"*読込エラー*"
            skinname = u"*読込エラー*"
            author = u""
            desc = u"Skin.xmlの読み込みでエラーが発生しました。"
            vocation120 = False
            initialcash = self.basecash
            self.skin_summarys[name] = (skintype, skinname, author, desc, vocation120, initialcash)

    def OnSkinChoice(self, event):
        self._choice_skin()

    def _choice_skin(self, init=False, applied=True):
        skin = self.skindirs[self.ch_skin.GetSelection()]
        s = u"種別: %s\n場所: %s\n作者: %s\n" + u"-" * 45 + u"\n%s"
        if not skin in self.skin_summarys:
            self._load_skinproperties(skin)
        skintype, _skinname, author, desc, _vocation120, _initialcash = self.skin_summarys[skin]
        desc = cw.util.txtwrap(desc, 1)
        self.st_skin.SetLabel(s % (skintype, cw.util.join_paths(u"Data/Skin", skin), author, desc))
        if self.editbuttons:
            self.btn_deleteskin.Enable(cw.cwpy.setting.skindirname <> skin)
        if not init and applied:
            self.GetTopLevelParent().applied()

    def _get_localsettings(self):
        local = cw.setting.LocalSetting()
        self.GetTopLevelParent().panel.pane_draw.apply_localsettings(local)
        self.GetTopLevelParent().panel.pane_font.apply_localsettings(local)
        return local

    def OnConvertSkin(self, event):
        dlg = cw.dialog.skin.SkinConversionDialog(self.TopLevelParent, exe=u"", from_settings=True,
                                                  get_localsettings=self._get_localsettings)
        cw.cwpy.frame.move_dlg(dlg)
        dlg.ShowModal()
        if dlg.successful:
            self.update_skins(dlg.skindirname)
            if self.pane_scenario:
                self.pane_scenario.celleditor = None
        dlg.Destroy()

    def OnEditSkin(self, event):
        skin = self.skindirs[self.ch_skin.GetSelection()]
        skinsummary = self.skin_summarys[skin]
        dlg = cw.dialog.skin.SkinEditDialog(self.TopLevelParent, skin, skinsummary,
                                            get_localsettings=self._get_localsettings)
        cw.cwpy.frame.move_dlg(dlg)

        if dlg.ShowModal() == wx.ID_OK:
            self.skin_summarys[skin] = dlg.skinsummary
            self.update_skins(skin, applied=False)
            if self.pane_scenario:
                self.pane_scenario.celleditor = None
        dlg.Destroy()

    def OnDeleteSkin(self, event):
        skin = self.skindirs[self.ch_skin.GetSelection()]
        if cw.cwpy.setting.skindirname == skin:
            return
        s = u"スキンを削除すると元に戻すことはできません。\n%sを削除しますか？" % (skin)
        dlg = cw.dialog.message.YesNoMessage(self.TopLevelParent, cw.cwpy.msgs["message"], s)
        cw.cwpy.frame.move_dlg(dlg)
        cw.cwpy.play_sound("signal")
        if dlg.ShowModal() == wx.ID_OK:
            cw.cwpy.play_sound("dump")
            dpath = cw.util.join_paths(u"Data/Skin", skin)
            cw.util.remove(dpath)
            self.update_skins(cw.cwpy.setting.skindirname)
            if self.pane_scenario:
                self.pane_scenario.celleditor = None

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        if self.editbuttons:
            bsizer_skinbtn = wx.BoxSizer(wx.HORIZONTAL)
            bsizer_skinbtn.Add(self.btn_convertskin, 0, wx.RIGHT, cw.ppis(3))
            bsizer_skinbtn.Add(self.btn_editskin, 0, wx.RIGHT, cw.ppis(3))
            bsizer_skinbtn.Add(self.btn_deleteskin, 0, 0, cw.ppis(3))

        sizer.Add(self.ch_skin, 0, wx.CENTER, cw.ppis(0))
        sizer.Add(self.st_skin, 1, wx.CENTER|wx.TOP, cw.ppis(3))
        if self.editbuttons:
            sizer.Add(bsizer_skinbtn, 0, wx.ALIGN_RIGHT|wx.TOP, cw.ppis(3))

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def apply_skin(self, forceupdate):
        skinname = self.ch_skin.GetSelection()
        skinname = self.skindirs[skinname]
        if forceupdate or cw.cwpy.setting.skindirname <> skinname:
            if self.editbuttons:
                self.btn_deleteskin.Disable()
            cw.cwpy.exec_func(cw.cwpy.update_skin, skinname, restartop=cw.cwpy.setting.skindirname <> skinname)
            return True
        return False

    def copy_values(self, skin):
        if skin.ch_skin.GetStringSelection() in self.skins:
            self.ch_skin.SetStringSelection(skin.ch_skin.GetStringSelection())
            self._choice_skin(init=True)

class ExpandPanel(wx.Panel):
    def __init__(self, parent, options):
        """拡大表示モードの設定を行う。"""
        wx.Panel.__init__(self, parent)
        self.options = options

        # 拡大表示モード
        self._expand_enable = True
        self.st_expandscr = wx.StaticText(self, -1, u"描画倍率:")
        self.st_expandwin = wx.StaticText(self, -1, u"表示倍率:")

        self.ch_expanddrawing = wx.ComboBox(self, -1, style=wx.CB_DROPDOWN|wx.CB_READONLY)

        self.sl_expand = wx.Slider(
            self, -1, 10, 10, 11, size=(cw.ppis(120), -1),
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)
        self.st_expand = wx.StaticText(self, -1)
        dc = wx.ClientDC(self.st_expand)
        s = u"9倍 (9999x9999)_"
        self.st_expand.SetMinSize((dc.GetTextExtent(s)[0], -1))

        self.cb_fullscreen = wx.CheckBox(self, -1, u"フルスクリーン")

        if self.options:
            self.ln_expand = wx.StaticLine(self, -1, style=wx.HORIZONTAL)
            self.cb_smoothexpand = wx.CheckBox(self, -1,
                                               u"拡大後の画面を滑らかにする")

        self._do_layout()
        self._bind()

    def _bind(self):
        self.sl_expand.Bind(wx.EVT_SLIDER, self.OnExpandChange)
        self.cb_fullscreen.Bind(wx.EVT_CHECKBOX, self.OnExpandChange)

    def load(self, setting):
        self.cb_fullscreen.SetValue(setting.expandmode == "FullScreen")
        if self.options:
            self.cb_smoothexpand.SetValue(setting.smoothexpand)

        # 最大倍率を概算
        x, y = cw.cwpy.frame.get_displaysize()
        x = 10 * x / cw.SIZE_SCR[0]
        y = 10 * y / cw.SIZE_SCR[1]
        if setting.expandmode == "FullScreen" or setting.expandmode == "None":
            n = 10 # FullScreen中はスライドを1.0倍に仮設定
        else:
            n = int(10 * float(setting.expandmode))
        nmax = x if x < y else y
        if nmax < 10:
            nmax = 10
        if nmax < n:
            n = nmax

        i = 0
        val = 1
        self.ch_expanddrawing.Clear()
        while True:
            self.ch_expanddrawing.Append(u"%s倍" % (val))
            if setting.expanddrawing == val:
                self.ch_expanddrawing.Select(i)
            i += 1
            val *= 2
            if nmax < val*10:
                break
        if nmax <= 10:
            self.sl_expand.SetMax(11)
            self._expand_enable = False
            n = 10
        else:
            self.sl_expand.SetMax(nmax)
            self._expand_enable = True
        self.sl_expand.SetValue(n)
        self.sl_expand.Enable(self._expand_enable)

        if self.ch_expanddrawing.GetSelection() == -1:
            self.ch_expanddrawing.Select(0)

        self.make_expandinfo()

    def make_expandinfo(self):
        if self.cb_fullscreen.IsChecked():
            self.sl_expand.Disable()
            self.st_expand.SetLabel(u"フルスクリーン")
        else:
            self.sl_expand.Enable(self._expand_enable)
            n = self.sl_expand.GetValue()
            x = cw.SIZE_GAME[0] * n / 10
            y = cw.SIZE_GAME[1] * n / 10
            s = u"%d.%d倍 (%dx%d)" % (n/10, n%10, x, y)
            self.st_expand.SetLabel(s)

    def OnExpandChange(self, event):
        self.make_expandinfo()

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        bsizer_expandmode_draw = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_expandmode_draw.Add(self.st_expandscr, 0, wx.RIGHT|wx.CENTER, cw.ppis(3))
        bsizer_expandmode_draw.Add(self.ch_expanddrawing, 0, wx.CENTER|wx.RIGHT, cw.ppis(10))
        bsizer_expandmode_draw.Add(self.st_expandwin, 0, wx.CENTER, cw.ppis(0))
        bsizer_expandmode_draw.Add(self.st_expand, 0, wx.CENTER, cw.ppis(0))

        sizer.Add(bsizer_expandmode_draw, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer.Add(self.sl_expand, 0, wx.EXPAND, cw.ppis(3))
        sizer.Add(self.cb_fullscreen, 0, wx.ALIGN_RIGHT, cw.ppis(0))
        if self.options:
            sizer.Add(self.ln_expand, 0, wx.TOP|wx.EXPAND, cw.ppis(3))
            sizer.Add(self.cb_smoothexpand, 0, wx.TOP, cw.ppis(3))

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def apply_expand(self, setting):
        """拡大設定を反映する。"""
        update = (setting == cw.cwpy.setting)
        if self.options:
            value = self.cb_smoothexpand.GetValue()
            setting.smoothexpand = value
        if self.cb_fullscreen.IsChecked():
            value = "FullScreen"
        elif self.sl_expand.GetValue() == 10: # 1倍 == 拡大なし
            value = "None"
        elif self.sl_expand.GetValue() % 10 == 0: # 整数倍
            value = self.sl_expand.GetValue() / 10
        else:
            value = float(self.sl_expand.GetValue()) / 10
        expanddrawing = int(2 ** self.ch_expanddrawing.GetSelection())
        if str(value) <> str(setting.expandmode) or expanddrawing <> setting.expanddrawing:
            if update and cw.cwpy.is_expanded():
                # 設定が変更されたので拡大状態を切り替え
                def func(value):
                    cw.cwpy.setting.expandmode = value
                    cw.cwpy.setting.expanddrawing = expanddrawing
                    if value == "FullScreen":
                        # FIXME: FullScreen以外の拡大設定で拡大しておき、
                        #        設定をFullScreenに変更し、その後F4キーで
                        #        拡大を解除するとウィンドウの操作が効かなくなる
                        cw.cwpy.set_expanded(False, value, force=True)
                    else:
                        cw.cwpy.set_expanded(True, value, force=True)
                cw.cwpy.exec_func(func, value)
            else:
                setting.expandmode = value
                setting.expanddrawing = expanddrawing

    def copy_values(self, expand):
        self.ch_expanddrawing.SetSelection(min(self.ch_expanddrawing.GetCount()-1, expand.ch_expanddrawing.GetSelection()))
        self.sl_expand.SetValue(expand.sl_expand.GetValue())
        self.cb_fullscreen.SetValue(expand.cb_fullscreen.GetValue())

        self.make_expandinfo()

        if self.options and expand.options:
            self.cb_smoothexpand.SetValue(expand.cb_smoothexpand.GetValue())

class GeneralSettingPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        # デバッグモード
        self.box_gene = wx.StaticBox(self, -1, u"動作モード")
        self.cb_debug = wx.CheckBox(self, -1, u"デバッグモードでプレイする" + u"(Ctrl+D)")
        self.cb_debug.SetValue(cw.cwpy.debug)
        
        self.st_startupscene = wx.StaticText(self, -1, u"起動時の動作:")
        self.ch_startupscene = wx.Choice(self, -1, choices=[u"タイトル画面を開く", u"最後に選択した拠点を開く"])

        self.box_messagelog = wx.StaticBox(self, -1, u"メッセージログ(F5キーで表示)")
        self.st_messagelog_type = wx.StaticText(self, -1, u"表示形式:")
        self.ch_messagelog_type = wx.Choice(self, -1, choices=[u"1件ずつ表示", u"並べて表示", u"高さを圧縮"])
        self.st_backlogmax = wx.StaticText(self, -1, u"最大数:")
        self.sc_backlogmax = wx.SpinCtrl(self, -1, size=(cw.ppis(80), -1), max=9999, min=0)

        # スキン
        self.box_skin = wx.StaticBox(self, -1, u"スキン",)
        self.skin = SkinPanel(self, True)

        # 拡大表示モード
        self.box_expandmode = wx.StaticBox(self, -1, u"拡大表示方式(F4キーで拡大)")
        self.expand = ExpandPanel(self, True)

        # 持出金額
        self.box_party = wx.StaticBox(self, -1, u"パーティ")
        self.st_initmoneyamount = wx.StaticText(self, -1, u"結成時の持出金額:")
        self.sc_initmoneyamount = wx.SpinCtrl(self, -1, "", size=(cw.ppis(80), -1), min=0, max=999999)
        self.cb_initmoneyisinitialcash = wx.CheckBox(self, -1, u"初期資金と同額")

        self.cb_autosavepartyrecord = wx.CheckBox(
            self, -1, u"解散時、自動的にパーティ情報を記録する")
        #self.cb_overwritepartyrecord = wx.CheckBox(
        #    self, -1, u"自動記録時、同名のパーティ記録へ上書きする")

        # スクリーンショット情報
        self.box_ss = wx.StaticBox(self, -1, u"スクリーンショット情報(PrtScrキーで撮影)")
        self.tx_ssinfoformat = wx.TextCtrl(self, -1, size=(cw.ppis(150), -1), style=wx.SIMPLE_BORDER)
        # スクリーンショット情報の色
        choices = [u"黒文字", u"白文字"]
        self.ch_ssinfocolor = wx.Choice(self, -1, size=(-1, -1), choices=choices)

        # 背景イメージ
        self.st_ssinfobackimage = wx.StaticText(self, -1, u"背景画像:")
        self.tx_ssinfobackimage = wx.TextCtrl(self, -1, size=(-1, -1), style=wx.SIMPLE_BORDER)
        self.ref_ssinfobackimage = cw.util.create_fileselection(self,
                                                                target=self.tx_ssinfobackimage,
                                                                message=u"スクリーンショット情報の背景にするファイルを選択",
                                                                wildcard=u"画像ファイル (*.jpg;*.png;*.gif;*.bmp;*.tiff;*.xpm)|*.jpg;*.png;*.gif;*.bmp;*.tiff;*.xpm|全てのファイル (*.*)|*.*")

        # スクリーンショットのファイル名
        self.st_ssfnameformat = wx.StaticText(self, -1, u"ファイル名:")
        self.tx_ssfnameformat = wx.TextCtrl(self, -1, size=(cw.ppis(150), -1), style=wx.SIMPLE_BORDER)
        # 所持カード撮影情報のファイル名
        self.st_cardssfnameformat = wx.StaticText(self, -1, u"所持カード:")
        self.tx_cardssfnameformat = wx.TextCtrl(self, -1, size=(cw.ppis(150), -1), style=wx.SIMPLE_BORDER)
        self.st_cardssfnameformat.SetToolTipString(u"パーティ全員の所持カード一覧のファイル名。\nshift+PrtScrで撮影。")

        self.ss_tx = set()
        self.ss_tx.add(self.tx_ssinfoformat)
        self.ss_tx.add(self.tx_ssfnameformat)
        self.ss_tx.add(self.tx_cardssfnameformat)

        #self.st_ssinfo_brackets = wx.StaticText(self, -1, u"[ ] 内は、各種情報がある場合のみ")

        self.sstoolbar = wx.ToolBar(self, -1, style=wx.TB_FLAT|wx.TB_NODIVIDER|wx.TB_HORZ_TEXT|wx.TB_NOICONS)
        self.sstoolbar.SetToolBitmapSize(wx.Size(cw.ppis(0), cw.ppis(0)))
        self.ti_ssins = self.sstoolbar.AddLabelTool(
            -1, u"各種情報の挿入", wx.EmptyBitmap(cw.ppis(0), cw.ppis(0)),
            shortHelp=u"利用可能な環境変数一覧。手動でも入力できます。\n[ ] 内は、情報がない場合出力されません。")
        self.sstoolbar.Realize()

        ssdic = [
            (u"application", u"アプリケーション名"),
            (u"version", u"バージョン情報"),None,
            (u"skin", u"スキン名"),
            (u"yado", u"拠点名"),
            (u"party", u"パーティ名"),None,
            (u"scenario", u"シナリオ名"),
            (u"author", u"作者名"),
            (u"path", u"シナリオのファイルパス"),
            (u"file", u"シナリオのファイル名"),
            (u"compatibility", u"互換モード"),None,
            (u"date", u"日付"),(u"time", u"時刻"),(u"year", u"年"),(u"month", u"月"),(u"day", u"日"),
            (u"hour", u"時"),(u"minute", u"分"),(u"second", u"秒"),(u"millisecond", u"ミリ秒"),
        ]
        if versioninfo:
            ssdic.insert(2, (u"build", u"ビルド情報"))
        self.ssdic = {}
        self.ssinsmenu = wx.Menu()
        for t in ssdic:
            if t:
                p, name = t
                mi = self.ssinsmenu.Append(-1, u"%%%s%% = %s" % (p, name))
                self.ssdic[mi.GetId()] = (mi.GetId(), p, name)
            else:
                self.ssinsmenu.AppendSeparator()
        self._ss_focus()

        self._do_layout()
        self._bind()

    def _bind(self):
        self.cb_autosavepartyrecord.Bind(wx.EVT_CHECKBOX, self.OnAutoSavePartyRecord)
        self.cb_initmoneyisinitialcash.Bind(wx.EVT_CHECKBOX, self.OnInitMoneyIsInitialCash)
        self.sstoolbar.Bind(wx.EVT_TOOL, self.OnSSTool)
        for tx in self.ss_tx:
            tx.Bind(wx.EVT_SET_FOCUS, self.OnSSFocus)
            tx.Bind(wx.EVT_KILL_FOCUS, self.OnSSFocus)

    def load(self, setting):
        if setting.messagelog_type == cw.setting.LOG_SINGLE:
            self.ch_messagelog_type.SetSelection(0) # 単一表示
        elif setting.messagelog_type == cw.setting.LOG_COMPRESS:
            self.ch_messagelog_type.SetSelection(2) # 圧縮表示
        else:
            self.ch_messagelog_type.SetSelection(1) # 並べて表示(デフォルト)
        if setting.startupscene == cw.setting.OPEN_LAST_BASE:
            self.ch_startupscene.SetSelection(1) # 最後に選択した拠点を開く
        else:
            self.ch_startupscene.SetSelection(0) # タイトル画面を開く
        self.sc_backlogmax.SetValue(setting.backlogmax)
        self.sc_initmoneyamount.SetValue(setting.initmoneyamount)
        self.cb_initmoneyisinitialcash.SetValue(setting.initmoneyisinitialcash)
        self.sc_initmoneyamount.Enable(not self.cb_initmoneyisinitialcash.GetValue())
        self.cb_autosavepartyrecord.SetValue(setting.autosave_partyrecord)
        #self.cb_overwritepartyrecord.SetValue(setting.overwrite_partyrecord)
        #self.cb_overwritepartyrecord.Enable(setting.autosave_partyrecord)
        self.tx_ssinfoformat.SetValue(setting.ssinfoformat)
        self.tx_ssfnameformat.SetValue(setting.ssfnameformat)
        self.tx_cardssfnameformat.SetValue(setting.cardssfnameformat)
        if setting.ssinfofontcolor[:3] == (255, 255, 255):
            self.ch_ssinfocolor.Select(1)
        else:
            self.ch_ssinfocolor.Select(0)
        self.tx_ssinfobackimage.SetValue(setting.ssinfobackimage)
        self.expand.load(setting)

    def init_values(self, setting):

        if setting.messagelog_type_init == cw.setting.LOG_SINGLE:
            self.ch_messagelog_type.SetSelection(0)
        elif setting.messagelog_type_init == cw.setting.LOG_LIST:
            self.ch_messagelog_type.SetSelection(1)
        elif setting.messagelog_type_init == cw.setting.LOG_COMPRESS:
            self.ch_messagelog_type.SetSelection(2)
        if setting.startupscene_init == cw.setting.OPEN_TITLE:
            self.ch_startupscene.SetSelection(0)
        elif setting.startupscene_init == cw.setting.OPEN_LAST_BASE:
            self.ch_startupscene.SetSelection(1)
        self.sc_backlogmax.SetValue(setting.backlogmax_init)
        self.expand.ch_expanddrawing.SetSelection(0)
        if setting.expandmode_init == "FullScreen":
            self.expand.cb_fullscreen.SetValue(True)
        else:
            self.expand.ch_expanddrawing.SetSelection(int(setting.expandmode_init) - 1)
            self.expand.cb_fullscreen.SetValue(False)
        self.expand.make_expandinfo()
        self.expand.cb_smoothexpand.SetValue(setting.smoothexpand_init)
        self.sc_initmoneyamount.SetValue(setting.initmoneyamount_init)
        self.cb_initmoneyisinitialcash.SetValue(setting.initmoneyisinitialcash_init)
        self.sc_initmoneyamount.Enable(not self.cb_initmoneyisinitialcash.GetValue())
        self.cb_autosavepartyrecord.SetValue(setting.autosave_partyrecord_init)
        #self.cb_overwritepartyrecord.SetValue(setting.overwrite_partyrecord_init)
        #self.cb_overwritepartyrecord.Enable(self.cb_autosavepartyrecord.GetValue())
        self.tx_ssinfoformat.SetValue(setting.ssinfoformat_init)
        self.tx_ssfnameformat.SetValue(setting.ssfnameformat_init)
        self.tx_cardssfnameformat.SetValue(setting.cardssfnameformat_init)
        self.ch_ssinfocolor.Select(1 if setting.ssinfofontcolor_init[:3] == (255, 255, 255) else 0)
        self.tx_ssinfobackimage.SetValue(setting.ssinfobackimage_init)

    def OnSSTool(self, event):
        if self.ti_ssins.GetId() == event.GetId():
            self.sstoolbar.PopupMenu(self.ssinsmenu)
        else:
            t = self.ssdic.get(event.GetId(), None)
            if not t:
                return
            p = t[1]
            f = wx.Window.FindFocus()
            for tx in self.ss_tx:
                if tx is f:
                    tx.WriteText(u"%%%s%%" % (p))

    def OnSSFocus(self, event):
        self._ss_focus()
        event.Skip()

    def _ss_focus(self):
        enable = wx.Window.FindFocus() in self.ss_tx
        self.sstoolbar.Enable(enable)

    def OnAutoSavePartyRecord(self, event):
        pass
        #self.cb_overwritepartyrecord.Enable(self.cb_autosavepartyrecord.GetValue())

    def OnInitMoneyIsInitialCash(self, event):
        self.sc_initmoneyamount.Enable(not self.cb_initmoneyisinitialcash.GetValue())

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer_h1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_left = wx.BoxSizer(wx.VERTICAL)
        sizer_right = wx.BoxSizer(wx.VERTICAL)

        bsizer_gene = wx.StaticBoxSizer(self.box_gene, wx.VERTICAL)
        bsizer_skin = wx.StaticBoxSizer(self.box_skin, wx.VERTICAL)
        bsizer_expandmode = wx.StaticBoxSizer(self.box_expandmode, wx.VERTICAL)

        bsizer_gene.Add(self.cb_debug, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))

        bsizer_startup = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_startup.Add(self.st_startupscene, 0, wx.ALIGN_CENTER, cw.ppis(0))
        bsizer_startup.Add(self.ch_startupscene, 0, wx.LEFT|wx.ALIGN_CENTER, cw.ppis(3))
        bsizer_gene.Add(bsizer_startup, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))

        bsizer_gene.SetMinSize((_settings_width(), -1))

        bsizer_log = wx.StaticBoxSizer(self.box_messagelog, wx.HORIZONTAL)
        bsizer_log.Add(self.st_messagelog_type, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.ALIGN_CENTER, cw.ppis(3))
        bsizer_log.Add(self.ch_messagelog_type, 0, wx.RIGHT|wx.BOTTOM|wx.ALIGN_CENTER, cw.ppis(5))
        bsizer_log.Add(self.st_backlogmax, 0, wx.RIGHT|wx.BOTTOM|wx.ALIGN_CENTER, cw.ppis(3))
        bsizer_log.Add(self.sc_backlogmax, 0, wx.RIGHT|wx.BOTTOM|wx.ALIGN_CENTER, cw.ppis(5))
        bsizer_log.SetMinSize((_settings_width(), -1))

        bsizer_skin.Add(self.skin, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_skin.SetMinSize((_settings_width(), cw.ppis(180)))

        bsizer_expandmode.Add(self.expand, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        bsizer_expandmode.SetMinSize((_settings_width(), -1))

        bsizer_party = wx.StaticBoxSizer(self.box_party, wx.VERTICAL)
        bsizer_partymoney = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_partymoney.Add(self.st_initmoneyamount, 0, wx.RIGHT|wx.CENTER, cw.ppis(3))
        bsizer_partymoney.Add(self.sc_initmoneyamount, 0, wx.RIGHT|wx.CENTER, cw.ppis(3))
        bsizer_partymoney.Add(self.cb_initmoneyisinitialcash, 0, wx.CENTER, cw.ppis(3))
        bsizer_party.Add(bsizer_partymoney, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_party.Add(self.cb_autosavepartyrecord, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        #bsizer_party.Add(self.cb_overwritepartyrecord, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))

        bsizer_ss = wx.StaticBoxSizer(self.box_ss, wx.VERTICAL)
        bsizer_ssl = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_ssl.Add(self.tx_ssinfoformat, 1, wx.RIGHT|wx.CENTER, cw.ppis(3))
        bsizer_ssl.Add(self.ch_ssinfocolor, 0, wx.CENTER, cw.ppis(3))
        bsizer_ss.Add(bsizer_ssl, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        ssinfobackimage_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ssinfobackimage_sizer.Add(self.tx_ssinfobackimage, 1, wx.RIGHT | wx.CENTER, cw.ppis(3))
        ssinfobackimage_sizer.Add(self.ref_ssinfobackimage, 0, wx.CENTER, cw.ppis(0))

        gsizer_fname = wx.GridBagSizer()
        gsizer_fname.Add(self.st_ssinfobackimage, pos=(0, 0), flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                                  border=cw.ppis(3))
        gsizer_fname.Add(ssinfobackimage_sizer, pos=(0, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND,
                                  border=cw.ppis(3))
        gsizer_fname.Add((0, cw.ppis(3)), pos=(1, 0))
        gsizer_fname.Add(self.st_ssfnameformat, pos=(2, 0), flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                                  border=cw.ppis(3))
        gsizer_fname.Add(self.tx_ssfnameformat, pos=(2, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND,
                                  border=cw.ppis(3))
        gsizer_fname.Add(self.st_cardssfnameformat, pos=(3, 0),
                                  flag=wx.TOP | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=cw.ppis(3))
        gsizer_fname.Add(self.tx_cardssfnameformat, pos=(3, 1),
                                  flag=wx.TOP | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=cw.ppis(3))
        gsizer_fname.AddGrowableCol(1, 4)

        bsizer_ss.Add(gsizer_fname, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, cw.ppis(1) - 1)
        #bsizer_ss2 = wx.BoxSizer(wx.HORIZONTAL)
        #bsizer_ss2.Add(self.st_ssinfo_brackets, 0, wx.TOP |wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.ALIGN_LEFT, cw.ppis(3))
        bsizer_ss.Add(self.sstoolbar, 0, wx.TOP |wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.ALIGN_RIGHT, cw.ppis(8))
        #bsizer_ss.Add(bsizer_ss2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, cw.ppis(1) - 1)

        sizer_left.Add(bsizer_gene, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_left.Add(bsizer_log, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_left.Add(bsizer_skin, 1, wx.EXPAND, cw.ppis(3))

        sizer_right.Add(bsizer_expandmode, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_right.Add(bsizer_party, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_right.Add(bsizer_ss, 0, wx.EXPAND, cw.ppis(0))

        sizer_h1.Add(sizer_left, 0, wx.RIGHT|wx.EXPAND, cw.ppis(5))
        sizer_h1.Add(sizer_right, 1, wx.EXPAND, cw.ppis(3))

        sizer.Add(sizer_h1, 1, wx.ALL|wx.EXPAND, cw.ppis(10))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

class SpeedPanel(wx.Panel):
    def __init__(self, parent, battlespeed):
        """背景切替方式と各種速度を設定する。"""
        wx.Panel.__init__(self, parent)
        self.battlespeed = battlespeed

        # トランジション効果
        self.box_tran = wx.StaticBox(
            self, -1, u"背景の切り替え方式(速い⇔遅い)")
        self.transitions = [
            "None", "Blinds", "PixelDissolve", "Fade"]
        self.choices_tran = [
            u"アニメーションなし", u"短冊(スレッド)式", u"ドット置換(シェーブ)式",
            u"色置換(フェード)式"]
        self.ch_tran = wx.Choice(
            self, -1, size=(-1, -1), choices=self.choices_tran)
        self.sl_tran = wx.Slider(
            self, -1, 0, 0, 10,
            size=(_settings_width()-cw.ppis(10), -1), style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)
        self.sl_tran.SetTickFreq(1, 1)
        # カード描画速度
        self.box_deal = wx.StaticBox(
            self, -1, u"カード描画速度(速い⇔遅い)")
        self.sl_deal = wx.Slider(
            self, -1, 0, 0, 10, size=(_settings_width()-cw.ppis(10), -1),
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)
        self.sl_deal.SetTickFreq(1, 1)

        if self.battlespeed:
            # 戦闘行動描画速度
            self.box_deal_battle = wx.StaticBox(
                self, -1, u"戦闘行動描画速度(速い⇔遅い)")
            self.sl_deal_battle = wx.Slider(
                self, -1, 0, 0, 10, size=(_settings_width()-cw.ppis(10), -1),
                style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)
            self.sl_deal_battle.SetTickFreq(1, 1)
            self.cb_use_battlespeed = wx.CheckBox(
                self, -1, u"戦闘中の描画速度を同期")
            self.cb_wait_usecard  = wx.CheckBox(
                self, -1, u"カード使用前に空白時間")
            self.cb_wait_usecard.SetToolTipString( u"戦闘中の描画速度にも影響します(1.28互換)" )
        # メッセージ表示速度
        self.box_msgs = wx.StaticBox(
            self, -1, u"メッセージ表示速度(速い⇔遅い)")
        self.sl_msgs = wx.Slider(
            self, -1, 0, 0, 10, size=(_settings_width()-cw.ppis(10), -1),
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)
        self.sl_msgs.SetTickFreq(1, 1)

        self._do_layout()
        self._bind()

    def load(self, setting):
        n = self.transitions.index(setting.transition)
        self.ch_tran.SetSelection(n)
        self.sl_tran.SetValue(setting.transitionspeed)
        self.sl_deal.SetValue(setting.dealspeed)
        if self.battlespeed:
            self.sl_deal_battle.SetValue(setting.dealspeed_battle)
            self.cb_use_battlespeed.SetValue(not setting.use_battlespeed)
            self.sl_deal_battle.Enable(setting.use_battlespeed)
            self.cb_wait_usecard.SetValue(setting.wait_usecard)
        self.sl_msgs.SetValue(setting.messagespeed)

    def _bind(self):
        if self.battlespeed:
            self.cb_use_battlespeed.Bind(wx.EVT_CHECKBOX, self.OnUseBattleSpeed, id=self.cb_use_battlespeed.GetId())

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        bsizer_tran = wx.StaticBoxSizer(self.box_tran, wx.VERTICAL)
        bsizer_deal = wx.StaticBoxSizer(self.box_deal, wx.VERTICAL)

        if self.battlespeed:
            bsizer_deal_battle = wx.StaticBoxSizer(self.box_deal_battle, wx.VERTICAL)
        bsizer_msgs = wx.StaticBoxSizer(self.box_msgs, wx.VERTICAL)

        bsizer_tran.Add(self.ch_tran, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(0))
        bsizer_tran.Add(self.sl_tran, 0, wx.EXPAND, cw.ppis(0))
        bsizer_deal.Add(self.sl_deal, 0, wx.EXPAND, cw.ppis(0))
        if self.battlespeed:
            bsizer_deal_battle.Add(self.sl_deal_battle, 0, wx.EXPAND, cw.ppis(0))
            bsizer_deal2 = wx.GridSizer(0, 2)
            bsizer_deal2.Add(self.cb_wait_usecard, 0, wx.LEFT|wx.RIGHT, cw.ppis(3))
            bsizer_deal2.Add(self.cb_use_battlespeed, 0, wx.ALIGN_RIGHT, cw.ppis(0))
            bsizer_deal2.Fit
            bsizer_deal.Add(bsizer_deal2, 0, wx.EXPAND, cw.ppis(0))
        bsizer_msgs.Add(self.sl_msgs, 0, wx.EXPAND, cw.ppis(0))

        sizer.Add(bsizer_tran, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer.Add(bsizer_deal, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        if self.battlespeed:
            sizer.Add(bsizer_deal_battle, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer.Add(bsizer_msgs, 0, wx.EXPAND, cw.ppis(3))

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnUseBattleSpeed(self, event):
        self.sl_deal_battle.Enable(not self.cb_use_battlespeed.GetValue())

    def apply_speed(self, setting):
        dealspeed = self.sl_deal.GetValue()
        if self.battlespeed:
            dealspeed_battle = self.sl_deal_battle.GetValue()
            use_battlespeed = not self.cb_use_battlespeed.GetValue()
            setting.set_dealspeed(dealspeed, dealspeed_battle, use_battlespeed)
        else:
            setting.set_dealspeed(dealspeed, setting.dealspeed_battle, setting.use_battlespeed)
        value = self.sl_msgs.GetValue()
        setting.messagespeed = value
        value = self.ch_tran.GetSelection()
        value = self.transitions[value]
        setting.transition = value
        value = self.sl_tran.GetValue()
        setting.transitionspeed = value
        value = self.cb_wait_usecard.GetValue()
        setting.wait_usecard = value

    def copy_values(self, speed):
        self.ch_tran.SetSelection(speed.ch_tran.GetSelection())
        self.sl_tran.SetValue(speed.sl_tran.GetValue())
        self.sl_deal.SetValue(speed.sl_deal.GetValue())
        self.cb_use_battlespeed.SetValue(speed.cb_use_battlespeed.GetValue())
        if self.battlespeed and speed.battlespeed:
            self.sl_deal_battle.SetValue(speed.sl_deal_battle.GetValue())
            self.cb_use_battlespeed.SetValue(speed.cb_use_battlespeed.GetValue())
            self.sl_deal_battle.Enable(speed.sl_deal_battle.IsEnabled())
        self.sl_msgs.SetValue(speed.sl_msgs.GetValue())

class DrawingSettingPanel(wx.Panel):
    def __init__(self, parent, for_local, get_localsettings, use_copybase):
        wx.Panel.__init__(self, parent)
        self._for_local = for_local
        self._get_localsettings = get_localsettings

        if self._for_local:
            self.cb_important = wx.CheckBox(self, -1, u"このスキンの描画設定を基本設定よりも優先して使用する")
        else:
            self.cb_important = None
            self.box_gene = wx.StaticBox(self, -1, u"カードの画像補正")
            self.cb_smoothing_card_down = wx.CheckBox(self, -1, u"縮小カードの画像補正を行う")
            self.cb_smoothing_card_up = wx.CheckBox(self, -1, u"拡大カードの画像補正を行う")
            self.cb_smooth_bg = wx.CheckBox(self, -1, u"拡大・縮小した背景画像を滑らかにする")

            # 背景切替方式と各種速度
            self.speed = SpeedPanel(self, True)

        # メッセージボード背景色
        self.box_mwin = wx.StaticBox(self, -1, u"メッセージボードの背景")
        self.st_mwin = wx.StaticText(self, -1, u"カラー")
        self.cs_mwin = wx.ColourPickerCtrl(self, -1)
        self.st_blwin = wx.StaticText(self, -1, u"ログ")
        self.cs_blwin = wx.ColourPickerCtrl(self, -1)
        self.st_mwin2 = wx.StaticText(self, -1, u"透明度")
        self.sc_mwin = wx.SpinCtrl(self, -1, "", size=(cw.ppis(50), -1))
        self.sc_mwin.SetRange(0, 255)
        # メッセージボード枠色
        self.box_mframe = wx.StaticBox(self, -1, u"メッセージボードの枠")
        self.st_mframe = wx.StaticText(self, -1, u"カラー")
        self.cs_mframe = wx.ColourPickerCtrl(self, -1)
        self.st_blframe = wx.StaticText(self, -1, u"ログ")
        self.cs_blframe = wx.ColourPickerCtrl(self, -1)
        self.st_mframe2 = wx.StaticText(self, -1, u"透明度")
        self.sc_mframe = wx.SpinCtrl(self, -1, "", size=(cw.ppis(50), -1))
        self.sc_mframe.SetRange(0, 255)

        # メッセージログカーテン色
        self.box_blcurtain = wx.StaticBox(self, -1, u"メッセージログの背景")
        self.st_blcurtain = wx.StaticText(self, -1, u"カラー")
        self.cs_blcurtain = wx.ColourPickerCtrl(self, -1)
        self.st_blcurtain2 = wx.StaticText(self, -1, u"透明度")
        self.sc_blcurtain = wx.SpinCtrl(self, -1, "", size=(cw.ppis(50), -1))
        self.sc_blcurtain.SetRange(0, 255)

        # カーテン色
        self.box_curtain = wx.StaticBox(self, -1, u"カーテン(選択モードの背景効果)")
        self.st_curtain = wx.StaticText(self, -1, u"カラー")
        self.cs_curtain = wx.ColourPickerCtrl(self, -1)
        self.st_curtain2 = wx.StaticText(self, -1, u"透明度")
        self.sc_curtain = wx.SpinCtrl(self, -1, "", size=(cw.ppis(50), -1))
        self.sc_curtain.SetRange(0, 255)

        # フルスクリーンの背景
        self.box_fscrback = wx.StaticBox(self, -1, u"フルスクリーンの背景")
        choices = [u"<背景なし>", u"<ファイルから選択>", u"ダイアログの壁紙", u"スキンのロゴ"]
        self.ch_fscrbacktype = wx.Choice(self, -1, size=(-1, -1), choices=choices)
        self.tx_fscrbackfile = wx.TextCtrl(self, -1, size=(cw.ppis(150), -1))
        self.ref_fscrbackfile = cw.util.create_fileselection(self,
            target=self.tx_fscrbackfile,
            message=u"フルスクリーンの背景にするファイルを選択",
            wildcard=u"画像ファイル (*.jpg;*.png;*.gif;*.bmp;*.tiff;*.xpm)|*.jpg;*.png;*.gif;*.bmp;*.tiff;*.xpm|全てのファイル (*.*)|*.*")

        if self._for_local:
            if use_copybase:
                self.copybtn = wx.Button(self, -1, u"基本設定をコピー")
            else:
                self.copybtn = None
            self.initbtn = wx.Button(self, -1, u"デフォルト")

        self._do_layout()
        self._bind()

    def load(self, setting, local):
        if self._for_local:
            self.cb_important.SetValue(local.important_draw)
        else:
            self.cb_smooth_bg.SetValue(setting.smoothscale_bg)
            self.cb_smoothing_card_up.SetValue(setting.smoothing_card_up)
            self.cb_smoothing_card_down.SetValue(setting.smoothing_card_down)
            #self.cb_whitecursor.SetValue(setting.cursor_type == cw.setting.CURSOR_WHITE)

            self.speed.load(setting)

        self.cs_mwin.SetColour(local.mwincolour)
        self.cs_blwin.SetColour(local.blwincolour)
        self.sc_mwin.SetValue(local.mwincolour[3])
        self.cs_mframe.SetColour(local.mwinframecolour)
        self.cs_blframe.SetColour(local.blwinframecolour)
        self.sc_mframe.SetValue(local.mwinframecolour[3])
        self.cs_blcurtain.SetColour(local.blcurtaincolour)
        self.sc_blcurtain.SetValue(local.blcurtaincolour[3])
        self.cs_curtain.SetColour(local.curtaincolour)
        self.sc_curtain.SetValue(local.curtaincolour[3])

        if local.fullscreenbackgroundtype == 0:
            self.ch_fscrbacktype.SetSelection(0)
            self.tx_fscrbackfile.SetValue(u"")
        elif local.fullscreenbackgroundtype == 1:
            self.ch_fscrbacktype.SetSelection(1)
            self.tx_fscrbackfile.SetValue(local.fullscreenbackgroundfile)
        elif local.fullscreenbackgroundtype == 2:
            if local.fullscreenbackgroundfile == u"Resource/Image/Dialog/CAUTION":
                self.ch_fscrbacktype.SetSelection(2)
                self.tx_fscrbackfile.SetValue(u"")
            elif local.fullscreenbackgroundfile == u"Resource/Image/Dialog/PAD":
                self.ch_fscrbacktype.SetSelection(3)
                self.tx_fscrbackfile.SetValue(u"")
            else:
                self.ch_fscrbacktype.SetSelection(0)
                self.tx_fscrbackfile.SetValue(u"")

        self._update_enabled()

    def init_values(self, setting, local):
        if not self._for_local:
            self.cb_smoothing_card_up.SetValue(setting.smoothing_card_up_init)
            self.cb_smoothing_card_down.SetValue(setting.smoothing_card_down_init)
            self.cb_smooth_bg.SetValue(setting.smoothscale_bg_init)
            #self.cb_whitecursor.SetValue(setting.cursor_type_init == cw.setting.CURSOR_WHITE)
            self.speed.sl_deal.SetValue(setting.dealspeed_init)
            self.speed.sl_deal_battle.SetValue(setting.dealspeed_battle_init)
            self.speed.cb_use_battlespeed.SetValue(not setting.use_battlespeed_init)
            self.speed.cb_wait_usecard.SetValue(setting.wait_usecard_init)
            self.speed.sl_deal_battle.Enable(setting.use_battlespeed_init)
            self.speed.sl_msgs.SetValue(setting.messagespeed_init)
            self.speed.ch_tran.SetSelection(self.speed.transitions.index(setting.transition_init))
            self.speed.sl_tran.SetValue(setting.transitionspeed_init)
        self.sc_mwin.SetValue(local.mwincolour_init[3])
        self.cs_mwin.SetColour(local.mwincolour_init[:3])
        self.sc_mframe.SetValue(local.mwinframecolour_init[3])
        self.cs_mframe.SetColour(local.mwinframecolour_init[:3])
        self.cs_blwin.SetColour(local.blwincolour_init[:3])
        self.cs_blframe.SetColour(local.blwinframecolour_init[:3])
        self.sc_blcurtain.SetValue(local.blcurtaincolour_init[3])
        self.cs_blcurtain.SetColour(local.blcurtaincolour_init[:3])
        self.sc_curtain.SetValue(local.curtaincolour_init[3])
        self.cs_curtain.SetColour(local.curtaincolour_init[:3])

        if local.fullscreenbackgroundtype_init == 2:
            self.tx_fscrbackfile.SetValue("")
            if local.fullscreenbackgroundfile_init == u"Resource/Image/Dialog/CAUTION":
                self.ch_fscrbacktype.Select(2)
            else:
                self.ch_fscrbacktype.Select(3)
        elif local.fullscreenbackgroundtype_init == 1:
            self.tx_fscrbackfile.SetValue(local.fullscreenbackgroundfile_init)
            self.ch_fscrbacktype.Select(1)
        else:
            self.tx_fscrbackfile.SetValue("")
            self.ch_fscrbacktype.Select(0)
        self.tx_fscrbackfile.Enable(self.ch_fscrbacktype.GetSelection() == 1)
        self.ref_fscrbackfile.Enable(self.ch_fscrbacktype.GetSelection() == 1)

    def apply_localsettings(self, local):
        updatemessage = False
        alpha = self.sc_mwin.GetValue()
        colour = self.cs_mwin.GetColour()
        colour = (colour[0], colour[1], colour[2], alpha)
        updatemessage |= local.mwincolour <> colour
        local.mwincolour = colour
        alpha = self.sc_mframe.GetValue()
        colour = self.cs_mframe.GetColour()
        colour = (colour[0], colour[1], colour[2], alpha)
        updatemessage |= local.mwinframecolour <> colour
        local.mwinframecolour = colour
        # 配色(バックログ)
        alpha = self.sc_mwin.GetValue()
        colour = self.cs_blwin.GetColour()
        colour = (colour[0], colour[1], colour[2], alpha)
        updatemessage |= local.blwincolour <> colour
        local.blwincolour = colour
        alpha = self.sc_mframe.GetValue()
        colour = self.cs_blframe.GetColour()
        colour = (colour[0], colour[1], colour[2], alpha)
        updatemessage |= local.blwinframecolour <> colour
        local.blwinframecolour = colour

        updatecurtain = False
        # 配色(メッセージログカーテン)
        alpha = self.sc_blcurtain.GetValue()
        colour = self.cs_blcurtain.GetColour()
        colour = (colour[0], colour[1], colour[2], alpha)
        updatecurtain |= local.blcurtaincolour <> colour
        local.blcurtaincolour = colour
        # 配色(選択モードカーテン)
        alpha = self.sc_curtain.GetValue()
        colour = self.cs_curtain.GetColour()
        colour = (colour[0], colour[1], colour[2], alpha)
        updatecurtain |= local.curtaincolour <> colour
        local.curtaincolour = colour

        # フルスクリーンの背景
        value = self.ch_fscrbacktype.GetSelection()
        fullscreenbackgroundfile = local.fullscreenbackgroundfile
        fullscreenbackgroundtype = local.fullscreenbackgroundtype
        if value == 0:
            fullscreenbackgroundfile = u""
            fullscreenbackgroundtype = 0
        elif value == 1:
            fullscreenbackgroundfile = self.tx_fscrbackfile.GetValue()
            fullscreenbackgroundtype = 1
        elif value == 2:
            fullscreenbackgroundfile = u"Resource/Image/Dialog/CAUTION"
            fullscreenbackgroundtype = 2
        elif value == 3:
            fullscreenbackgroundfile = u"Resource/Image/Dialog/PAD"
            fullscreenbackgroundtype = 2

        updatefullscreen = fullscreenbackgroundfile <> local.fullscreenbackgroundfile or\
                           fullscreenbackgroundtype <> local.fullscreenbackgroundtype

        local.fullscreenbackgroundfile = fullscreenbackgroundfile
        local.fullscreenbackgroundtype = fullscreenbackgroundtype

        if self.cb_important and self.cb_important.GetValue() <> local.important_draw:
            local.important_draw = self.cb_important.GetValue()
            updatemessage = True
            updatecurtain = True
            updatefullscreen = True

        return updatemessage, updatecurtain, updatefullscreen

    def _bind(self):
        self.ch_fscrbacktype.Bind(wx.EVT_CHOICE, self.OnFullScreenBackgroundType, id=self.ch_fscrbacktype.GetId())
        if self._for_local:
            self.cb_important.Bind(wx.EVT_CHECKBOX, self.OnImportant)
            if self.copybtn:
                self.copybtn.Bind(wx.EVT_BUTTON, self.OnCopyBase)
            self.initbtn.Bind(wx.EVT_BUTTON, self.OnInitValue)

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer_h1 = wx.BoxSizer(wx.HORIZONTAL)
        if not self._for_local:
            sizer_left = wx.BoxSizer(wx.VERTICAL)
        sizer_right = wx.BoxSizer(wx.VERTICAL)

        if not self._for_local:
            bsizer_gene = wx.StaticBoxSizer(self.box_gene, wx.VERTICAL)

            bsizer_gene.Add(self.cb_smoothing_card_down, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
            bsizer_gene.Add(self.cb_smoothing_card_up, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
            bsizer_gene.Add(self.cb_smooth_bg, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
            #bsizer_gene.Add(self.cb_whitecursor, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
            bsizer_gene.SetMinSize((_settings_width(), -1))

        bsizer_mwin = wx.BoxSizer(wx.HORIZONTAL)
        if self._for_local:
            bsizer_mwin.Add(self.st_mwin, 0, wx.CENTER|wx.RIGHT, cw.ppis(3))
            bsizer_mwin.Add(self.cs_mwin, 0, wx.CENTER|wx.RIGHT, cw.ppis(5))
            bsizer_mwin.Add(self.st_blwin, 0, wx.CENTER|wx.RIGHT, cw.ppis(3))
            bsizer_mwin.Add(self.cs_blwin, 0, wx.CENTER, cw.ppis(0))
        else:
            gsizer_mwin = wx.GridBagSizer()
            gsizer_mwin.Add(self.st_mwin, pos=(0, 0), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=cw.ppis(3))
            gsizer_mwin.Add(self.cs_mwin, pos=(0, 1), flag=wx.EXPAND)
            gsizer_mwin.Add(self.st_blwin, pos=(1, 0), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=cw.ppis(3))
            gsizer_mwin.Add(self.cs_blwin, pos=(1, 1), flag=wx.EXPAND)
            bsizer_mwin.Add(gsizer_mwin, 0, wx.CENTER, cw.ppis(0))
        bsizer_mwin.Add(self.st_mwin2, 0, wx.CENTER|wx.LEFT, cw.ppis(5))
        bsizer_mwin.Add(self.sc_mwin, 0, wx.CENTER|wx.LEFT, cw.ppis(3))
        bsizer_mwin2 = wx.StaticBoxSizer(self.box_mwin, wx.HORIZONTAL)
        bsizer_mwin2.Add(bsizer_mwin, 0, wx.BOTTOM|wx.LEFT|wx.RIGHT, cw.ppis(3))

        bsizer_mframe = wx.BoxSizer(wx.HORIZONTAL)
        if self._for_local:
            bsizer_mframe.Add(self.st_mframe, 0, wx.CENTER|wx.RIGHT, cw.ppis(3))
            bsizer_mframe.Add(self.cs_mframe, 0, wx.CENTER|wx.RIGHT, cw.ppis(5))
            bsizer_mframe.Add(self.st_blframe, 0, wx.CENTER|wx.RIGHT, cw.ppis(3))
            bsizer_mframe.Add(self.cs_blframe, 0, wx.CENTER, cw.ppis(0))
        else:
            gsizer_mframe = wx.GridBagSizer()
            gsizer_mframe.Add(self.st_mframe, pos=(0, 0), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=cw.ppis(3))
            gsizer_mframe.Add(self.cs_mframe, pos=(0, 1), flag=wx.EXPAND)
            gsizer_mframe.Add(self.st_blframe, pos=(1, 0), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=cw.ppis(3))
            gsizer_mframe.Add(self.cs_blframe, pos=(1, 1), flag=wx.EXPAND)
            bsizer_mframe.Add(gsizer_mframe, 0, wx.CENTER, cw.ppis(0))
        bsizer_mframe.Add(self.st_mframe2, 0, wx.CENTER|wx.LEFT, cw.ppis(5))
        bsizer_mframe.Add(self.sc_mframe, 0, wx.CENTER|wx.LEFT, cw.ppis(3))
        bsizer_mframe2 = wx.StaticBoxSizer(self.box_mframe, wx.HORIZONTAL)
        bsizer_mframe2.Add(bsizer_mframe, 0, wx.BOTTOM|wx.LEFT|wx.RIGHT, cw.ppis(3))

        bsizer_blcurtain = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_blcurtain.Add(self.st_blcurtain, 0, wx.RIGHT|wx.CENTER, cw.ppis(3))
        bsizer_blcurtain.Add(self.cs_blcurtain, 0, wx.RIGHT|wx.EXPAND, cw.ppis(5))
        bsizer_blcurtain.Add(self.st_blcurtain2, 0, wx.CENTER|wx.RIGHT, cw.ppis(3))
        bsizer_blcurtain.Add(self.sc_blcurtain, 0, wx.CENTER, cw.ppis(0))
        bsizer_blcurtain2 = wx.StaticBoxSizer(self.box_blcurtain, wx.HORIZONTAL)
        bsizer_blcurtain2.Add(bsizer_blcurtain, 0, wx.BOTTOM|wx.LEFT|wx.RIGHT, cw.ppis(3))

        bsizer_curtain = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_curtain.Add(self.st_curtain, 0, wx.RIGHT|wx.CENTER, cw.ppis(3))
        bsizer_curtain.Add(self.cs_curtain, 0, wx.RIGHT|wx.EXPAND, cw.ppis(5))
        bsizer_curtain.Add(self.st_curtain2, 0, wx.CENTER|wx.RIGHT, cw.ppis(3))
        bsizer_curtain.Add(self.sc_curtain, 0, wx.CENTER, cw.ppis(0))
        bsizer_curtain2 = wx.StaticBoxSizer(self.box_curtain, wx.HORIZONTAL)
        bsizer_curtain2.Add(bsizer_curtain, 0, wx.BOTTOM|wx.LEFT|wx.RIGHT, cw.ppis(3))

        bsizer_fscrback = wx.StaticBoxSizer(self.box_fscrback, wx.VERTICAL)
        bsizer_fscrback.Add(self.ch_fscrbacktype, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_fscrbackfile = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_fscrbackfile.Add(self.tx_fscrbackfile, 1, wx.RIGHT|wx.CENTER, cw.ppis(3))
        bsizer_fscrbackfile.Add(self.ref_fscrbackfile, 0, wx.CENTER, cw.ppis(3))
        bsizer_fscrback.Add(bsizer_fscrbackfile, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))

        if self._for_local:
            sizer_right.Add(self.cb_important, 0, wx.BOTTOM, cw.ppis(5))
        else:
            sizer_left.Add(bsizer_gene, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
            sizer_left.Add(self.speed, 0, wx.EXPAND, cw.ppis(3))

        sizer_right.Add(bsizer_mwin2, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_right.Add(bsizer_mframe2, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_right.Add(bsizer_blcurtain2, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_right.Add(bsizer_curtain2, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_right.Add(bsizer_fscrback, 0, wx.EXPAND, cw.ppis(3))

        if self._for_local:
            sizer_right.AddStretchSpacer(1)
            bsizer_btn = wx.BoxSizer(wx.HORIZONTAL)
            if self.copybtn:
                bsizer_btn.Add(self.copybtn, 0, wx.RIGHT, cw.ppis(3))
            bsizer_btn.Add(self.initbtn, 0, 0, cw.ppis(0))
            sizer_right.Add(bsizer_btn, 0, wx.ALIGN_RIGHT|wx.TOP, cw.ppis(5))

        if self._for_local:
            sizer_h1.Add(sizer_right, 1, wx.EXPAND, cw.ppis(3))
        else:
            sizer_h1.Add(sizer_left, 1, wx.RIGHT|wx.EXPAND, cw.ppis(5))
            sizer_h1.Add(sizer_right, 0, wx.EXPAND, cw.ppis(3))

        sizer.Add(sizer_h1, 1, wx.ALL|wx.EXPAND, cw.ppis(10))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnFullScreenBackgroundType(self, event):
        self.tx_fscrbackfile.Enable(self.ch_fscrbacktype.GetSelection() == 1)
        self.ref_fscrbackfile.Enable(self.ch_fscrbacktype.GetSelection() == 1)

    def OnImportant(self, event):
        self._update_enabled()

    def _update_enabled(self):
        enbl = self.cb_important.GetValue() if self.cb_important else True
        self.cs_mwin.Enable(enbl)
        self.cs_blwin.Enable(enbl)
        self.sc_mwin.Enable(enbl)
        self.cs_mframe.Enable(enbl)
        self.cs_blframe.Enable(enbl)
        self.sc_mframe.Enable(enbl)
        self.cs_curtain.Enable(enbl)
        self.sc_curtain.Enable(enbl)
        self.cs_blcurtain.Enable(enbl)
        self.sc_blcurtain.Enable(enbl)
        self.ch_fscrbacktype.Enable(enbl)
        self.tx_fscrbackfile.Enable(enbl and self.ch_fscrbacktype.GetSelection() == 1)
        self.ref_fscrbackfile.Enable(enbl and self.ch_fscrbacktype.GetSelection() == 1)
        if self._for_local:
            if self.copybtn:
                self.copybtn.Enable(enbl)
            self.initbtn.Enable(enbl)

    def OnInitValue(self, event):
        local = cw.setting.LocalSetting()
        self.init_values(None, local)

    def OnCopyBase(self, event):
        local = self._get_localsettings()
        local.important_draw = True
        self.load(None, local)

class AudioSettingPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self.box_gene = wx.StaticBox(self, -1, u"音響効果")
        # 音楽を再生する
        self.cb_playbgm = wx.CheckBox(
            self, -1, u"BGMを鳴らす")
        # 効果音を再生する
        self.cb_playsound = wx.CheckBox(
            self, -1, u"効果音を鳴らす")

        # 全体音量
        self.box_master = wx.StaticBox(self, -1, u"全体音量")
        self.sl_master = wx.Slider(
            self, -1, 0, 0, 100, size=(_settings_width()-cw.ppis(10), -1),
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS|wx.SL_LABELS)
        self.sl_master.SetTickFreq(10, 1)

        # 音量
        self.box_music = wx.StaticBox(self, -1, u"BGM音量")
        self.sl_music = wx.Slider(
            self, -1, 0, 0, 100, size=(_settings_width()-cw.ppis(10), -1),
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS|wx.SL_LABELS)
        self.sl_music.SetTickFreq(10, 1)

        # midi音量
        self.box_midi = wx.StaticBox(self, -1, u"MIDI音量")
        self.sl_midi = wx.Slider(
            self, -1, 0, 0, 100, size=(_settings_width()-cw.ppis(10), -1),
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS|wx.SL_LABELS)
        self.sl_midi.SetTickFreq(10, 1)

        # 効果音音量
        self.box_sound = wx.StaticBox(self, -1, u"効果音音量")
        self.sl_sound = wx.Slider(
            self, -1, 0, 0, 100, size=(_settings_width()-cw.ppis(10), -1),
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS|wx.SL_LABELS)
        self.sl_sound.SetTickFreq(10, 1)

        # サウンドフォント
        self.box_soundfont = wx.StaticBox(self, -1, u"MIDIサウンドフォント")
        self.btn_addsoundfont = wx.Button(self, -1, u"追加...")
        self.btn_rmvsoundfont = wx.Button(self, -1, u"削除")
        self.btn_upsoundfont = wx.Button(self, -1, u"↑", size=(cw.ppis(25), -1))
        self.btn_downsoundfont = wx.Button(self, -1, u"↓", size=(cw.ppis(25), -1))
        self.list_soundfont = cw.util.CheckableListCtrl(self, -1, size=(_settings_width(), -1),
                                                        style=wx.MULTIPLE|wx.VSCROLL|wx.HSCROLL,
                                                        system=True)

        self._do_layout()
        self._bind()

    def load(self, setting):
        self.cb_playbgm.SetValue(setting.play_bgm)
        self.cb_playsound.SetValue(setting.play_sound)
        n = int(setting.vol_master * 100)
        self.sl_master.SetValue(n)
        n = int(setting.vol_bgm * 100)
        self.sl_music.SetValue(n)
        n = int(setting.vol_midi * 100)
        self.sl_midi.SetValue(n)
        n = int(setting.vol_sound * 100)
        self.sl_sound.SetValue(n)
        self.list_soundfont.DeleteAllItems()
        for index, soundfont in enumerate(setting.soundfonts):
            sfont, use = soundfont
            self.list_soundfont.InsertStringItem(index, sfont)
            self.list_soundfont.CheckItem(index, use)

    def init_values(self, setting):
        self.cb_playbgm.SetValue(setting.play_bgm_init)
        self.cb_playsound.SetValue(setting.play_sound_init)
        self.sl_master.SetValue(int(setting.vol_master_init * 100))
        self.sl_music.SetValue(int(setting.vol_bgm_init * 100))
        self.sl_midi.SetValue(int(setting.vol_midi_init * 100))
        self.sl_sound.SetValue(int(setting.vol_sound_init * 100))
        self.list_soundfont.DeleteAllItems()
        for index, soundfont in enumerate(setting.soundfonts_init):
            sfont, use = soundfont
            self.list_soundfont.InsertStringItem(index, sfont)
            self.list_soundfont.CheckItem(index, use)

    def _bind(self):
        self.Bind(wx.EVT_BUTTON, self.OnAddSoundFontBtn, self.btn_addsoundfont)
        self.Bind(wx.EVT_BUTTON, self.OnRemoveSoundFontBtn, self.btn_rmvsoundfont)
        self.Bind(wx.EVT_BUTTON, self.OnUpSoundFontBtn, self.btn_upsoundfont)
        self.Bind(wx.EVT_BUTTON, self.OnDownSoundFontBtn, self.btn_downsoundfont)
        self.list_soundfont.OnCheckItem = self.OnGridCellChanged

    def OnGridCellChanged(self, index, flag):
        self.list_soundfont.DefaultOnCheckItem(index, flag)
        self.GetTopLevelParent().applied()

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer_h1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_left = wx.BoxSizer(wx.VERTICAL)
        sizer_right = wx.BoxSizer(wx.VERTICAL)

        bsizer_gene = wx.StaticBoxSizer(self.box_gene, wx.VERTICAL)
        bsizer_master = wx.StaticBoxSizer(self.box_master, wx.VERTICAL)
        bsizer_music = wx.StaticBoxSizer(self.box_music, wx.VERTICAL)
        bsizer_midi = wx.StaticBoxSizer(self.box_midi, wx.VERTICAL)
        bsizer_sound = wx.StaticBoxSizer(self.box_sound, wx.VERTICAL)
        bsizer_soundfont = wx.StaticBoxSizer(self.box_soundfont, wx.VERTICAL)

        bsizer_gene.Add(self.cb_playbgm, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.Add(self.cb_playsound, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.SetMinSize((_settings_width(), -1))

        sizer_soundfontbtns = wx.BoxSizer(wx.HORIZONTAL)
        sizer_soundfontbtns.Add(self.btn_addsoundfont, 0, wx.RIGHT, cw.ppis(3))
        sizer_soundfontbtns.Add(self.btn_rmvsoundfont, 0, wx.RIGHT, cw.ppis(3))
        sizer_soundfontbtns.Add(self.btn_upsoundfont, 0, wx.RIGHT, cw.ppis(3))
        sizer_soundfontbtns.Add(self.btn_downsoundfont, 0, 0, cw.ppis(0))

        bsizer_master.Add(self.sl_master, 0, wx.EXPAND, cw.ppis(0))
        bsizer_music.Add(self.sl_music, 0, wx.EXPAND, cw.ppis(0))
        bsizer_midi.Add(self.sl_midi, 0, wx.EXPAND, cw.ppis(0))
        bsizer_sound.Add(self.sl_sound, 0, wx.EXPAND, cw.ppis(0))
        bsizer_soundfont.Add(sizer_soundfontbtns, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_soundfont.Add(self.list_soundfont, 1, wx.EXPAND|wx.LEFT|wx.BOTTOM|wx.RIGHT, cw.ppis(3))

        sizer_left.Add(bsizer_gene, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_left.Add(bsizer_master, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_left.Add(bsizer_music, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_left.Add(bsizer_midi, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_left.Add(bsizer_sound, 0, wx.EXPAND, cw.ppis(3))

        sizer_right.Add(bsizer_soundfont, 1, wx.EXPAND, cw.ppis(0))

        sizer_h1.Add(sizer_left, 0, wx.RIGHT|wx.EXPAND, cw.ppis(5))
        sizer_h1.Add(sizer_right, 1, wx.EXPAND, cw.ppis(3))

        sizer.Add(sizer_h1, 1, wx.ALL|wx.EXPAND, cw.ppis(10))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnAddSoundFontBtn(self, event):
        dlg = wx.FileDialog(self.GetTopLevelParent(), u"MIDIの演奏に使用するサウンドフォント選択", u"Data/SoundFont", "", "*.sf2", wx.FD_OPEN|wx.FD_MULTIPLE)
        if dlg.ShowModal() == wx.ID_OK:
            exists = set()
            index = -1
            for index in xrange(self.list_soundfont.GetItemCount()):
                soundfont = self.list_soundfont.GetItemText(index)
                exists.add(soundfont.lower())

            for fname in dlg.GetFilenames():
                fpath = os.path.join(dlg.GetDirectory(), fname)
                try:
                    rel = cw.util.relpath(fpath, u"")
                    if not rel.startswith(u".."):
                        fpath = rel
                except:
                    cw.util.print_ex()
                fpath = cw.util.join_paths(fpath)
                if fpath.lower() in exists:
                    continue
                index = self.list_soundfont.GetItemCount()
                self.list_soundfont.InsertStringItem(index, fpath)
                self.list_soundfont.CheckItem(index, True)
                self.GetTopLevelParent().applied()

    def OnRemoveSoundFontBtn(self, event):
        while True:
            index = self.list_soundfont.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if index < 0:
                break
            self.list_soundfont.DeleteItem(index)
            self.GetTopLevelParent().applied()

    def OnUpSoundFontBtn(self, event):
        index = -1
        while True:
            index = self.list_soundfont.GetNextItem(index, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if index <= 0:
                break
            item = self.list_soundfont.GetItemText(index)
            use = self.list_soundfont.IsChecked(index)
            self.list_soundfont.DeleteItem(index)
            self.list_soundfont.InsertStringItem(index - 1, item)
            self.list_soundfont.CheckItem(index - 1, use)
            self.list_soundfont.Select(index - 1)
            self.GetTopLevelParent().applied()

    def OnDownSoundFontBtn(self, event):
        indexes = []
        index = -1
        while True:
            index = self.list_soundfont.GetNextItem(index, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if index < 0:
                break
            indexes.append(index)

        if not indexes or self.list_soundfont.GetItemCount() <= indexes[-1] + 1:
            return

        indexes.reverse()
        for index in indexes:
            item = self.list_soundfont.GetItemText(index)
            use = self.list_soundfont.IsChecked(index)
            self.list_soundfont.DeleteItem(index)
            self.list_soundfont.InsertStringItem(index + 1, item)
            self.list_soundfont.CheckItem(index + 1, use)
            self.list_soundfont.Select(index + 1)
            self.GetTopLevelParent().applied()

class ScenarioSettingPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        # シナリオのオプション
        self.box_gene = wx.StaticBox(self, -1, u"シナリオの選択")
        self.cb_show_paperandtree = wx.CheckBox(self, -1, u"シナリオ選択ダイアログで貼紙と一覧を同時に表示する")
        self.cb_open_lastscenario = wx.CheckBox(
            self, -1, u"最後に選んだシナリオを開始位置にする")
        self.cb_selectscenariofromtype = wx.CheckBox(self, -1, u"シナリオ選択の初期位置をスキンタイプ別に変更")
        self.cb_selectscenariofromtype.SetToolTipString( u"シナリオフォルダ(スキンタイプ別)で設定した場所をデフォルトの開始位置にします\n無効にした場合はScenarioを読みます")


        # その他オプション
        self.box_other = wx.StaticBox(self, -1, u"その他")
        self.cb_show_debuglogdialog = wx.CheckBox(
            self, -1, u"シナリオの終了時にデバッグ情報を表示する")
        self.cb_write_playlog = wx.CheckBox(self, -1, u"シナリオのプレイログをテキスト出力する")
        self.cb_oldf9 = wx.CheckBox(
            self, -1, u"CardWirth1.28由来のF9仕様を使用する")
        self.cb_oldf9.SetToolTipString( u"有効化非推奨\nシナリオによって変更された終了印・ゴシップがF9でリセットされなくなります")


        # スキンタイプ毎の初期フォルダ
        self.box_folderoftype = wx.StaticBox(self, -1, u"シナリオフォルダ(スキンタイプ別)")
        self.btn_reffolder = wx.Button(self, -1, u"参照...")
        self.btn_removefolder = wx.Button(self, -1, u"削除")
        self.btn_upfolder = wx.Button(self, -1, u"↑", size=(cw.ppis(25), -1))
        self.btn_downfolder = wx.Button(self, -1, u"↓", size=(cw.ppis(25), -1))

        self.btn_constructdb = wx.Button(self, -1, u"データベース構築...", size=(-1, -1))

        self.grid_folderoftype = wx.grid.Grid(self, -1, style=wx.BORDER)
        self.grid_folderoftype.CreateGrid(0, 2)
        #self.grid_folderoftype.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)

        self.celleditor = None

        # シナリオエディタ
        self.box_application = wx.StaticBox(self, -1, u"外部アプリ")
        self.st_editor = wx.StaticText(self, -1, u"エディタ")
        self.tx_editor = wx.TextCtrl(self, -1, size=(-1, -1), style=wx.SIMPLE_BORDER)
        if sys.platform == "win32":
            wildcard = u"実行可能ファイル (*.exe)|*.exe|全てのファイル (*.*)|*.*"
        else:
            wildcard = u"全てのファイル (*.*)|*.*"
        self.ref_editor = cw.util.create_fileselection(self,
            target=self.tx_editor,
            message=u"CardWirthのシナリオエディタを選択",
            wildcard=wildcard)

        # シナリオ選択ダイアログでのファイラー(フォルダ用)
        self.st_filer_dir = wx.StaticText(self, -1, u"ファイラー(フォルダ用)")
        self.tx_filer_dir = wx.TextCtrl(self, -1, size=(-1, -1), style=wx.SIMPLE_BORDER)
        self.ref_filer_dir = cw.util.create_fileselection(self,
            target=self.tx_filer_dir,
            message=u"シナリオの場所を開くためのファイラー(フォルダ用)を選択",
            wildcard=wildcard)
        # シナリオ選択ダイアログでのファイラー(ファイル用)
        self.st_filer_file = wx.StaticText(self, -1, u"ファイラー(ファイル用)")
        self.tx_filer_file = wx.TextCtrl(self, -1, size=(-1, -1), style=wx.SIMPLE_BORDER)
        self.ref_filer_file = cw.util.create_fileselection(self,
            target=self.tx_filer_file,
            message=u"シナリオの場所を開くためのファイラー(ファイル用)を選択",
            wildcard=wildcard)

        w, h, _lh = 0, 0, 0
        for obj in (self.st_editor, self.st_filer_dir, self.st_filer_file):
            dc = wx.ClientDC(obj)
            w2, h2, _lh = dc.GetMultiLineTextExtent(obj.GetLabel())
            w = max(w, w2)
            h = max(h, h2)
        for obj in (self.st_editor, self.st_filer_dir, self.st_filer_file):
            obj.SetMinSize((w + cw.ppis(15), h))

        self._do_layout()
        self._bind()

    def load(self, setting):
        self.cb_selectscenariofromtype.SetValue(setting.selectscenariofromtype)
        self.cb_show_paperandtree.SetValue(setting.show_paperandtree)
        self.cb_write_playlog.SetValue(setting.write_playlog)
        self.cb_show_debuglogdialog.SetValue(setting.show_debuglogdialog)
        self.cb_open_lastscenario.SetValue(setting.open_lastscenario)
        self.cb_oldf9.SetValue(setting.enable_oldf9)

        if 0 < self.grid_folderoftype.GetNumberRows():
            self.grid_folderoftype.DeleteRows(0, self.grid_folderoftype.GetNumberRows())
        self.grid_folderoftype.InsertRows(0, len(setting.folderoftype) + 1)
        self.grid_folderoftype.SetColLabelSize(cw.ppis(0))
        self.grid_folderoftype.SetRowLabelSize(cw.ppis(0))
        self.grid_folderoftype.SetColSize(0, cw.ppis(100))
        self.grid_folderoftype.SetColSize(1, cw.ppis(370))
        for row in xrange(self.grid_folderoftype.GetNumberRows() - 1):
            skintype, folder = setting.folderoftype[row]
            self.grid_folderoftype.SetCellValue(row, 0, skintype)
            self.grid_folderoftype.SetCellValue(row, 1, folder)
        self.tx_editor.SetValue(setting.editor)
        self.tx_filer_dir.SetValue(setting.filer_dir)
        self.tx_filer_file.SetValue(setting.filer_file)

    def init_values(self, setting):
        self.tx_editor.SetValue(setting.editor_init)
        self.cb_selectscenariofromtype.SetValue(setting.selectscenariofromtype_init)
        self.cb_show_paperandtree.SetValue(setting.show_paperandtree)
        self.cb_write_playlog.SetValue(setting.write_playlog)
        self.cb_show_debuglogdialog.SetValue(setting.show_debuglogdialog_init)
        self.cb_open_lastscenario.SetValue(setting.open_lastscenario_init)
        self.cb_oldf9.SetValue(setting.enable_oldf9_init)

        self.tx_filer_dir.SetValue(setting.filer_dir_init)
        self.tx_filer_file.SetValue(setting.filer_file_init)

    def OnGirdSelectCell(self, event):
        if self.celleditor:
            return
        types = set()
        self.Parent.Parent.pane_gene.skin.load_allskins()
        for t in self.Parent.Parent.pane_gene.skin.skin_summarys.itervalues():
            skintype, _skinname, _author, _desc, _vocation120, _initialcash = t
            types.add(skintype)

        types = list(types)
        cw.util.sort_by_attr(types)

        colattr = wx.grid.GridCellAttr()
        self.celleditor = wx.grid.GridCellChoiceEditor(types, allowOthers=True)
        colattr.SetEditor(self.celleditor)
        self.grid_folderoftype.SetColAttr(0, colattr)

    def _bind(self):
        self.Bind(wx.EVT_BUTTON, self.OnRefFolderBtn, self.btn_reffolder)
        self.Bind(wx.EVT_BUTTON, self.OnRemoveFolderBtn, self.btn_removefolder)
        self.Bind(wx.EVT_BUTTON, self.OnUpFolderBtn, self.btn_upfolder)
        self.Bind(wx.EVT_BUTTON, self.OnDownFolderBtn, self.btn_downfolder)
        self.Bind(wx.EVT_BUTTON, self.OnConstructDBBtn, self.btn_constructdb)
        self.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.OnGridCellChange, self.grid_folderoftype)
        self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnGirdSelectCell, self.grid_folderoftype)

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v2 = wx.GridSizer( 0, 2, 0, 0 )

        bsizer_gene = wx.StaticBoxSizer(self.box_gene, wx.VERTICAL)
        bsizer_other = wx.StaticBoxSizer(self.box_other, wx.VERTICAL)
        bsizer_folderoftype = wx.StaticBoxSizer(self.box_folderoftype, wx.VERTICAL)

        bsizer_gene.Add(self.cb_show_paperandtree, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.Add(self.cb_open_lastscenario, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.Add(self.cb_selectscenariofromtype, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        #bsizer_gene.SetMinSize((_settings_width(), -1))

        bsizer_other.Add(self.cb_show_debuglogdialog, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_other.Add(self.cb_write_playlog, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_other.Add(self.cb_oldf9, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))

        sizer_v2.Add(bsizer_gene, 1, wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v2.Add(bsizer_other, 1, wx.LEFT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))

        sizer_folderbtns = wx.BoxSizer(wx.HORIZONTAL)
        sizer_folderbtns.Add(self.btn_reffolder, 0, wx.RIGHT, cw.ppis(3))
        sizer_folderbtns.Add(self.btn_removefolder, 0, wx.RIGHT, cw.ppis(3))
        sizer_folderbtns.Add(self.btn_upfolder, 0, wx.RIGHT, cw.ppis(3))
        sizer_folderbtns.Add(self.btn_downfolder, 0, wx.RIGHT, cw.ppis(3))
        sizer_folderbtns.Add(cw.ppis((0, 0)), 1, 0, cw.ppis(0))
        sizer_folderbtns.Add(self.btn_constructdb, 0, 0, cw.ppis(0))

        bsizer_folderoftype.Add(sizer_folderbtns, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        bsizer_folderoftype.Add(self.grid_folderoftype, 1, wx.EXPAND|wx.LEFT|wx.BOTTOM|wx.RIGHT, cw.ppis(3))

        bsizer_application = wx.StaticBoxSizer(self.box_application, wx.VERTICAL)
        gbsizer_application = wx.GridBagSizer()

        def add_application(ctrl, pos, flag):
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(ctrl, 1, wx.ALIGN_CENTER_VERTICAL, 0)
            gbsizer_application.Add(sizer, pos=pos, flag=flag|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, border=cw.ppis(2))

        add_application(self.st_editor, pos=(0, 0), flag=wx.RIGHT|wx.BOTTOM)
        add_application(self.tx_editor, pos=(0, 1), flag=wx.RIGHT|wx.BOTTOM)
        add_application(self.ref_editor, pos=(0, 2), flag=wx.BOTTOM)
        add_application(self.st_filer_dir, pos=(1, 0), flag=wx.RIGHT|wx.BOTTOM)
        add_application(self.tx_filer_dir, pos=(1, 1), flag=wx.RIGHT|wx.BOTTOM)
        add_application(self.ref_filer_dir, pos=(1, 2), flag=wx.BOTTOM)
        add_application(self.st_filer_file, pos=(2, 0), flag=wx.RIGHT)
        add_application(self.tx_filer_file, pos=(2, 1), flag=wx.RIGHT)
        add_application(self.ref_filer_file, pos=(2, 2), flag=0)
        gbsizer_application.AddGrowableCol(1)
        bsizer_application.Add(gbsizer_application, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))

        sizer_v1.Add(sizer_v2, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v1.Add(bsizer_folderoftype, 1, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v1.Add(bsizer_application, 0, wx.EXPAND, cw.ppis(0))

        sizer.Add(sizer_v1, 1, wx.ALL|wx.EXPAND, cw.ppis(10))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnGridCellChange(self, event):
        if event.Col == 0 and event.Row + 1 == self.grid_folderoftype.GetNumberRows() and\
                self.grid_folderoftype.GetCellValue(event.Row, 0):
            self.grid_folderoftype.AppendRows(1)

    def OnRefFolderBtn(self, event):
        row = self.grid_folderoftype.GetGridCursorRow()
        if row == -1:
            return

        skintype = self.grid_folderoftype.GetCellValue(row, 0)
        if not skintype:
            skintype = u"(指定無し)"

        dpath = os.path.abspath("Scenario")
        dlg = wx.DirDialog(self.TopLevelParent, u"「%s」タイプのスキンでプレイするシナリオのフォルダを選択してください。" % (skintype), dpath, style=wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            dpath = dlg.GetPath()
            relpath = cw.util.relpath(dpath, ".")
            if not relpath.startswith(".."):
                dpath = relpath
            self.grid_folderoftype.SetCellValue(row, 1, cw.util.join_paths(dpath))
            self.GetTopLevelParent().applied()

    def OnRemoveFolderBtn(self, event):
        row = self.grid_folderoftype.GetGridCursorRow()
        if row == -1 or row + 1 == self.grid_folderoftype.GetNumberRows():
            return
        self.grid_folderoftype.DeleteRows(row)
        self.GetTopLevelParent().applied()

    def OnUpFolderBtn(self, event):
        row = self.grid_folderoftype.GetGridCursorRow()
        if row == -1 or row == 0:
            return
        for col in xrange(self.grid_folderoftype.GetNumberCols()):
            value1 = self.grid_folderoftype.GetCellValue(row, col)
            value2 = self.grid_folderoftype.GetCellValue(row - 1, col)
            self.grid_folderoftype.SetCellValue(row, col, value2)
            self.grid_folderoftype.SetCellValue(row - 1, col, value1)
            self.GetTopLevelParent().applied()
        self.grid_folderoftype.SetGridCursor(row - 1, self.grid_folderoftype.GetGridCursorCol())

    def OnDownFolderBtn(self, event):
        row = self.grid_folderoftype.GetGridCursorRow()
        if row == -1 or self.grid_folderoftype.GetNumberRows() <= row + 2:
            return
        for col in xrange(self.grid_folderoftype.GetNumberCols()):
            value1 = self.grid_folderoftype.GetCellValue(row, col)
            value2 = self.grid_folderoftype.GetCellValue(row + 1, col)
            self.grid_folderoftype.SetCellValue(row, col, value2)
            self.grid_folderoftype.SetCellValue(row + 1, col, value1)
            self.GetTopLevelParent().applied()
        self.grid_folderoftype.SetGridCursor(row + 1, self.grid_folderoftype.GetGridCursorCol())

    def OnConstructDBBtn(self, event):
        d = {}
        for row in xrange(self.grid_folderoftype.GetNumberRows()):
            skintype = self.grid_folderoftype.GetCellValue(row, 0)
            dpath = self.grid_folderoftype.GetCellValue(row, 1)
            if not dpath:
                continue
            if skintype in d:
                s = d[skintype]
            else:
                s = set()
                d[skintype] = s
            dpath = cw.util.get_linktarget(dpath)
            if os.path.isdir(dpath):
                s.add(dpath)

        if os.path.isdir(u"Scenario"):
            if not cw.cwpy.setting.skintype in d:
                d[cw.cwpy.setting.skintype] = set([u"Scenario"])
            elif not d:
                d[u""] = set([u"Scenario"])

        dlg = editscenariodb.ConstructScenarioDB(self.TopLevelParent, dpaths=d)
        cw.cwpy.frame.move_dlg(dlg)
        dlg.ShowModal()
        dlg.Destroy()

class UISettingPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        # マウスオプション
        self.box_wait = wx.StaticBox(self, -1, u"マウス操作とスキップ")
        self.cb_can_skipwait = wx.CheckBox(
            self, -1, u"空白時間をスキップ可能にする")
        self.cb_can_skipanimation = wx.CheckBox(
            self, -1, u"アニメーションをスキップ可能にする")
        self.cb_can_repeatlclick = wx.CheckBox(
            self, -1, u"マウスの左ボタンを押し続けた時は連打状態にする")
        self.cb_autoenter_on_sprite = wx.CheckBox(
            self, -1, u"連打状態の時、カードなどの選択を自動的に決定")
        self.cb_can_clicksidesofcardcontrol = wx.CheckBox(
            self, -1, u"カード選択ダイアログの背景クリックで左右移動を行う")
        self.cb_wheel_movefocus = wx.CheckBox(
            self, -1, u"ホイールでカード選択と選択肢のフォーカス移動を行う")
        self.cb_wheel_movefocus.SetToolTipString(u"ホイール上でのログ表示が有効な場合はログ表示が優先")
        self.cb_showlogwithwheelup = wx.CheckBox(
            self, -1, u"ホイールを上に回すとログを表示")
        self.st_wheel_down = wx.StaticText(self, -1,
                                                     u"ホイール下の動作:")
        self.cb_can_skipwait_with_wheel = wx.CheckBox(
            self, -1, u"スキップ")
        self.cb_can_forwardmessage_with_wheel = wx.CheckBox(
            self, -1, u"メッセージ送り")

        # 描画オプション
        self.box_draw = wx.StaticBox(self, -1, u"カード")
        self.st_quickdeal = wx.StaticText(self, -1,
                                                     u"メニューの高速表示:")
        choices = [u"全てのシステムカード", u"キャンプモードへの切替のみ", u"使用しない"]
        self.st_quickdeal.SetToolTipString( u"一度にカードアニメーションを行うことで瞬時に画面を移行します" )
        self.ch_quickdeal = wx.Choice(self, -1, choices=choices)
        self.cb_show_cardkind = wx.CheckBox(
            self, -1, u"カード置場と荷物袋でカードの種類を表示する")
        self.cb_show_premiumicon = wx.CheckBox(
            self, -1, u"カードの希少度をアイコンで表示する(1.20方式)")

        # インタフェースオプション
        self.box_gene = wx.StaticBox(self, -1, u"インターフェース補助")
        self.st_showbackpackcard = wx.StaticText(self, -1,
                                                     u"荷物袋のカードを一時的に使用:")
        self.st_showbackpackcard.SetToolTipString( u"シナリオ中、テーブルモードでキャラクターの手札に特殊カードが配置されます" )
        choices = [u"最初に配置", u"最後に配置", u"使用しない"]
        self.ch_showbackpackcard = wx.Choice(self, -1, choices=choices)
        self.cb_revertcardpocket = wx.CheckBox(
            self, -1, u"レベル調節で手放したカードを自動的に戻す")
        self.cb_show_addctrlbtn = wx.CheckBox(
            self, -1, u"選択ダイアログで検索モード切替ボタンを追加(Ctrl+F)")
        self.cb_show_addctrlbtn.SetToolTipString( u"非表示にしてもCtrl+Fは有効" )
        self.cb_showautobuttoninentrydialog = wx.CheckBox(
            self, -1, u"キャラクターの新規登録で自動ボタンを追加")
        self.cb_protect_premiercard = wx.CheckBox(
            self, -1, u"プレミアカードの売却や破棄を禁止する")

        # 戦闘オプション
        self.box_battle = wx.StaticBox(self, -1, u"戦闘")
        self.cb_showroundautostartbutton = wx.CheckBox(
            self, -1, u"自動で行動開始するボタンを追加(F7)")
        self.cb_showallselectedcards = wx.CheckBox(
            self, -1, u"戦闘行動を全員分表示する")
        self.cb_showstatustime = wx.CheckBox(
            self, -1, u"状態の残り時間をカード上に表示する")

        # 通知オプション
        self.box_notice = wx.StaticBox(self, -1, u"通知と解説")
        self.cb_show_experiencebar = wx.CheckBox(
            self, -1, u"キャラクター情報に次のレベルアップまでの割合を表示")
        self.cb_show_btndesc = wx.CheckBox(
            self, -1, u"ステータスバーで解説を表示する")
        self.cb_statusbarmask = wx.CheckBox(
            self, -1, u"イベント中にステータスバーの色を変える")
        self.cb_blink_statusbutton = wx.CheckBox(
            self, -1, u"通知のあるステータスボタンを点滅させる")
        self.cb_blink_partymoney = wx.CheckBox(
            self, -1, u"所持金が増減した時に所持金欄を点滅させる")

        #self.cb_protect_staredcard = wx.CheckBox(
        #    self, -1, u"スター付きのカードの売却や破棄を禁止する")

        # ダイアログオプション
        self.box_dlg = wx.StaticBox(self, -1, u"ダイアログ省略")

        self.st_confirm_beforesaving = wx.StaticText(self, -1,
                                                     u"セーブ前の確認メッセージ:")
        choices = [u"常に表示", u"拠点にいる時だけ表示", u"表示しない"]
        self.ch_confirm_beforesaving = wx.Choice(self, -1, choices=choices)
        self.cb_showsavedmessage = wx.CheckBox(
            self, -1, u"セーブ完了時に確認メッセージを表示")
        self.st_confirm_card = wx.StaticText(self, -1,
                                                     u"カード操作の確認:")
        self.cb_confirmbeforeusingcard = wx.CheckBox(
            self, -1, u"カード使用時")
        self.cb_confirm_dumpcard = wx.CheckBox(
            self, -1, u"売却・破棄時")
        self.cb_noticeimpossibleaction = wx.CheckBox(
            self, -1, u"不可能な行動を選択した時に警告を表示")
        self.cb_noticeimpossibleaction.SetToolTipString( u"Capを超えてカードを配ろうとしたり、戦闘中に行動不能キャストをクリックした時など" )
        self.cb_cautionbeforesaving = wx.CheckBox(
            self, -1, u"保存せずに終了しようとしたら警告を表示")

        self._do_layout()
        #self._bind()

    def load(self, setting):
        self.cb_can_skipwait.SetValue(setting.can_skipwait)
        self.cb_can_skipanimation.SetValue(setting.can_skipanimation)
        self.cb_can_skipwait_with_wheel.SetValue(setting.can_skipwait_with_wheel)
        self.cb_can_forwardmessage_with_wheel.SetValue(setting.can_forwardmessage_with_wheel)
        self.cb_can_repeatlclick.SetValue(setting.can_repeatlclick)
        self.cb_autoenter_on_sprite.SetValue(setting.autoenter_on_sprite)
        self.cb_wheel_movefocus.SetValue(setting.wheel_movefocus)

        if setting.all_quickdeal:
            self.ch_quickdeal.SetSelection(0)
        elif setting.quickdeal:
            self.ch_quickdeal.SetSelection(1)
        else:
            self.ch_quickdeal.SetSelection(2)
        self.cb_showallselectedcards.SetValue(setting.show_allselectedcards)
        self.cb_showstatustime.SetValue(setting.show_statustime)
        self.cb_show_cardkind.SetValue(setting.show_cardkind)
        self.cb_show_premiumicon.SetValue(setting.show_premiumicon)

        if setting.show_backpackcardatend:
            self.ch_showbackpackcard.SetSelection(1)
        elif setting.show_backpackcard:
            self.ch_showbackpackcard.SetSelection(0)
        else:
            self.ch_showbackpackcard.SetSelection(2)
        self.cb_can_clicksidesofcardcontrol.SetValue(setting.can_clicksidesofcardcontrol)
        self.cb_revertcardpocket.SetValue(setting.revert_cardpocket)
        self.cb_showlogwithwheelup.SetValue(setting.wheelup_operation == cw.setting.WHEEL_SHOWLOG)
        self.cb_showroundautostartbutton.SetValue(setting.show_roundautostartbutton)
        self.cb_showautobuttoninentrydialog.SetValue(setting.show_autobuttoninentrydialog)
        #self.cb_protect_staredcard.SetValue(setting.protect_staredcard)
        self.cb_protect_premiercard.SetValue(setting.protect_premiercard)

        self.cb_show_btndesc.SetValue(setting.show_btndesc)
        self.cb_statusbarmask.SetValue(setting.statusbarmask)
        self.cb_blink_statusbutton.SetValue(setting.blink_statusbutton)
        self.cb_blink_partymoney.SetValue(setting.blink_partymoney)

        if setting.confirm_beforesaving == cw.setting.CONFIRM_BEFORESAVING_BASE:
            self.ch_confirm_beforesaving.SetSelection(1)
        elif setting.confirm_beforesaving == cw.setting.CONFIRM_BEFORESAVING_NO:
            self.ch_confirm_beforesaving.SetSelection(2)
        else:
            self.ch_confirm_beforesaving.SetSelection(0)
        self.cb_cautionbeforesaving.SetValue(setting.caution_beforesaving)
        self.cb_showsavedmessage.SetValue(setting.show_savedmessage)

        self.cb_show_addctrlbtn.SetValue(setting.show_addctrlbtn)
        self.cb_show_experiencebar.SetValue(setting.show_experiencebar)
        self.cb_confirmbeforeusingcard.SetValue(setting.confirm_beforeusingcard)
        self.cb_confirm_dumpcard.SetValue(setting.confirm_dumpcard)
        self.cb_noticeimpossibleaction.SetValue(setting.noticeimpossibleaction)

    def init_values(self, setting):
        self.cb_can_skipwait.SetValue(setting.can_skipwait_init)
        self.cb_can_skipanimation.SetValue(setting.can_skipanimation_init)
        self.cb_can_skipwait_with_wheel.SetValue(setting.can_skipwait_with_wheel_init)
        self.cb_can_forwardmessage_with_wheel.SetValue(setting.can_forwardmessage_with_wheel_init)
        self.cb_can_repeatlclick.SetValue(setting.can_repeatlclick_init)
        self.cb_autoenter_on_sprite.SetValue(setting.autoenter_on_sprite_init)
        self.cb_wheel_movefocus.SetValue(setting.wheel_movefocus_init)

        if setting.all_quickdeal_init:
            self.ch_quickdeal.SetSelection(0)
        elif setting.quickdeal_init:
            self.ch_quickdeal.SetSelection(1)
        else:
            self.ch_quickdeal.SetSelection(2)
        self.cb_showallselectedcards.SetValue(setting.show_allselectedcards_init)
        self.cb_showstatustime.SetValue(setting.show_statustime_init)
        self.cb_show_cardkind.SetValue(setting.show_cardkind_init)
        self.cb_show_premiumicon.SetValue(setting.show_premiumicon_init)
        self.cb_showroundautostartbutton.SetValue(setting.show_roundautostartbutton_init)
        self.cb_showautobuttoninentrydialog.SetValue(setting.show_autobuttoninentrydialog_init)
        #self.cb_protect_staredcard.SetValue(setting.protect_staredcard_init)
        self.cb_protect_premiercard.SetValue(setting.protect_premiercard_init)

        self.cb_show_btndesc.SetValue(setting.show_btndesc_init)
        self.cb_statusbarmask.SetValue(setting.statusbarmask_init)
        self.cb_blink_statusbutton.SetValue(setting.blink_statusbutton_init)
        self.cb_blink_partymoney.SetValue(setting.blink_partymoney_init)

        self.cb_show_addctrlbtn.SetValue(setting.show_addctrlbtn_init)
        self.cb_show_experiencebar.SetValue(setting.show_experiencebar_init)

        if cw.setting.CONFIRM_BEFORESAVING_BASE == setting.confirm_beforesaving_init:
            self.ch_confirm_beforesaving.SetSelection(1)
        elif not cw.util.str2bool(setting.confirm_beforesaving_init):
            self.ch_confirm_beforesaving.SetSelection(2)
        else:
            self.ch_confirm_beforesaving.SetSelection(0)
        self.cb_showsavedmessage.SetValue(setting.show_savedmessage_init)
        self.cb_cautionbeforesaving.SetValue(setting.caution_beforesaving_init)

        if setting.show_backpackcardatend_init:
            self.ch_showbackpackcard.SetSelection(1)
        elif setting.show_backpackcard_init:
            self.ch_showbackpackcard.SetSelection(0)
        else:
            self.ch_showbackpackcard.SetSelection(2)
        self.cb_can_clicksidesofcardcontrol.SetValue(setting.can_clicksidesofcardcontrol_init)
        self.cb_revertcardpocket.SetValue(setting.revert_cardpocket_init)
        self.cb_showlogwithwheelup.SetValue(setting.wheelup_operation_init == cw.setting.WHEEL_SHOWLOG)
        self.cb_confirmbeforeusingcard.SetValue(setting.confirm_beforeusingcard_init)
        self.cb_confirm_dumpcard.SetValue(setting.confirm_dumpcard_init)

        self.cb_noticeimpossibleaction.SetValue(setting.noticeimpossibleaction_init)

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v2 = wx.BoxSizer(wx.VERTICAL)
        sizer_v3 = wx.GridSizer( 0, 2, 0, 0 )
        bsizer_wait = wx.StaticBoxSizer(self.box_wait, wx.VERTICAL)
        bsizer_draw = wx.StaticBoxSizer(self.box_draw, wx.VERTICAL)
        bsizer_gene = wx.StaticBoxSizer(self.box_gene, wx.VERTICAL)
        bsizer_notice = wx.StaticBoxSizer(self.box_notice, wx.VERTICAL)
        bsizer_battle = wx.StaticBoxSizer(self.box_battle, wx.VERTICAL)
        bsizer_dlg = wx.StaticBoxSizer(self.box_dlg, wx.VERTICAL)

        bsizer_wait.Add(self.cb_can_skipwait, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wait.Add(self.cb_can_skipanimation, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wait.Add(self.cb_can_repeatlclick, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wait.Add(self.cb_autoenter_on_sprite, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wait.Add(self.cb_can_clicksidesofcardcontrol, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wait.Add(self.cb_wheel_movefocus, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wait.Add(self.cb_showlogwithwheelup, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wheeldown = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_wheeldown.Add(self.st_wheel_down, 0, wx.LEFT|wx.RIGHT, cw.ppis(3))
        bsizer_wheeldown.Add(self.cb_can_skipwait_with_wheel, 0, wx.LEFT|wx.RIGHT, cw.ppis(3))
        bsizer_wheeldown.Add(self.cb_can_forwardmessage_with_wheel, 0, wx.LEFT|wx.RIGHT, cw.ppis(3))

        bsizer_wait.Add(bsizer_wheeldown, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_wait.SetMinSize((_settings_width(), -1))

        bsizer_quickdeal = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_quickdeal.Add(self.st_quickdeal, 0, wx.ALIGN_CENTER|wx.RIGHT, cw.ppis(3))
        bsizer_quickdeal.Add(self.ch_quickdeal, 0, wx.ALIGN_CENTER, cw.ppis(3))

        bsizer_draw.Add(bsizer_quickdeal, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_draw.Add(self.cb_show_premiumicon, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_draw.Add(self.cb_show_cardkind, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        #bsizer_draw.Add(self.cb_protect_staredcard, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_draw.Add(self.cb_protect_premiercard, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_draw.SetMinSize((_settings_width(), -1))

        bsizer_showbackpackcard = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_showbackpackcard.Add(self.st_showbackpackcard, 0, wx.ALIGN_CENTER|wx.RIGHT, cw.ppis(3))
        bsizer_showbackpackcard.Add(self.ch_showbackpackcard, 0, wx.ALIGN_CENTER, cw.ppis(3))
        
        bsizer_gene.Add(bsizer_showbackpackcard, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(1))
        bsizer_gene.Add(self.cb_revertcardpocket, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.Add(self.cb_show_addctrlbtn, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.Add(self.cb_showautobuttoninentrydialog, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.SetMinSize((_settings_width(), -1))

        
        bsizer_battle.Add(self.cb_showroundautostartbutton, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_battle.Add(self.cb_showallselectedcards, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_battle.Add(self.cb_showstatustime, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))

        bsizer_notice.Add(self.cb_show_experiencebar, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_notice.Add(self.cb_show_btndesc, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_notice.Add(self.cb_statusbarmask, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_notice.Add(self.cb_blink_statusbutton, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_notice.Add(self.cb_blink_partymoney, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))

        bsizer_confirm_beforesaving = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_confirm_beforesaving.Add(self.st_confirm_beforesaving, 0, wx.ALIGN_CENTER|wx.RIGHT, cw.ppis(3))
        bsizer_confirm_beforesaving.Add(self.ch_confirm_beforesaving, 0, wx.ALIGN_CENTER, cw.ppis(3))

        bsizer_confirm_card = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_confirm_card.Add(self.st_confirm_card, 0, wx.RIGHT, cw.ppis(3))
        bsizer_confirm_card.Add(self.cb_confirmbeforeusingcard, 0, wx.LEFT|wx.RIGHT, cw.ppis(3))
        bsizer_confirm_card.Add(self.cb_confirm_dumpcard, 0, wx.LEFT|wx.RIGHT, cw.ppis(3))

        bsizer_dlg.Add(bsizer_confirm_beforesaving, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_dlg.Add(self.cb_showsavedmessage, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_dlg.Add(self.cb_cautionbeforesaving, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_dlg.Add(self.cb_noticeimpossibleaction, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_dlg.Add(bsizer_confirm_card, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_dlg.SetMinSize((_settings_width(), -1))

        sizer_v1.Add(bsizer_wait, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v2.Add(bsizer_draw, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v1.Add(bsizer_gene, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v2.Add(bsizer_notice, 0, wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v1.Add(bsizer_battle, 0, wx.BOTTOM|wx.EXPAND, 5)
        sizer_v2.Add(bsizer_dlg, 0, wx.EXPAND, cw.ppis(3))
        
        sizer_v3.Add(sizer_v1, 1, wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))
        sizer_v3.Add(sizer_v2, 1, wx.LEFT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))

        sizer.Add(sizer_v3, 1, wx.ALL|wx.EXPAND, cw.ppis(10))

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

class FontSettingPanel(wx.Panel):
    def __init__(self, parent, for_local, get_localsettings, use_copybase):
        wx.Panel.__init__(self, parent)
        self.SetDoubleBuffered(True)
        self._for_local = for_local
        self._get_localsettings = get_localsettings
        self.typenames = {"gothic"       : u"等幅ゴシック",
                          "uigothic"     : u"UI用",
                          "mincho"       : u"等幅明朝",
                          "pmincho"      : u"可変幅明朝",
                          "pgothic"      : u"可変幅ゴシック",
                          "button"       : u"ボタン",
                          "combo"        : u"コンボボックス",
                          "tree"         : u"ツリー・リスト",
                          "tab"          : u"タブ",
                          "menu"         : u"メニュー",
                          "scenario"     : u"貼り紙のタイトル",
                          "targetlevel"  : u"貼り紙の対象レベル",
                          "paneltitle"   : u"パネルタイトル1",
                          "paneltitle2"  : u"パネルタイトル2",
                          "dlgmsg"       : u"ダイアログテキスト1",
                          "dlgmsg2"      : u"ダイアログテキスト2",
                          "dlgtitle"     : u"英文タイトル1",
                          "dlgtitle2"    : u"英文タイトル2",
                          "createtitle"  : u"登録タイトル",
                          "inputname"    : u"名前入力欄",
                          "datadesc"     : u"データ解説文",
                          "charaparam"   : u"キャラクター情報1",
                          "charaparam2"  : u"キャラクター情報2",
                          "charadesc"    : u"キャラクター解説文",
                          "characre"     : u"キャラクター登録",
                          "dlglist"      : u"ダイアログリスト",
                          "uselimit"     : u"カード残り回数",
                          "cardname"     : u"カード名",
                          "ccardname"    : u"キャストカード名",
                          "level"        : u"キャストレベル",
                          "numcards"     : u"所持カード枚数",
                          "message"      : u"メッセージ",
                          "selectionbar" : u"選択肢",
                          "logpage"      : u"メッセージログ頁",
                          "sbarpanel"    : u"ステータスパネル",
                          "sbarprogress" : u"進行状況・音量バー",
                          "sbarbtn"      : u"ステータスボタン",
                          "sbardesctitle": u"ボタン解説の表題",
                          "sbardesc"     : u"ボタン解説",
                          "statusnum"    : u"状態値",
                          "screenshot"   : u"撮影情報",
                          }

        self.bases = ("gothic", "pgothic", "mincho", "pmincho", "uigothic")
        self.types = ("message", "selectionbar", "cardname", "ccardname", "level",
                      "logpage", "uselimit", "numcards", "statusnum",
                      "sbarpanel", "sbarprogress", "sbarbtn", "sbardesctitle", "sbardesc", "screenshot",
                      "scenario", "targetlevel", "paneltitle", "paneltitle2", "dlgmsg", "dlgmsg2", "dlgtitle", "dlgtitle2",
                      "createtitle", "dlglist", "inputname", "datadesc", "charadesc", "charaparam", "charaparam2",  "characre", 
                      "button", "combo", "tree", "tab", "menu")

        # フォント配列のロード
        facenames = list(wx.FontEnumerator().GetFacenames())
        cw.util.sort_by_attr(facenames)
        self.str_default = u"[付属フォント]" # デフォルトフォント名
        self._fontface_array = [self.str_default]
        self._types = []
        for base in self.bases:
            self._types.append(u"[%s]" % (self.typenames[base]))
        for name in facenames:
            if not name.startswith(u"@"):
                self._fontface_array.append(name)
                self._types.append(name)

        if self._for_local:
            self.cb_important = wx.CheckBox(self, -1, u"このスキンのフォント設定を基本設定よりも優先して使用する")
        else:
            self.cb_important = None

        # フォント表示サンプル
        self.box_example = wx.StaticBox(self, -1, u"表示例")
        self.st_example = wx.StaticText(self, -1, size=cw.ppis((100, 32)), style=wx.ALIGN_CENTER)
        self.st_example.SetDoubleBuffered(True)

        # 描画オプション
        self.box_gene = wx.StaticBox(self, -1, u"文字の補正")
        self.cb_bordering_cardname = wx.CheckBox(self, -1, u"カード名やタイトルを縁取りする")
        self.cb_decorationfont = wx.CheckBox(self, -1, u"メッセージで装飾フォントを使用する")
        self.cb_fontsmoothingmessage = wx.CheckBox(self, -1, u"メッセージの文字を滑らかにする")
        self.cb_fontsmoothingcardname = wx.CheckBox(self, -1, u"カード名の文字を滑らかにする")
        self.cb_fontsmoothingstatusbar = wx.CheckBox(self, -1, u"ステータスバーの文字を滑らかにする")

        def create_grid(grid, seq, faces, cols, rowlblsize):
            grid.CreateGrid(len(seq), cols)
            grid.DisableDragRowSize()
            #grid.SetLabelBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_3DLIGHT ) )
            #grid.SetLabelTextColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_CAPTIONTEXT ) )
            grid.SetSelectionMode(wx.grid.Grid.SelectRows)
            grid.SetRowLabelAlignment(wx.LEFT, wx.CENTER)
            grid.SetRowLabelSize(rowlblsize)
            grid.SetColLabelSize( cw.ppis(20) )
            grid.SetColLabelValue(0, u"フォント名")
            grid.SetColSize(0, cw.ppis(150))
            editors = []
            for i, name in enumerate(seq):
                editor = wx.grid.GridCellChoiceEditor(faces)
                grid.SetCellEditor(i, 0, editor)
                editors.append(editor)
            return editors

        # 基本フォント
        self.box_base = wx.StaticBox(self, -1, u"基本フォント(役割別の[同名]に反映)")
        self.base = wx.grid.Grid(self, -1, size=(-1, -1), style=wx.BORDER)
        self.base.SetLabelTextColour(wx.Colour(30, 55, 240))
        #self.base.SetLabelBackgroundColour(wx.Colour(230, 235, 240))
        self.base.SetColLabelSize(cw.ppis(16))
        self.base.SetDefaultCellFont(wx.Font(cw.ppis(8), 71, wx.NORMAL, wx.NORMAL))
        #self.base.SetDefaultRowSize(cw.ppis(23))
        self.base.SetDoubleBuffered(True)
        self.choicebases = create_grid(self.base, self.bases, self._fontface_array, 1, cw.ppis(100))
        self.base.SetMinSize(self.base.GetBestSize())# (cw.ppis( (0, 4))))#余白を作らないとスクロールバーが出てしまう

        # 役割別フォント
        self.box_type = wx.StaticBox(self, -1, u"役割別フォント")
        self.type = wx.grid.Grid(self, -1, size=(1, 0), style=wx.BORDER)
        #self.type.SetColLabelSize(cw.ppis(20))
        self.type.SetDoubleBuffered(True)
        self.choicetypes = create_grid(self.type, self.types, self._types, 5, cw.ppis(120))
        self.type.SetColLabelValue(1, u"サイズ")
        self.type.SetColSize(1, cw.ppis(80))
        self.type.SetColLabelValue(2, u"太字")
        self.type.SetColSize(2, cw.ppis(70))
        self.type.SetColLabelValue(3, u"太字(拡大)")
        self.type.SetColSize(3, cw.ppis(70))
        self.type.SetColLabelValue(4, u"斜体")
        self.type.SetColSize(4, cw.ppis(70))
        local = cw.setting.LocalSetting()
        for i, name in enumerate(self.types):
            _deffonttype, _defface, defpixels, defbold, defbold_upscr, defitalic = local.fonttypes_init[name]
            if 0 < defpixels:
                self.type.SetCellEditor(i, 1, wx.grid.GridCellNumberEditor(1, 99))
                self.type.SetCellRenderer(i, 1, wx.grid.GridCellNumberRenderer())
            else:
                self.type.GetOrCreateCellAttr(i, 1).SetReadOnly(True)
            self.type.SetCellAlignment(i, 1, wx.ALIGN_CENTER, 0)
            if not defbold is None:
                self.type.SetCellEditor(i, 2, wx.grid.GridCellBoolEditor())
                self.type.SetCellRenderer(i, 2, wx.grid.GridCellBoolRenderer())
            else:
                self.type.GetOrCreateCellAttr(i, 2).SetReadOnly(True)
            self.type.SetCellAlignment(i, 2, wx.ALIGN_CENTER, 0)
            if not defbold_upscr is None:
                self.type.SetCellEditor(i, 3, wx.grid.GridCellBoolEditor())
                self.type.SetCellRenderer(i, 3, wx.grid.GridCellBoolRenderer())
            else:
                self.type.GetOrCreateCellAttr(i, 3).SetReadOnly(True)
            self.type.SetCellAlignment(i, 3, wx.ALIGN_CENTER, 0)
            if not defitalic is None:
                self.type.SetCellEditor(i, 4, wx.grid.GridCellBoolEditor())
                self.type.SetCellRenderer(i, 4, wx.grid.GridCellBoolRenderer())
            else:
                self.type.GetOrCreateCellAttr(i, 4).SetReadOnly(True)
            self.type.SetCellAlignment(i, 4, wx.ALIGN_CENTER, 0)

        if self._for_local:
            if use_copybase:
                self.copybtn = wx.Button(self, -1, u"基本設定をコピー")
            else:
                self.copybtn = None
            self.initbtn = wx.Button(self, -1, u"デフォルト")

        self._do_layout()
        self._bind()

    def load(self, setting, local):
        if self._for_local:
            self.cb_important.SetValue(local.important_font)
        self.cb_bordering_cardname.SetValue(local.bordering_cardname)
        self.cb_decorationfont.SetValue(local.decorationfont)
        self.cb_fontsmoothingmessage.SetValue(local.fontsmoothing_message)
        self.cb_fontsmoothingcardname.SetValue(local.fontsmoothing_cardname)
        self.cb_fontsmoothingstatusbar.SetValue(local.fontsmoothing_statusbar)

        def create_grid(grid, seq):
            for i, name in enumerate(seq):
                grid.SetRowLabelValue(i, self.typenames[name])

        create_grid(self.base, self.bases)
        for i, name, in enumerate(self.bases):
            str_font = local.basefont[name]
            if not str_font:
                str_font = self.str_default#付属フォント
            self.base.SetCellValue(i, 0, str_font)

        create_grid(self.type, self.types)
        self.type.SetColLabelSize( cw.ppis(20) )
        self.type.SetColLabelValue(1, u"サイズ")
        self.type.SetColSize(1, cw.ppis(80))
        self.type.SetColLabelValue(2, u"太字")
        self.type.SetColSize(2, cw.ppis(70))
        self.type.SetColLabelValue(3, u"太字(拡大)")
        self.type.SetColSize(3, cw.ppis(70))
        self.type.SetColLabelValue(4, u"斜体")
        self.type.SetColSize(4, cw.ppis(70))

        for i, name, in enumerate(self.bases):
            str_font = local.basefont[name]
            if not str_font:
                str_font = self.str_default
            self.base.SetCellValue(i, 0, str_font)

        for i, name in enumerate(self.types):
            _deffonttype, _defface, defpixels, defbold, defbold_upscr, defitalic = local.fonttypes_init[name]
            fonttype, face, pixels, bold, bold_upscr, italic = local.fonttypes[name]
            if fonttype:
                self.type.SetCellValue(i, 0, u"[%s]" % (self.typenames[fonttype]))
            else:
                self.type.SetCellValue(i, 0, face)

            if 0 < defpixels:
                self.type.SetCellValue(i, 1, str(pixels))
            else:
                self.type.SetCellValue(i, 1, u"-")
            if not defbold is None:
                self.type.SetCellValue(i, 2, u"1" if bold else u"")
            else:
                self.type.SetCellValue(i, 2, u"-")

            if not defbold_upscr is None:
                self.type.SetCellValue(i, 3, u"1" if bold_upscr else u"")
            else:
                self.type.SetCellValue(i, 3, u"-")
            if not defitalic is None:
                self.type.SetCellValue(i, 4, u"1" if italic else u"")
            else:
                self.type.SetCellValue(i, 4, u"-")

        self._select_base(self.base.GetGridCursorRow())

        font = wx.Font(17, wx.DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
                       face=self.st_example.GetLabel())
        self.st_example.SetFont(font)
        self.st_example.SetLabel(self.get_basefontface(self.bases[0]))

        self._update_enabled()
        self.Layout()

    def init_values(self, setting, local):
        for i, basename in enumerate(self.bases):
            name = local.basefont_init[basename]
            if not name:
                name = self.str_default
            self.base.SetCellValue(i, 0, name)
        for i, typename in enumerate(self.types):
            fonttype, name, pixels, bold, bold_upscr, italic = local.fonttypes_init[typename]
            if fonttype:
                name = u"[%s]" % (self.typenames[fonttype])
            self.type.SetCellValue(i, 0, name)
            self.type.SetCellValue(i, 1, str(pixels) if 0 < pixels else u"-")
            self.type.SetCellValue(i, 2, (u"1" if bold else u"") if not bold is None else u"-")
            self.type.SetCellValue(i, 3, (u"1" if bold_upscr else u"") if not bold_upscr is None else u"-")
            self.type.SetCellValue(i, 4, (u"1" if italic else u"") if not italic is None else u"-")

        self.cb_bordering_cardname.SetValue(local.bordering_cardname_init)
        self.cb_decorationfont.SetValue(local.decorationfont_init)
        self.cb_fontsmoothingmessage.SetValue(local.fontsmoothing_message_init)
        self.cb_fontsmoothingcardname.SetValue(local.fontsmoothing_cardname_init)
        self.cb_fontsmoothingstatusbar.SetValue(local.fontsmoothing_statusbar_init)

    def apply_localsettings(self, local):
        updatecardimg = False  # キャラクターカードイメージの更新が必要か
        updatemcardimg = False  # メニューカードイメージの更新が必要か
        updatemessage = False  # メッセージの更新が必要か
        flag_fontupdate = False  # フォントの変更があるか

        value = self.cb_bordering_cardname.GetValue()
        if local.bordering_cardname <> value:
            local.bordering_cardname = value
            updatecardimg = True
            updatemcardimg = True
        value = self.cb_decorationfont.GetValue()
        if value <> local.decorationfont:
            local.decorationfont = value
            updatemessage = True
        value = self.cb_fontsmoothingmessage.GetValue()
        if value <> local.fontsmoothing_message:
            local.fontsmoothing_message = value
            updatemessage = True
        value = self.cb_fontsmoothingcardname.GetValue()
        if value <> local.fontsmoothing_cardname:
            local.fontsmoothing_cardname = value
            flag_fontupdate = True
        value = self.cb_fontsmoothingstatusbar.GetValue()
        if value <> local.fontsmoothing_statusbar:
            local.fontsmoothing_statusbar = value
            flag_fontupdate = True

        basetable = {}
        basefont = {}
        for i, basename in enumerate(self.bases):
            value = self.base.GetCellValue(i, 0)
            if value == self.str_default:
                value = u""
            basefont[basename] = value
            basetable[u"[%s]" % (self.typenames[basename])] = basename
        fonttypes = {}
        for i, typename in enumerate(self.types):
            value = self.type.GetCellValue(i, 0)
            pixels = self.type.GetCellValue(i, 1)
            try:
                if pixels <> u"-":
                    pixels = int(pixels)
                else:
                    pixels = -1
            except:
                pixels = -1
            bold = self.type.GetCellValue(i, 2)
            if bold in (u"1", u""):
                bold = bold == u"1"
            else:
                bold = None
            bold_upscr = self.type.GetCellValue(i, 3)
            if bold_upscr in (u"1", u""):
                bold_upscr = bold_upscr == u"1"
            else:
                bold_upscr = None
            italic = self.type.GetCellValue(i, 4)
            if italic in (u"1", u""):
                italic = italic == u"1"
            else:
                italic = None
            fonttype = basetable.get(value, "")
            if fonttype:
                fonttypes[typename] = (fonttype, u"", pixels, bold, bold_upscr, italic)
            else:
                fonttypes[typename] = (u"", value, pixels, bold, bold_upscr, italic)

        # フォント変更チェック
        if basefont <> local.basefont:
            local.basefont = basefont
            flag_fontupdate = True
        if fonttypes <> local.fonttypes:
            local.fonttypes = fonttypes
            flag_fontupdate = True

        if self.cb_important and self.cb_important.GetValue() <> local.important_font:
            local.important_font = self.cb_important.GetValue()
            flag_fontupdate = True

        return flag_fontupdate, updatecardimg, updatemcardimg, updatemessage

    def _bind(self):
        self.base.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.OnSelectFontBase)
        self.base.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.OnCellChangeBase)
        self.base.Bind(wx.grid.EVT_GRID_EDITOR_CREATED, self.OnEditorCreatedBase)
        self.type.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.OnSelectFontType)
        self.type.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.OnCellChangeType)
        self.type.Bind(wx.grid.EVT_GRID_EDITOR_CREATED, self.OnEditorCreatedType)
        if self._for_local:
            self.cb_important.Bind(wx.EVT_CHECKBOX, self.OnImportant)
            if self.copybtn:
                self.copybtn.Bind(wx.EVT_BUTTON, self.OnCopyBase)
            self.initbtn.Bind(wx.EVT_BUTTON, self.OnInitValue)

    def _select_base(self, i):
        if 0 <= i:
            self.Freeze()
            self.st_example.SetLabel(self.get_basefontface(self.bases[i]))
            font = wx.Font(17, wx.DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
                           face=self.st_example.GetLabel())
            self.st_example.SetFont(font)
            self.Layout()
            self.Thaw()

    def OnCellChangeBase(self, event):
        self._select_base(self.base.GetGridCursorRow())

    def OnSelectFontBase(self, event):
        def func(self):
            if self:
                self._select_base(self.base.GetGridCursorRow())
        cw.cwpy.frame.exec_func(func, self)
        event.Skip()

    def OnEditorCreatedBase(self, event):
        for editor in self.choicebases:
            if editor.GetControl():
                editor.GetControl().Bind(wx.EVT_COMBOBOX, self.OnCellChangeBase)

    def get_basefontface(self, fonttype):
        editors = filter(lambda choice: choice.GetControl() and choice.GetControl().IsShown(),
                         self.choicebases)
        if editors:
            face = editors[0].GetControl().GetValue()
        else:
            face = self.base.GetCellValue(self.bases.index(fonttype), 0)
        if face == self.str_default:#付属フォント
            if cw.cwpy:
                d = cw.cwpy.rsrc.fontnames_init
            else:
                d = {}
                d["gothic"],d["uigothic"],d["mincho"],d["pmincho"],d["pgothic"] = ((u"梅Hyゴシック",)*5)
            face = d[fonttype]
        return face

    def _select_type(self, i):
        if 0 <= i:
            self.Freeze()
            self.st_example.SetLabel(self.get_typefontface(self.types[i]))
            font = wx.Font(17, wx.DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
                           face=self.st_example.GetLabel())
            self.st_example.SetFont(font)
            self.Layout()
            self.Thaw()

    def OnCellChangeType(self, event):
        self._select_type(self.type.GetGridCursorRow())

    def OnSelectFontType(self, event):
        def func(self):
            if self:
                self._select_type(self.type.GetGridCursorRow())
        cw.cwpy.frame.exec_func(func, self)
        event.Skip()

    def OnEditorCreatedType(self, event):
        for editor in self.choicetypes:
            ctrl = editor.GetControl()
            if ctrl:
               ctrl.Bind(wx.EVT_COMBOBOX, self.OnCellChangeType)

    def get_typefontface(self, fonttype):
        editors = filter(lambda choice: choice.GetControl() and choice.GetControl().IsShown(),
                         self.choicetypes)
        if editors:
            face = editors[0].GetControl().GetValue()
        else:
            face = self.type.GetCellValue(self.types.index(fonttype), 0)
        for basename in self.bases:
            if u"[%s]" % self.typenames[basename] == face:
                face = self.get_basefontface(basename)
                break
        return face

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_v1 = wx.BoxSizer(wx.VERTICAL)

        bsizer_top = wx.BoxSizer(wx.HORIZONTAL)

        bsizer_left = wx.BoxSizer(wx.VERTICAL)

        bsizer_example2 = wx.BoxSizer(wx.HORIZONTAL)
        bsizer_example2.Add(self.st_example, 1, wx.ALIGN_CENTER, cw.ppis(0))

        bsizer_example = wx.StaticBoxSizer(self.box_example, wx.VERTICAL)
        bsizer_example.Add(bsizer_example2, 1, wx.LEFT|wx.RIGHT|wx.EXPAND|wx.ALIGN_CENTER, cw.ppis(3))

        bsizer_gene = wx.StaticBoxSizer(self.box_gene, wx.VERTICAL)
        bsizer_gene.Add(self.cb_bordering_cardname, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))
        bsizer_gene.Add(self.cb_fontsmoothingmessage, 0, wx.LEFT|wx.BOTTOM|wx.RIGHT, cw.ppis(3))
        bsizer_gene.Add(self.cb_fontsmoothingcardname, 0, wx.LEFT|wx.BOTTOM|wx.RIGHT, cw.ppis(3))
        bsizer_gene.Add(self.cb_fontsmoothingstatusbar, 0, wx.LEFT|wx.BOTTOM|wx.RIGHT, cw.ppis(3))

        bsizer_left.Add(bsizer_example, 1, wx.EXPAND | wx.BOTTOM, cw.ppis(3))
        bsizer_left.Add(bsizer_gene, 0, wx.EXPAND, cw.ppis(3))

        bsizer_base = wx.StaticBoxSizer(self.box_base, wx.VERTICAL)
        bsizer_base.Add(self.base, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM, cw.ppis(3))#|wx.EXPAND
        bsizer_base.Add(self.cb_decorationfont, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, cw.ppis(3))

        bsizer_top.Add(bsizer_left, 1, wx.EXPAND|wx.RIGHT, cw.ppis(5))
        bsizer_top.Add(bsizer_base, 1, wx.EXPAND, cw.ppis(3))

        bsizer_type = wx.StaticBoxSizer(self.box_type, wx.VERTICAL)
        bsizer_type.Add(self.type, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, cw.ppis(3))

        if self.cb_important:
            sizer_v1.Add(self.cb_important, 0, wx.BOTTOM, cw.ppis(5))
        sizer_v1.Add(bsizer_top, 0, wx.EXPAND|wx.BOTTOM, cw.ppis(3))
        sizer_v1.Add(bsizer_type, 1, wx.EXPAND, cw.ppis(0))

        if self._for_local:
            sizer_v1.AddStretchSpacer(0)
            bsizer_btn = wx.BoxSizer(wx.HORIZONTAL)
            if self.copybtn:
                bsizer_btn.Add(self.copybtn, 0, wx.RIGHT, cw.ppis(3))
            bsizer_btn.Add(self.initbtn, 0, 0, cw.ppis(0))
            sizer_v1.Add(bsizer_btn, 0, wx.ALIGN_RIGHT|wx.TOP, cw.ppis(5))

        sizer.Add(sizer_v1, 1, wx.ALL|wx.EXPAND, cw.ppis(10))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnImportant(self, event):
        self._update_enabled()

    def _update_enabled(self):
        enbl = self.cb_important.GetValue() if self.cb_important else True
        self.base.Enable(enbl)
        self.type.Enable(enbl)
        self.cb_bordering_cardname.Enable(enbl)
        self.cb_decorationfont.Enable(enbl)
        self.cb_fontsmoothingmessage.Enable(enbl)
        self.cb_fontsmoothingcardname.Enable(enbl)
        self.cb_fontsmoothingstatusbar.Enable(enbl)
        if self._for_local:
            if self.copybtn:
                self.copybtn.Enable(enbl)
            self.initbtn.Enable(enbl)

    def OnInitValue(self, event):
        local = cw.setting.LocalSetting()
        self.init_values(None, local)

    def OnCopyBase(self, event):
        local = self._get_localsettings()
        local.important_font = True
        self.load(None, local)

def main():
    pass

if __name__ == "__main__":
    main()
