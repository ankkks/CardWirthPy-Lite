#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import io
import sys
import time
import datetime
import threading
import shutil
import subprocess
import wx

import cw
import message
import charainfo
import text
import select

from cw.util import synclock

_lockupdatescenario = threading.Lock()

#-------------------------------------------------------------------------------
#　貼り紙選択ダイアログ
#-------------------------------------------------------------------------------

class ScenarioSelect(select.Select):
    """
    貼り紙選択ダイアログ。
    """
    def __init__(self, parent, db, lastscenario, lastscenariopath):
        # ダイアログボックス作成
        select.Select.__init__(self, parent, cw.cwpy.msgs["select_scenario_title"])
        self.SetDoubleBuffered(True)
        self._bg = None
        self._quit = False

        self._last_narrowparams = None

        # ディレクトリとシナリオリストの対応
        self.scetable = {}
        # シナリオディレクトリ
        self.scedir = cw.cwpy.setting.get_scedir()
        # 現在開いているディレクトリ
        self.nowdir = self.scedir
        # 開いたディレクトリの階層
        self.dirstack = []
        # シナリオデータベース
        self.db = db
        # nowdirにあるScenarioHeaderのリスト
        self.db.update(self.nowdir, skintype=cw.cwpy.setting.skintype)
        headers = self.db.search_dpath(self.nowdir, create=True, skintype=cw.cwpy.setting.skintype)
        # nowdirにあるディレクトリリスト
        dpaths = self.get_dpaths(self.nowdir)
        # nowdirがディレクトリだった場合の内容リスト
        self.names = []
        self.updatenames_thr = None
        # クリアシナリオ名の集合
        self.stamps = cw.cwpy.ydata.get_compstamps()
        # パーティの所持しているクーポンの集合
        self.coupons = cw.cwpy.ydata.party.get_coupontable()
        # 現在進行中のシナリオパスの集合
        self.nowplayingpaths = cw.cwpy.ydata.get_nowplayingpaths()
        # 貼り紙バグの再現
        self._paperslide = False

        # 検索結果
        self.find_result = None

        # 表示設定
        def create_btn(msg, bmp, value):
            btn = wx.lib.buttons.ThemedGenBitmapToggleButton(self, -1, None, size=cw.wins((32, 24)))
            dbmp = cw.imageretouch.to_disabledimage(bmp)
            btn.SetToggle(value)
            if value:
                bmp2 = bmp
            else:
                bmp2 = dbmp
            btn.SetBitmapFocus(bmp2)
            btn.SetBitmapLabel(bmp2, False)
            btn.SetBitmapSelected(bmp2)
            btn.SetToolTipString(msg)
            return btn, bmp, dbmp
        self.unfitness, self.bmp_unfitness, self.dbmp_unfitness = create_btn(cw.cwpy.msgs["show_unfitness_scenario"],
                                                                             cw.cwpy.rsrc.dialogs["SUMMARY_UNFITNESS"],
                                                                             cw.cwpy.setting.show_unfitnessscenario)
        self.completed, self.bmp_completed, self.dbmp_completed = create_btn(cw.cwpy.msgs["show_completed_scenario"],
                                                                             cw.cwpy.rsrc.dialogs["SUMMARY_COMPLETE"],
                                                                             cw.cwpy.setting.show_completedscenario)
        self.invisible, self.bmp_invisible, self.dbmp_invisible = create_btn(cw.cwpy.msgs["show_invisible_scenario"],
                                                                             cw.cwpy.rsrc.dialogs["SUMMARY_INVISIBLE"],
                                                                             cw.cwpy.setting.show_invisiblescenario)

        # エクスプローラーで開く
        bmp = cw.cwpy.rsrc.dialogs["DIRECTORY"]
        self.opendirbtn = cw.cwpy.rsrc.create_wxbutton(self, -1, (cw.wins(32), cw.wins(24)), bmp=bmp)
        self.opendirbtn.SetToolTip(wx.ToolTip(cw.cwpy.msgs["open_directory"]))

        # エディタで開く
        if cw.cwpy.is_debugmode():
            bmp = cw.cwpy.rsrc.dialogs["EDITOR"]
            self.editorbtn = cw.cwpy.rsrc.create_wxbutton(self, -1, (cw.wins(32), cw.wins(24)), bmp=bmp)
            self.editorbtn.SetToolTip(wx.ToolTip(cw.cwpy.msgs["open_with_editor"]))
        else:
            self.editorbtn = None

        # 絞り込み欄等の表示設定
        if not cw.cwpy.setting.show_paperandtree:
            self.create_addctrlbtn(self, self._get_bg(), cw.cwpy.setting.show_additional_scenario)
            self._addctrlbg = self.addctrlbtn.GetBackgroundColour()

        # toppanelとツリー表示用のビュー
        if cw.cwpy.setting.show_paperandtree:
            self.toppanel = wx.Panel(self, -1, size=(cw.wins(400)+1, cw.wins(370)))
            size = (cw.wins(230), 0)
        else:
            self.toppanel = wx.Panel(self, -1, size=(cw.wins(400), cw.wins(370)+2))
            size = (cw.wins(400), cw.wins(370)+2)
            self.toppanel.SetDoubleBuffered(True)
        self.tree = wx.TreeCtrl(self, -1, size=size,
            style=wx.BORDER|wx.TR_SINGLE|wx.TR_HIDE_ROOT|wx.TR_DEFAULT_STYLE)
        self.tree.SetDoubleBuffered(True)
        self.tree.SetFont(cw.cwpy.rsrc.get_wxfont("tree", pixelsize=cw.wins(15)-1))
        self.tree.imglist = wx.ImageList(cw.wins(16), cw.wins(16))
        self.tree.imgidx_summary = self.tree.imglist.Add(cw.cwpy.rsrc.dialogs["SUMMARY"])
        self.tree.imgidx_complete = self.tree.imglist.Add(cw.cwpy.rsrc.dialogs["SUMMARY_COMPLETE"])
        self.tree.imgidx_playing = self.tree.imglist.Add(cw.cwpy.rsrc.dialogs["SUMMARY_PLAYING"])
        self.tree.imgidx_invisible = self.tree.imglist.Add(cw.cwpy.rsrc.dialogs["SUMMARY_INVISIBLE"])
        self.tree.imgidx_dir = self.tree.imglist.Add(cw.cwpy.rsrc.dialogs["DIRECTORY"])
        self.tree.imgidx_findresult = self.tree.imglist.Add(cw.cwpy.rsrc.dialogs["FIND_SCENARIO"])
        self.tree.root = self.tree.AddRoot(self.scedir)
        self.tree.SetItemPyData(self.tree.root, (0, self.scedir))
        self.tree.SetImageList(self.tree.imglist)
        self.tree.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        self._no_treechangedsound = False

        # 絞込条件
        choices = (cw.cwpy.msgs["title"],
                   cw.cwpy.msgs["description"],
                   cw.cwpy.msgs["author"],
                   cw.cwpy.msgs["target_level"],
                   cw.cwpy.msgs["file_name"])
        self._init_narrowpanel(choices, cw.cwpy.setting.scenario_narrow,
                               cw.cwpy.setting.scenario_narrowtype, tworows=True)

        # 整列条件
        font = cw.cwpy.rsrc.get_wxfont("paneltitle2", pixelsize=cw.wins(13))
        self.sort_label = wx.StaticText(self, -1, label=cw.cwpy.msgs["sort_title"])
        self.sort_label.SetFont(font)
        font = cw.cwpy.rsrc.get_wxfont("combo", pixelsize=cw.wins(13))
        choices = (cw.cwpy.msgs["target_level"],
                   cw.cwpy.msgs["title"],
                   cw.cwpy.msgs["author"],
                   cw.cwpy.msgs["file_name"],
                   cw.cwpy.msgs["modified_date"])
        self.sort = wx.Choice(self, -1, size=(-1, -1), choices=choices)
        self.sort.SetFont(font)
        self.sort.SetSelection(cw.cwpy.setting.scenario_sorttype)

        # 選択リスト
        self.list = dpaths + headers
        self.scetable[self._get_linktarget(self.nowdir)] = self.list
        self.list = self._narrow_scenario(self.list)
        self.index = 0

        # 検索
        bmp = cw.cwpy.rsrc.dialogs["FIND_SCENARIO"]
        self.find = cw.cwpy.rsrc.create_wxbutton(self, -1, (-1, cw.wins(23)), bmp=bmp)
        self.find.SetToolTip(wx.ToolTip(cw.cwpy.msgs["find_scenario"]))

        # ブックマーク
        bmp = cw.cwpy.rsrc.dialogs["BOOKMARK2"]
        self.bookmark = cw.cwpy.rsrc.create_wxbutton(self, -1, (-1, cw.wins(30)), bmp=bmp)
        self.bookmark.SetToolTip(wx.ToolTip(cw.cwpy.msgs["bookmark"]))

        if cw.cwpy.setting.show_paperandtree:
            buttonwidth = cw.wins(90)
        else:
            buttonwidth = cw.wins(55)

        # 絞り込み欄等の更新
        if not cw.cwpy.setting.show_paperandtree:
            self.additionals.append((self.unfitness, lambda: cw.cwpy.setting.show_scenariotree))
            self.additionals.append((self.completed, lambda: cw.cwpy.setting.show_scenariotree))
            self.additionals.append((self.invisible, lambda: cw.cwpy.setting.show_scenariotree))
            self.additionals.append((self.opendirbtn, lambda: cw.cwpy.setting.show_scenariotree))
            if self.editorbtn:
                self.additionals.append((self.editorbtn, lambda: cw.cwpy.setting.show_scenariotree))

            self.additionals.append(self.narrow)
            self.additionals.append(self.narrow_label)
            self.additionals.append(self.narrow_type)
            self.additionals.append(self.sort_label)
            self.additionals.append(self.sort)
            self.additionals.append(self.find)
            self.additionals.append(self.bookmark)
            self.update_additionals()

        # ok
        self.yesbtn = cw.cwpy.rsrc.create_wxbutton(self.panel, wx.ID_YES, (buttonwidth, cw.wins(23)), cw.cwpy.msgs["decide"])
        self.buttonlist.append(self.yesbtn)
        # info
        self.infobtn = cw.cwpy.rsrc.create_wxbutton(self.panel, -1, (buttonwidth, cw.wins(23)), cw.cwpy.msgs["description"])
        self.buttonlist.append(self.infobtn)
        if not cw.cwpy.setting.show_paperandtree:
            # view
            self.viewbtn = cw.cwpy.rsrc.create_wxbutton(self.panel, -1, (buttonwidth, cw.wins(23)), cw.cwpy.msgs["scenario_tree"])
            self.buttonlist.append(self.viewbtn)
        else:
            self.viewbtn = None
        # close
        self.nobtn = cw.cwpy.rsrc.create_wxbutton(self.panel, wx.ID_NO, (buttonwidth, cw.wins(23)), cw.cwpy.msgs["entry_cancel"])
        self.buttonlist.append(self.nobtn)
        # ドロップファイル機能ON
        self.DragAcceptFiles(True)

        if cw.cwpy.setting.show_paperandtree:
            self.show_tree()
        else:
            if cw.cwpy.setting.show_scenariotree:
                self.toppanel.Hide()
                self.show_tree()
            else:
                self.tree.Hide()

        if self.tree.IsShown():
            item = self.tree.GetSelection()
            if item and not self.tree.IsVisible(item):
                self.tree.ScrollTo(item)
                self.tree.SetScrollPos(wx.HORIZONTAL, 0)

        # リストが空だったらボタンを無効化
        self.enable_btn()
        # 選択状態を記憶
        self._update_saveddirstack()
        # layout
        self._do_layout()
        # bind
        self._bind()
        self.toppanel.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_DROP_FILES, self.OnDropFiles)
        self.Bind(wx.EVT_BUTTON, self.OnClickYesBtn, self.yesbtn)
        self.Bind(wx.EVT_BUTTON, self.OnClickNoBtn, self.nobtn)
        if self.viewbtn:
            self.Bind(wx.EVT_BUTTON, self.OnClickViewBtn, self.viewbtn)
        self.Bind(wx.EVT_BUTTON, self.OnClickInfoBtn, self.infobtn)
        self.Bind(wx.EVT_BUTTON, self.OnUnfitnessBtn, self.unfitness)
        self.Bind(wx.EVT_BUTTON, self.OnCompletedBtn, self.completed)
        self.Bind(wx.EVT_BUTTON, self.OnInvisibleBtn, self.invisible)
        self.Bind(wx.EVT_BUTTON, lambda event: self.open_directory(), self.opendirbtn)
        if self.editorbtn:
            self.Bind(wx.EVT_BUTTON, lambda event: self.open_with_editor(), self.editorbtn)
        self.tree.Bind(wx.EVT_TREE_ITEM_EXPANDED, self.OnTreeItemExpanded)
        self.tree.Bind(wx.EVT_TREE_ITEM_COLLAPSED, self.OnTreeItemCollapsed)
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelChanged)
        self.tree.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick2)
        self.tree.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        self.sort.Bind(wx.EVT_CHOICE, self.OnNarrowCondition)
        self.find.Bind(wx.EVT_BUTTON, self.OnFind)
        self.bookmark.Bind(wx.EVT_BUTTON, self.OnBookmark)

        self.Bind(wx.EVT_BUTTON, self.OnOk, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnCancel2, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self.OnCancel2)

        if lastscenario or lastscenariopath:
            self.set_selected(lastscenario, lastscenariopath)
        else:
            self.draw(True)

        self.bookmarkmenu = None
        self.directorymenu = None

        seq = self.accels
        upkey = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnUpKeyDown, id=upkey)
        seq.append((wx.ACCEL_CTRL, wx.WXK_UP, upkey))
        downkey = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnDownKeyDown, id=downkey)
        seq.append((wx.ACCEL_CTRL, wx.WXK_DOWN, downkey))

        seq = self.accels
        esckey = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnEscape, id=esckey)
        seq.append((wx.ACCEL_NORMAL, wx.WXK_ESCAPE, esckey))

        bookmarkkey = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnBookmark2, id=bookmarkkey)
        seq.append((wx.ACCEL_CTRL, ord('b'), bookmarkkey))

        copyid = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnCopyDetail, id=copyid)
        seq.append((wx.ACCEL_CTRL, ord('C'), copyid))

        newfolderid = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnCreateDirBtn, id=newfolderid)
        seq.append((wx.ACCEL_CTRL, ord('N'), newfolderid))

        installid = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnInstallBtn, id=installid)
        seq.append((wx.ACCEL_CTRL, ord('I'), installid))

        self.narrowkeydown = []
        self.sortkeydown = []
        for i in xrange(0, 9):
            narrowkeydown = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnNumberKeyDown, id=narrowkeydown)
            seq.append((wx.ACCEL_CTRL, ord('1')+i, narrowkeydown))
            self.narrowkeydown.append(narrowkeydown)
            sortkeydown = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnNumberKeyDown, id=sortkeydown)
            seq.append((wx.ACCEL_ALT, ord('1')+i, sortkeydown))
            self.sortkeydown.append(sortkeydown)
        if self.addctrlbtn:
            self.append_addctrlaccelerator(seq)
        cw.util.set_acceleratortable(self, seq)

    def update_additionals(self):
        self.addctrlbtn.SetDoubleBuffered(False)
        if self.addctrlbtn.GetToggle() or cw.cwpy.setting.show_scenariotree:
            self.addctrlbtn.Reparent(self)
        else:
            self.addctrlbtn.Reparent(self.toppanel)
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.AddStretchSpacer(1)
            sizer.Add(self.addctrlbtn, 0, wx.ALIGN_TOP, 0)
            self.toppanel.SetSizer(sizer)

        cw.cwpy.frame.exec_func(self._do_layout)

        if self.addctrlbtn.GetToggle():
            size = (cw.wins(400), cw.wins(370)+2)
        else:
            size = (cw.wins(400), cw.wins(370))

        if self.addctrlbtn.GetToggle() or cw.cwpy.setting.show_scenariotree:
            self.addctrlbtn.SetBackgroundColour(self.GetBackgroundColour())
        else:
            self.addctrlbtn.SetBackgroundColour(self._addctrlbg)
            self.addctrlbtn.SetDoubleBuffered(True)

        if cw.cwpy.setting.show_scenariotree and not self.addctrlbtn.GetToggle():
            h = size[1]
            h -= max(map(lambda ctrl: ctrl.GetSize()[1] if ctrl else 0,
                         (self.unfitness, self.completed, self.invisible, 
                          self.editorbtn, self.opendirbtn, self.addctrlbtn)))
            treesize = (size[0], h)
        else:
            treesize = size

        self.toppanel.SetSize(size)
        self.toppanel.SetMinSize(size)
        self.tree.SetSize(treesize)
        self.tree.SetMinSize(treesize)

        select.Select.update_additionals(self)
        cw.cwpy.setting.show_additional_scenario = self.addctrlbtn.GetToggle()

    def _get_linktarget(self, path):
        if isinstance(path, FindResult):
            return path
        return cw.util.get_linktarget(path)

    def OnCopyDetail(self, event):
        s = self.get_detailtext()
        if not s:
            return
        cw.cwpy.play_sound("equipment")
        cw.util.to_clipboard(s)

    def OnEscape(self, event):
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

    def OnUnfitnessBtn(self, event):
        cw.cwpy.play_sound("page")
        cw.cwpy.setting.show_unfitnessscenario = self.unfitness.GetToggle()
        if self.unfitness.GetToggle():
            bmp = self.bmp_unfitness
        else:
            bmp = self.dbmp_unfitness
        self.unfitness.SetBitmapFocus(bmp)
        self.unfitness.SetBitmapLabel(bmp, False)
        self.unfitness.SetBitmapSelected(bmp)

        self.update_narrowcondition()

    def OnCompletedBtn(self, event):
        cw.cwpy.play_sound("page")
        cw.cwpy.setting.show_completedscenario = self.completed.GetToggle()
        if self.completed.GetToggle():
            bmp = self.bmp_completed
        else:
            bmp = self.dbmp_completed
        self.completed.SetBitmapFocus(bmp)
        self.completed.SetBitmapLabel(bmp, False)
        self.completed.SetBitmapSelected(bmp)

        self.update_narrowcondition()

    def OnInvisibleBtn(self, event):
        cw.cwpy.play_sound("page")
        cw.cwpy.setting.show_invisiblescenario = self.invisible.GetToggle()
        if self.invisible.GetToggle():
            bmp = self.bmp_invisible
        else:
            bmp = self.dbmp_invisible
        self.invisible.SetBitmapFocus(bmp)
        self.invisible.SetBitmapLabel(bmp, False)
        self.invisible.SetBitmapSelected(bmp)

        self.update_narrowcondition()

    def OnPrevButton(self, event):
        if wx.Window.FindFocus() is self.tree:
            selitem = self.tree.GetSelection()
            if selitem:
                self._collapse_tree(selitem)
                return
        select.Select.OnPrevButton(self, event)

    def OnNextButton(self, event):
        if wx.Window.FindFocus() is self.tree:
            selitem = self.tree.GetSelection()
            if selitem:
                self._expand_tree(selitem)
                return
        select.Select.OnNextButton(self, event)

    def OnMouseWheel(self, event):
        if self._processing:
            return

        if select.change_combo(self.narrow_type, event):
            return
        elif select.change_combo(self.sort, event):
            return
        else:
            select.Select.OnMouseWheel(self, event)

    def OnUpKeyDown(self, event):
        if self.narrow.IsShown():
            self.narrow.SetFocus()

    def OnDownKeyDown(self, event):
        buttonlist = filter(lambda button: button.IsEnabled(), self.buttonlist)
        if buttonlist:
            buttonlist[0].SetFocus()

    def OnNumberKeyDown(self, event):
        """
        数値キー'1'～'9'までの押下を処理する。
        絞込条件の変更またはソート条件の変更を行う。
        """
        if self._processing:
            return
        if not self.narrow.IsShown():
            return

        eid = event.GetId()
        if eid in self.narrowkeydown:
            index = self.narrowkeydown.index(eid)
            if index < self.narrow_type.GetCount():
                self.narrow_type.SetSelection(index)
                self.OnNarrowCondition(event)
        if eid in self.sortkeydown:
            index = self.sortkeydown.index(eid)
            if index < self.sort.GetCount():
                self.sort.SetSelection(index)
                self.OnNarrowCondition(event)

    def _do_layout(self):
        if cw.cwpy.setting.show_paperandtree:
            sizer_1 = wx.BoxSizer(wx.VERTICAL)
            self.set_panelsizer()

            sizer_2 = wx.BoxSizer(wx.HORIZONTAL)

            self.topsizer = wx.BoxSizer(wx.VERTICAL)
            self.topsizer.Add(self._sizer_top(), 0, wx.EXPAND, 0)
            self.topsizer.Add(self.tree, 1, wx.EXPAND, 0)

            sizer_2.Add(self.toppanel, 0, 0, 0)
            sizer_2.Add(self.topsizer, 0, wx.EXPAND, 0)

            sizer_1.Add(sizer_2, 0, wx.EXPAND, 0)
            sizer_1.Add(self._sizer_find(), 0, wx.EXPAND, 0)
            sizer_1.Add(self.panel, 0, wx.EXPAND, 0)

            self.SetSizer(sizer_1)
            sizer_1.Fit(self)
            self.Layout()
        else:
            select.Select._do_layout(self)

    def _add_topsizer(self):
        self.topsizer.Insert(0, self._sizer_top(), 0, wx.EXPAND|wx.TOP|wx.CENTER|wx.ALIGN_RIGHT, 0)
        self.topsizer.Add(self.tree, 1, wx.EXPAND, 0)
        self.topsizer.Add(self._sizer_find(), 0, wx.EXPAND, 0)

    def _sizer_top(self):
        hsizer1 = wx.BoxSizer(wx.HORIZONTAL)
        hsizer1.Add(self.unfitness, 0, 0, 0)
        hsizer1.Add(self.completed, 0, 0, 0)
        hsizer1.Add(self.invisible, 0, 0, 0)
        hsizer1.AddStretchSpacer(1)
        hsizer1.Add(self.opendirbtn, 0, 0, 0)
        if self.editorbtn:
            hsizer1.Add(self.editorbtn, 0, 0, 0)
        if self.addctrlbtn and (self.addctrlbtn.GetToggle() or cw.cwpy.setting.show_scenariotree):
            hsizer1.Add(self.addctrlbtn, 0, 0, 0)
        return hsizer1

    def _sizer_find(self):
        #検索パネル
        nsizer = wx.BoxSizer(wx.HORIZONTAL)

        nsizer.Add(self.narrow_label, 0, wx.LEFT|wx.RIGHT|wx.CENTER, cw.wins(2))
        nsizer.Add(self.find, 0, wx.CENTER|wx.EXPAND, 0)
        nsizer.Add(self.narrow, 1, wx.CENTER, 0)
        nsizer.Add(self.narrow_type, 0, wx.CENTER, cw.wins(1))

        nsizer.Add(self.sort_label, 0, wx.LEFT|wx.RIGHT|wx.CENTER, cw.wins(1))
        #wx.EXPANDだと貼り紙の移動で描画が乱れる
        nsizer.Add(self.sort, 0, wx.CENTER, 0)
        #nsizer.Fit(self)


        nsizer.Add(self.bookmark, 0, wx.CENTER|wx.EXPAND, 0)
        return nsizer

    def OnFind(self, event):
        value = self.narrow.GetValue()
        if not value:
            cw.cwpy.play_sound("error")
            self.OnNextButton(event)
            #ENTERから呼ばれた場合に操作性が悪化するのでFocusを飛ばす
            return
        narrow = self.narrow_type.GetSelection()
        if narrow == 0:
            ftype = cw.scenariodb.DATA_TITLE
        elif narrow == 1:
            ftype = cw.scenariodb.DATA_DESC
        elif narrow == 2:
            ftype = cw.scenariodb.DATA_AUTHOR
        elif narrow == 3:
            ftype = cw.scenariodb.DATA_LEVEL
            try:
                value = int(value)
            except:
                cw.cwpy.play_sound("error")
                self.OnNextButton(event)
                return
        elif narrow == 4:
            ftype = cw.scenariodb.DATA_FNAME
        else:
            assert False
        headers = self.db.find_headers(ftype, value, skintype=cw.cwpy.setting.skintype)
        cw.cwpy.play_sound("harvest")
        self._set_findresult(headers, False)

        if cw.cwpy.setting.show_paperandtree or not (self.tree and self.tree.IsShown()):
            self.draw(True)

    def _set_findresult(self, headers, selfirstheader):
        list = self.scetable[self._get_linktarget(self.scedir)]
        if list and isinstance(list[0], FindResult):
            findresult = list[0]
        else:
            findresult = FindResult()
            list.insert(0, findresult)
            self.find_result = findresult
            self.scetable[self._get_linktarget(self.scedir)] = list

        self.scetable[findresult] = headers[:]
        cansort = 1 < len(headers) and isinstance(headers[0], cw.header.ScenarioHeader)
        if cansort:
            findresult.headers = self._sort_headers(headers)
        else:
            findresult.headers = headers[:]

        # 検索結果ディレクトリを表示する
        if self.tree and self.tree.IsShown():
            item, _cookie = self.tree.GetFirstChild(self.tree.root)
            if item and item.IsOk():
                data = self.tree.GetItemPyData(item)
                if data and isinstance(data[1], FindResult):
                    self.tree.Delete(item)
            item = self._create_findresultitem(0, self.tree.root, findresult)
            parent = item
            self.tree.Expand(item)
            item = self.tree.GetNextSibling(item)
            while item and item.IsOk():
                data = self.tree.GetItemPyData(item)
                if data:
                    index, header = data
                    self.tree.SetItemPyData(item, (index+1, header))
                item = self.tree.GetNextSibling(item)
            if headers and selfirstheader:
                item, _cookie = self.tree.GetFirstChild(parent)
                self.tree.SelectItem(item)
                list = self.scetable[self.find_result]
            else:
                self.tree.SelectItem(parent)
            self._tree_selchanged()
        else:
            if headers and selfirstheader:
                self.nowdir = self.find_result
                list = self.scetable[self.find_result]
            else:
                self.nowdir = self.scedir

        self.list = self._narrow_scenario(list)
        self.index = 0
        if headers and selfirstheader:
            self.dirstack = [(self.scedir, "/find_result")]

    def OnBookmark(self, event):
        # ブックマークメニューを生成して表示する
        cw.cwpy.play_sound("page")
        if not self.bookmarkmenu:
            self.create_bookmarkmenu()
        self._add_bookmark.Enable(not self._is_specialselected())
        self.bookmark.PopupMenu(self.bookmarkmenu)

    def OnBookmark2(self, event):
        cw.cwpy.play_sound("page")
        if not self.bookmarkmenu:
            self.create_bookmarkmenu()
        size = self.bookmark.GetSize()
        self._add_bookmark.Enable(not self._is_specialselected())
        self.bookmark.PopupMenuXY(self.bookmarkmenu, size[0] / 2, size[1] / 2)

    def _is_specialselected(self):
        return not self.list or isinstance(self.list[self.index], FindResult)

    def create_bookmarkmenu(self):
        if self.bookmarkmenu:
            self.bookmarkmenu.Destroy()
        menu = wx.Menu()
        self.bookmarkmenu = menu
        icon_add = cw.cwpy.rsrc.dialogs["BOOKMARK"]
        icon_arrange = cw.cwpy.rsrc.dialogs["ARRANGE_BOOKMARK"]
        icon_summary = cw.cwpy.rsrc.dialogs["SUMMARY"]
        icon_complete = cw.cwpy.rsrc.dialogs["SUMMARY_COMPLETE"]
        icon_playing = cw.cwpy.rsrc.dialogs["SUMMARY_PLAYING"]
        icon_invisible = cw.cwpy.rsrc.dialogs["SUMMARY_INVISIBLE"]
        icon_dir = cw.cwpy.rsrc.dialogs["DIRECTORY"]

        font = cw.cwpy.rsrc.get_wxfont("menu", pixelsize=cw.wins(13))

        self._add_bookmark = wx.MenuItem(menu, -1, cw.cwpy.msgs["add_bookmark"])
        self._add_bookmark.SetBitmap(icon_add)
        self._add_bookmark.SetFont(font)
        menu.AppendItem(self._add_bookmark)
        menu.Bind(wx.EVT_MENU, self.OnAddBookmark, self._add_bookmark)

        arrange = wx.MenuItem(menu, -1, cw.cwpy.msgs["arrange_bookmark"])
        arrange.SetBitmap(icon_arrange)
        arrange.SetFont(font)
        menu.AppendItem(arrange)
        menu.Bind(wx.EVT_MENU, self.OnArrangeBookmark, arrange)

        # ブックマークを開くためのユーティリティクラス
        class OpenBookmark(object):
            def __init__(self, outer, bookmark, bookmarkpath):
                self.outer = outer
                self.bookmark = bookmark
                self.bookmarkpath = bookmarkpath

            def OnOpen(self, event):
                cw.cwpy.play_sound("equipment")
                if self.outer.narrow.GetValue():
                    self.outer.narrow.SetValue("")
                    self.outer.update_narrowcondition()
                self.outer.set_selected(self.bookmark, self.bookmarkpath, opendir=True)

        if cw.cwpy.ydata.bookmarks:
            menu.AppendSeparator()
            for bookmark, bookmarkpath in cw.cwpy.ydata.bookmarks:
                if bookmark:
                    path = self.scedir
                    for p in bookmark:
                        if p.startswith("/"):
                            path = bookmarkpath
                            p = os.path.basename(path)
                            break
                        path = cw.util.join_paths(path, p)
                        if not os.path.exists(path):
                            path = bookmarkpath
                            p = os.path.basename(path)
                            break
                        path = cw.util.get_linktarget(path)
                else:
                    path = bookmarkpath
                    p = os.path.basename(path)

                path = cw.util.get_linktarget(path)
                if self.is_scenario(path):
                    header = self.db.search_path(path, skintype=cw.cwpy.setting.skintype)
                elif os.path.isdir(path):
                    header = None
                else:
                    header = None
                    if bookmark and bookmark[-1]:
                        p = bookmark[-1]
                    elif bookmarkpath:
                        p = os.path.basename(bookmarkpath)
                    else:
                        p = u""

                if header:
                    item = wx.MenuItem(menu, -1, header.name.replace("&", "&&"))
                    item.SetFont(font)
                    if self.is_playing(header):
                        item.SetBitmap(icon_playing)
                    elif self.is_complete(header):
                        item.SetBitmap(icon_complete)
                    elif self.is_invisible(header):
                        item.SetBitmap(icon_invisible)
                    else:
                        item.SetBitmap(icon_summary)
                else:
                    if not p:
                        p = u"[フォルダが見つかりません]"
                    elif sys.platform == "win32":
                        sp = os.path.splitext(p)
                        if sp[1].lower() == ".lnk":
                            p = sp[0]
                    item = wx.MenuItem(menu, -1, p.replace("&", "&&"))
                    item.SetFont(font)
                    item.SetBitmap(icon_dir)

                openbookmark = OpenBookmark(self, bookmark, bookmarkpath)
                menu.AppendItem(item)
                menu.Bind(wx.EVT_MENU, openbookmark.OnOpen, item)

    def OnAddBookmark(self, event):
        self._update_saveddirstack()
        header = self.list[self.index]
        if isinstance(header, FindResult):
            return
        cw.cwpy.play_sound("signal")
        if isinstance(header, cw.header.ScenarioHeader):
            name = header.name
        else:
            name = os.path.basename(header)
            if sys.platform == "win32":
                sp = os.path.splitext(name)
                if sp[1].lower() == ".lnk":
                    name = sp[0]
        s = cw.cwpy.msgs["add_bookmark_message"] % (name)
        dlg = message.YesNoMessage(self, cw.cwpy.msgs["message"], s)
        self.Parent.move_dlg(dlg)

        if not dlg.ShowModal() == wx.ID_OK:
            dlg.Destroy()
            return
        dlg.Destroy()

        def func(panel, selected, selectedpath):
            cw.cwpy.ydata.add_bookmark(selected, selectedpath)
            cw.cwpy.play_sound("harvest")
            def func(panel):
                if panel:
                    panel.bookmarkmenu = None
            cw.cwpy.frame.exec_func(func, panel)
        sel, selpath = self.get_selected()
        cw.cwpy.exec_func(func, self, sel, selpath)

    def OnArrangeBookmark(self, event):
        cw.cwpy.play_sound("click")
        dlg = cw.dialog.etc.BookmarkDialog(self, self.scedir, self.db)
        self.Parent.move_dlg(dlg)
        dlg.ShowModal()
        dlg.Destroy()
        def func(panel):
            def func(panel):
                if panel:
                    panel.bookmarkmenu = None
            cw.cwpy.frame.exec_func(func, panel)
        cw.cwpy.exec_func(func, self)

    def OnLeftDClick(self, event):
        if self._processing:
            return
        if self.can_clickside() and self.clickmode == wx.LEFT:
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.leftbtn.GetId())
            self.ProcessEvent(btnevent)
        elif self.can_clickside() and self.clickmode == wx.RIGHT:
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.rightbtn.GetId())
            self.ProcessEvent(btnevent)

    def OnLeftDClick2(self, event):
        if not (self.tree.HitTest(event.GetPosition())[1] & wx.TREE_HITTEST_ONITEM):
            return
        self._tree_dclick()

    def _tree_dclick(self):
        selitem = self.tree.GetSelection()
        if not selitem:
            return
        data = self.tree.GetItemPyData(selitem)
        if not data:
            return
        _index, pathorheader = data
        if isinstance(pathorheader, cw.header.ScenarioHeader):
            if self.viewbtn:
                if self.viewbtn.IsEnabled():
                    btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.viewbtn.GetId())
                    self.ProcessEvent(btnevent)
            elif self.yesbtn.IsEnabled():
                btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.yesbtn.GetId())
                self.ProcessEvent(btnevent)
        else:
            if self.tree.IsExpanded(selitem):
                cw.cwpy.play_sound("page")
                self.tree.Collapse(selitem)
            else:
                cw.cwpy.play_sound("equipment")
                self.tree.Expand(selitem)

    def OnKeyDown(self, event):
        if event.GetKeyCode() <> wx.WXK_RETURN:
            event.Skip()
            return

        selitem = self.tree.GetSelection()
        if not selitem:
            return
        data = self.tree.GetItemPyData(selitem)
        if not data:
            return
        _index, pathorheader = data
        if isinstance(pathorheader, cw.header.ScenarioHeader):
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_YES)
            self.ProcessEvent(btnevent)
        else:
            self._tree_dclick()

    def can_clickcenter(self):
        return self.yesbtn.IsEnabled()

    def get_selected(self):
        """
        現在選択されているシナリオを経路形式
        (ディレクトリ・ファイル名の配列)で返す。
        """
        seq = []
        if not self.list or not self._saved_list:
            return seq, u""

        spdir = False
        for _dpath, selname in self._saved_dirstack:
            if selname.startswith("/"):
                seq = []
                spdir = True
                break
            seq.append(selname)

        sel = self._saved_list[self._saved_index]
        if isinstance(sel, cw.header.ScenarioHeader):
            if not spdir:
                seq.append(sel.fname)
            return seq, os.path.abspath(sel.get_fpath())
        elif isinstance(sel, FindResult):
            return [], u""
        else:
            if not spdir:
                seq.append(os.path.basename(sel))
            return seq, os.path.abspath(sel)

    def _get_nowlist(self, nowdir=None, update=True):
        if nowdir is None:
            nowdir = self.nowdir
        nowdir = self._get_linktarget(nowdir)
        if not update and nowdir in self.scetable:
            return self.scetable[nowdir]
        if isinstance(nowdir, FindResult):
            return nowdir.headers
        seq = []
        if nowdir == self.scedir and self.find_result:
            seq.append(self.find_result)
        seq.extend(self.db.search_dpath(nowdir, skintype=cw.cwpy.setting.skintype))
        seq.extend(self.get_dpaths(nowdir))
        return seq

    def set_selected(self, spaths, fullpath, opendir=False, updatetree=False, findresults=[]):
        """
        シナリオを経路形式(ディレクトリ・ファイル名の配列)で
        設定する。
        """
        processing = self._processing
        self._processing = True

        exists_spaths = bool(spaths)
        spath = self.scedir
        updatetreeitem = None
        for path in spaths:
            if path.startswith("/"):
                exists_spaths = False
                break
            spath = cw.util.join_paths(spath, path)
            spath = cw.util.get_linktarget(spath)
            if not os.path.exists(spath):
                exists_spaths = False
                break

        selfullpath = False
        if not exists_spaths:
            headers = []
            if findresults:
                for fpath in findresults:
                    header = self.db.search_path(fpath)
                    if header:
                        headers.append(header)

            if headers:
                self._set_findresult(headers, True)
                selfullpath = True
            elif self.is_scenario(fullpath):
                header = self.db.search_path(fullpath)
                if header and self.is_showing(header):
                    self._set_findresult([header], True)
                    selfullpath = True
                else:
                    exists_spaths = False
            elif os.path.isdir(fullpath):
                self._set_findresult([fullpath], True)
                selfullpath = True
            else:
                exists_spaths = False

        if not selfullpath and (not spaths or not exists_spaths):
            # 対象が存在しない場合(初期ディレクトリを選択)
            self.nowdir = self.scedir
            self.index = 0
            self.dirstack = []
            self.list = self._get_nowlist(update=True)
            self.scetable[self._get_linktarget(self.nowdir)] = self.list
            self.list = self._narrow_scenario(self.list)

        elif not selfullpath:
            # 経路をたどれる場合
            parent = self.scedir
            self.dirstack = []
            exists = True
            treeitem = self.tree.root
            for fname in spaths[:-1]:
                if fname.startswith("/"):
                    break
                parent2 = cw.util.join_paths(parent, fname)
                if os.path.exists(parent2):
                    self.dirstack.append((parent, fname))
                    parent = cw.util.get_linktarget(parent2)
                    if self.tree.IsShown():
                        paritem = treeitem
                        item, cookie = self.tree.GetFirstChild(paritem)
                        while item.IsOk():
                            data = self.tree.GetItemPyData(item)
                            assert not data is None
                            index, header = data
                            if not isinstance(header, cw.header.ScenarioHeader) and\
                               not isinstance(header, FindResult) and\
                                    os.path.normcase(os.path.basename(header)) ==\
                                    os.path.normcase(fname):
                                treeitem = item
                                if not self.tree.IsExpanded(item) or\
                                        not self.tree.GetItemPyData(self.tree.GetFirstChild(item)[0]):
                                    self.tree.Expand(item)
                                    self.create_treeitems(item)
                                    updatetree = False
                                else:
                                    updatetreeitem = item
                                break
                            item, cookie = self.tree.GetNextChild(paritem, cookie)
                else:
                    exists = False
                    break

            self.nowdir = parent
            self.list = self._get_nowlist(update=True)
            self.scetable[self._get_linktarget(self.nowdir)] = self.list
            self.list = self._narrow_scenario(self.list)
            self.index = 0

            if updatetree and self.tree.IsShown():
                # 探索経路以外でリストを更新すべき箇所があれば更新しておく
                if updatetreeitem:
                    self.create_treeitems(updatetreeitem)
                else:
                    self.create_treeitems(self.tree.root)

            if exists:
                fname = os.path.normcase(spaths[-1])
                for index, sel in enumerate(self.list):
                    if isinstance(sel, FindResult):
                        continue
                    elif isinstance(sel, cw.header.ScenarioHeader):
                        name = sel.fname
                    else:
                        name = os.path.basename(sel)
                    if os.path.normcase(name) == fname:
                        self.index = index
                        if self.tree.IsShown():
                            item, cookie = self.tree.GetFirstChild(treeitem)
                            i = 0
                            while item.IsOk() and i <> index:
                                item, cookie = self.tree.GetNextChild(treeitem, cookie)
                                i += 1
                            if item.IsOk():
                                self.tree.SelectItem(item)
                                if not isinstance(sel, cw.header.ScenarioHeader):
                                    self.tree.Expand(item)
                                    self.create_treeitems(item)
                        break

        self._processing = processing
        self.draw(True)
        self.enable_btn()
        if self.list:
            self._enable_btn2(self.list[self.index])
        self._update_saveddirstack()

    def _update_saveddirstack(self):
        if len(self.dirstack) == 1 and self.dirstack[0][0].startswith("/"):
            return
        self._saved_dirstack = self.dirstack[:]
        self._saved_list = self.list[:]
        self._saved_index = self.index

    def index_changed(self):
        self._update_saveddirstack()
        self._paperslide = True

    def OnDropFiles(self, event):
        paths = event.GetFiles()
        headers = self._to_headers(paths)

        if not headers:
            cw.cwpy.play_sound("error")
            return

        self._install_scenario(headers)

    def OnInstallBtn(self, event):
        wildcard = u"シナリオファイル (*.wsn; *.wsm; *.zip; *.lzh; *.cab; Summary.xml)|*.wsn;*.wsm;*.zip;*.cab;Summary.xml"
        dlg = wx.FileDialog(self, u"インストールするシナリオを選択", wildcard=wildcard, style=wx.FD_OPEN|wx.FD_MULTIPLE)
        if dlg.ShowModal() == wx.ID_OK:
            paths = dlg.GetPaths()
            headers = self._to_headers(paths)
            if headers:
                self._install_scenario(headers)

    def OnCreateDirBtn(self, event):
        cw.cwpy.play_sound("signal")
        dpath = self.nowdir
        if isinstance(dpath, FindResult):
            dpath = self.scedir
        s = u"%sに作成する新しいフォルダの名前を入力してください。" % (os.path.basename(dpath))
        dname = cw.util.join_paths(dpath, u"新規フォルダ")
        dname = cw.util.dupcheck_plus(dname, yado=False)
        dname = os.path.basename(dname)
        dlg = cw.dialog.edit.InputTextDialog(self, u"新規フォルダ",
                                             msg=s,
                                             text=dname)
        self.Parent.move_dlg(dlg)
        if dlg.ShowModal() == wx.ID_OK:
            cw.cwpy.play_sound("harvest")
            dpath = cw.util.join_paths(dpath, dlg.text)
            dpath = cw.util.dupcheck_plus(dpath, yado=False)
            os.makedirs(dpath)

            self._update_saveddirstack()
            lastscenario, lastscenariopath = self.get_selected()
            if lastscenario:
                lastscenario[-1] = os.path.basename(dpath)
            else:
                lastscenario = [os.path.basename(dpath)]
            lastscenariopath = os.path.abspath(dpath)
            self.set_selected(lastscenario, lastscenariopath, updatetree=True)

    def _to_headers(self, paths):
        headers = []
        for path in paths:
            if os.path.isfile(path) and not os.path.splitext(path)[1].lower() in (".wsn", ".zip", ".lzh", ".cab"):
                path = os.path.dirname(path)
            header = self.db.search_path(path)
            if header:
                headers.append(header)
            elif os.path.isdir(path):
                headers.extend(self.db.search_dpath(path))
        return headers

    def _show_selectedscenario(self, headers):
        self._processing = True
        cw.cwpy.play_sound("equipment")
        self.narrow.SetValue("")
        selfirstheader = (1 == len(headers))
        self._set_findresult(headers, selfirstheader=selfirstheader)

        self._processing = False
        if cw.cwpy.setting.show_paperandtree or not (self.tree and self.tree.IsShown()):
            self.draw(True)
        self.enable_btn()

    def _install_scenario(self, headers):
        """
        headersを選択中のディレクトリにインストールする。
        シナリオDB内に同じ名前・作者のシナリオがあった場合は
        プレイヤーへの問い合わせの上で置換する。
        """
        if not headers:
            return

        # シナリオのインストール
        dpath = self.nowdir
        if isinstance(dpath, FindResult):
            dpath = self.scedir
            seldname = u""
        if self.list:
            sel = self.list[self.index]
            if isinstance(sel, (FindResult, cw.header.ScenarioHeader)):
                seldname = u""
            else:
                dpath = sel
                seldname = os.path.basename(sel)
        else:
            seldname = u""

        cw.cwpy.play_sound("signal")
        if sys.platform == "win32" and os.path.isfile(dpath) and os.path.splitext(dpath)[1].lower() == ".lnk":
            dname = os.path.splitext(os.path.basename(dpath))[0]
        else:
            dname = os.path.basename(dpath)
        if 1 < len(headers):
            s = u"%s本のシナリオを%sにインストールしますか？" % (len(headers), dname)
        else:
            s = u"「%s」を%sにインストールしますか？" % (headers[0].name, dname)

        dpath = cw.util.get_linktarget(dpath)

        choices = (
            (u"インストール", wx.ID_YES, cw.wins(105)),
            (u"表示のみ", wx.ID_NO, cw.wins(105)),
            (u"キャンセル", wx.ID_CANCEL, cw.wins(105)),
        )
        dlg = message.Message(self, cw.cwpy.msgs["message"], s, mode=3, choices=choices)
        self.Parent.move_dlg(dlg)
        ret = dlg.ShowModal()
        dlg.Destroy()

        if ret == wx.ID_CANCEL:
            return

        elif ret == wx.ID_YES:

            # インストール済みの情報が見つかったシナリオ
            db_exists = {}

            for header in headers:
                header2 = self.db.find_scenario(header.name, header.author, skintype=cw.cwpy.setting.skintype,
                                                ignore_dpath=header.dpath, ignore_fname=header.fname)
                if header2:
                    db_exists[header.get_fpath()] = header2

            if db_exists:
                if 1 < len(db_exists):
                    s = u"%s本のシナリオがすでにインストール済みです。\n以前インストールしたシナリオを置換しますか？" % (len(db_exists))
                else:
                    header2 = list(db_exists.itervalues())[0]
                    sname = header2.name if header2.name else u"(無名のシナリオ)"
                    if header2.author:
                        sname += u"(%s)" % header2.author
                    s = u"インストール済みの「%s」がシナリオデータベース上に見つかりました。\n以前インストールしたシナリオを置換しますか？" % (sname)
                dlg = message.YesNoCancelMessage(self, cw.cwpy.msgs["message"], s)
                cw.cwpy.frame.move_dlg(dlg)
                ret = dlg.ShowModal()
                dlg.Destroy()
                if ret == wx.ID_CANCEL:
                    return
                elif ret <> wx.ID_YES:
                    db_exists.clear()

            # プログレスダイアログ表示
            dlg = cw.dialog.progress.ProgressDialog(self, u"シナリオのインストール",
                                                    "", maximum=len(headers), cancelable=True)

            class InstallThread(threading.Thread):
                def __init__(self, outer, headers, dstpath, db_exists):
                    threading.Thread.__init__(self)
                    self.outer = outer
                    self.headers = headers
                    self.dstpath = dstpath
                    self.db_exists = db_exists
                    self.num = 0
                    self.msg = u""
                    self.firstpath = u""
                    self.failed = None
                    self.updates = set()
                    self.paths = []

                def run(self):
                    dstpath = os.path.normcase(os.path.normpath(os.path.abspath(self.dstpath)))
                    allret = [None]
                    for header in self.headers:
                        if dlg.cancel:
                            break
                        try:
                            self.msg = u"「%s」をコピーしています..." % (header.name)
                            fpath = header.get_fpath()
                            header2 = self.db_exists.get(fpath, None)
                            rmpath = u""
                            if header2:
                                # DBに登録されている既存のシナリオを置換
                                dst = cw.util.join_paths(header2.dpath, os.path.basename(fpath))
                                rmpath = header2.get_fpath()
                            else:
                                # 指定箇所にインストール
                                dst = cw.util.join_paths(self.dstpath, os.path.basename(fpath))
                                if dstpath <> os.path.normcase(os.path.normpath(os.path.abspath(header.dpath))):
                                    if os.path.exists(dst):
                                        s = u"%sはすでに存在します。置換しますか？" % (os.path.basename(dst))
                                        def func(self):
                                            choices = (
                                                (u"置換", wx.ID_YES, cw.wins(80)),
                                                (u"名前変更", wx.ID_DUPLICATE, cw.wins(80)),
                                                (u"スキップ", wx.ID_NO, cw.wins(80)),
                                                (u"中止", wx.ID_CANCEL, cw.wins(80)),
                                            )
                                            dlg2 = message.Message(dlg, cw.cwpy.msgs["message"], s, mode=3, choices=choices)
                                            cw.cwpy.frame.move_dlg(dlg2)
                                            ret = dlg2.ShowModal()
                                            dlg2.Destroy()
                                            if wx.GetKeyState(wx.WXK_SHIFT):
                                                allret[0] = ret

                                            return ret

                                        if allret[0] is None:
                                            ret = cw.cwpy.frame.sync_exec(func, self.outer)
                                        else:
                                            ret = allret[0]

                                        if ret == wx.ID_YES:
                                            rmpath = dst
                                        elif ret == wx.ID_NO:
                                            self.num += 1
                                            continue
                                        elif ret == wx.ID_CANCEL:
                                            break
                                        else:
                                            dst = cw.util.dupcheck_plus(dst, yado=False)

                            if os.path.normcase(os.path.normpath(os.path.abspath(fpath))) <>\
                                    os.path.normcase(os.path.normpath(os.path.abspath(dst))):
                                if rmpath:
                                    cw.util.remove(rmpath, trashbox=True)
                                shutil.move(fpath, dst)

                            self.updates.add(os.path.dirname(dst))

                            if not self.firstpath:
                                self.firstpath = dst
                            self.paths.append(dst)
                            self.num += 1
                        except:
                            cw.util.print_ex(file=sys.stderr)
                            self.failed = header
                            break

            thread = InstallThread(self, headers, dpath, db_exists)
            thread.start()

            def progress():
                while thread.is_alive():
                    wx.CallAfter(dlg.Update, thread.num, thread.msg)
                    time.sleep(0.001)
                wx.CallAfter(dlg.Destroy)

            thread2 = threading.Thread(target=progress)
            thread2.start()
            cw.cwpy.frame.move_dlg(dlg)
            dlg.ShowModal()

            if thread.failed:
                s = u"「%s」のインストールに失敗しました。" % (thread.failed.name)
                dlg = cw.dialog.message.ErrorMessage(self, s)
                cw.cwpy.frame.move_dlg(dlg)
                dlg.ShowModal()
                dlg.Destroy()

            elif thread.firstpath:
                cw.cwpy.play_sound("harvest")

                for dpath in thread.updates:
                    self.db.update(dpath, skintype=cw.cwpy.setting.skintype)

                self._update_saveddirstack()
                lastscenario, lastscenariopath = self.get_selected()
                if lastscenario:
                    dpath = cw.util.get_linktarget(self.nowdir)
                    if seldname:
                        lastscenario[-1] = seldname
                        lastscenario.append(os.path.basename(thread.firstpath))
                    else:
                        lastscenario[-1] = os.path.basename(thread.firstpath)
                else:
                    dpath = cw.util.get_linktarget(self.scedir)
                    if seldname:
                        lastscenario = [seldname, os.path.basename(thread.firstpath)]
                    else:
                        lastscenario = [os.path.basename(thread.firstpath)]
                lastscenariopath = os.path.abspath(thread.firstpath)
                self._processing = True
                self.narrow.SetValue(u"")
                self._processing = False
                self.set_selected(lastscenario, lastscenariopath, updatetree=True, findresults=thread.paths)

            return

        self._show_selectedscenario(headers)

    def OnClickInfoBtn(self, event):
        cw.cwpy.play_sound("click")
        dlg = text.Readme(self, cw.cwpy.msgs["description"], self.texts)
        self.Parent.move_dlg(dlg)
        dlg.ShowModal()
        dlg.Destroy()

    def OnClickYesBtn(self, event):
        if self.yesbtn.GetLabel() == cw.cwpy.msgs["see"]:
            if self.tree.IsShown():
                cw.cwpy.play_sound("equipment")
                self._no_treechangedsound = True
                selitem = self.tree.GetSelection()
                item = self.tree.GetFirstChild(selitem)[0]
                if not item.IsOk() or not self.tree.GetItemPyData(item):
                    self.create_treeitems(selitem)
                    item = self.tree.GetFirstChild(selitem)[0]
                if item.IsOk():
                    self.tree.SelectItem(item)
                self._no_treechangedsound = False
            else:
                cw.cwpy.play_sound("equipment")
                if isinstance(self.list[self.index], FindResult):
                    self.dirstack.append((self.nowdir, "/find_result"))
                    self.nowdir = self.list[self.index]
                else:
                    self.dirstack.append((self.nowdir, os.path.basename(self.list[self.index])))
                    self.nowdir = cw.util.get_linktarget(self.list[self.index])
                self.list = self._get_nowlist(update=True)
                self.scetable[self._get_linktarget(self.nowdir)] = self.list
                self.list = self._narrow_scenario(self.list)
                self.index = 0
                self.enable_btn()
                self.draw(True)
                self._update_saveddirstack()
        elif self.yesbtn.GetLabel() == cw.cwpy.msgs["decide"]:
            self._update_saveddirstack()
            cw.cwpy.play_sound("signal")
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_OK)
            self.ProcessEvent(btnevent)

    def BackPaper(self):
        cw.cwpy.play_sound("equipment")
        self.nowdir, selname = self.dirstack.pop()
        self.list = self._get_nowlist(update=True)
        self.scetable[self._get_linktarget(self.nowdir)] = self.list
        self.list = self._narrow_scenario(self.list)
        self.index = 0
        if not selname.startswith("/"):
            selname = os.path.normcase(selname)
            for index, name in enumerate(self.list):
                if not isinstance(name, (cw.header.ScenarioHeader, FindResult)):
                    name = os.path.normcase(os.path.basename(name))
                    if selname == name:
                        self.index = index

        self.enable_btn()

        self.draw(True)

    def OnClickNoBtn(self, event):
        if self.nobtn.GetLabel() == cw.cwpy.msgs["return"]:
            assert not self.tree.IsShown()
            self.BackPaper()
        elif self.nobtn.GetLabel() == cw.cwpy.msgs["entry_cancel"]:
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
            self.ProcessEvent(btnevent)

    def OnClickViewBtn(self, event):
        if cw.cwpy.setting.show_paperandtree:
            return

        cw.cwpy.play_sound("equipment")
        if self.tree.IsShown():
            self.tree.Hide()
            self.toppanel.Show()
            selitem = self.tree.GetSelection()
            if selitem and self.tree.IsExpanded(selitem):
                self.update_narrowcondition()
            else:
                self.draw(True)
            cw.cwpy.setting.show_scenariotree = False
        else:
            self.show_tree()
            selitem = self.tree.GetSelection()
            if selitem and selitem.IsOk() and not self.tree.IsVisible(selitem):
                self.tree.ScrollTo(selitem)
                self.tree.SetScrollPos(wx.HORIZONTAL, 0)
            self.toppanel.Hide()
            self.tree.Show()
            self.tree.SetFocus()
            cw.cwpy.setting.show_scenariotree = True

        self.update_additionals()

        self.enable_btn()
        self.Layout()

    def _can_opendir(self):
        return bool(self.list and not isinstance(self.list[self.index], FindResult))

    def _can_editor(self):
        return bool(cw.cwpy.setting.editor and self.list and isinstance(self.list[self.index], cw.header.ScenarioHeader))

    def open_directory(self):
        if not self.list:
            return
        header = self.list[self.index]
        if isinstance(header, FindResult):
            return

        cw.cwpy.play_sound("click")

        def open_file(fpath):
            fpath = os.path.normpath(fpath)
            filer = cw.cwpy.setting.filer_file
            encoding = sys.getfilesystemencoding()
            if filer:
                filer = filer.encode(encoding)
                fpath = fpath.encode(encoding)
                seq = [filer, fpath]
                try:
                    subprocess.Popen(seq)
                except:
                    s = u"「%s」の実行に失敗しました。設定の [シナリオ] > [外部アプリ] > [ファイラー(ファイル用)] に適切なエディタを指定してください。" % (os.path.basename(cw.cwpy.setting.filer_file))
                    dlg = cw.dialog.message.ErrorMessage(self, s)
                    cw.cwpy.frame.move_dlg(dlg)
                    dlg.ShowModal()
                    dlg.Destroy()

            else:
                if sys.platform == "win32":
                    s = "explorer /select,\"%s\"" % (fpath)
                elif sys.platform.startswith("darwin"):
                    s = "open \"%s\"" % (os.path.dirname(fpath))
                elif sys.platform.startswith("linux"):
                    s = "nautilus \"%s\"" % (os.path.dirname(fpath))
                else:
                    cw.cwpy.play_sound("error")
                os.popen(s.encode(encoding))

        def open_dir(dpath):
            dpath = os.path.normpath(dpath)
            filer = cw.cwpy.setting.filer_dir
            encoding = sys.getfilesystemencoding()
            if filer:
                filer = filer.encode(encoding)
                dpath = dpath.encode(encoding)
                seq = [filer, dpath]
                try:
                    subprocess.Popen(seq)
                except:
                    s = u"「%s」の実行に失敗しました。設定の [シナリオ] > [外部アプリ] > [ファイラー(フォルダ用)] に適切なエディタを指定してください。" % (os.path.basename(cw.cwpy.setting.filer_dir))
                    dlg = cw.dialog.message.ErrorMessage(self, s)
                    cw.cwpy.frame.move_dlg(dlg)
                    dlg.ShowModal()
                    dlg.Destroy()

            else:
                if sys.platform == "win32":
                    s = "explorer \"%s\"" % (dpath)
                elif sys.platform.startswith("darwin"):
                    s = "open \"%s\"" % (dpath)
                elif sys.platform.startswith("linux"):
                    s = "nautilus \"%s\"" % (dpath)
                else:
                    cw.cwpy.play_sound("error")
                os.popen(s.encode(encoding))

        if isinstance(header, cw.header.ScenarioHeader):
            s = header.get_fpath()
            s = os.path.abspath(s)
            s = cw.util.get_linktarget(s)
            if os.path.isfile(s):
                open_file(s)
            else:
                if os.path.isfile(os.path.join(s, u"Summary.wsm")):
                    open_file(os.path.join(s, u"Summary.wsm"))
                elif os.path.isfile(os.path.join(s, u"Summary.xml")):
                    open_file(os.path.join(s, u"Summary.xml"))
                else:
                    open_dir(s)
        else:
            s = os.path.abspath(header)
            s = cw.util.get_linktarget(s)
            open_dir(s)

    def open_with_editor(self):
        if not self.list:
            return
        editor = cw.cwpy.setting.editor
        if not editor:
            return

        header = self.list[self.index]
        if not isinstance(header, cw.header.ScenarioHeader):
            return

        cw.cwpy.play_sound("click")

        # エディタ起動
        fpath = header.get_fpath()
        fpath = os.path.abspath(fpath)
        fpath = cw.util.get_linktarget(fpath)
        if os.path.isdir(fpath):
            # WirthBuilderはSummary.wsmのパスを渡さないとシナリオを開けない
            wsm = cw.util.join_paths(fpath, "Summary.wsm")
            if os.path.isfile(wsm):
                fpath = wsm
        fpath = os.path.normpath(fpath)
        encoding = sys.getfilesystemencoding()
        editor = editor.encode(encoding)
        fpath = fpath.encode(encoding)
        seq = [editor, fpath]

        try:
            subprocess.Popen(seq)
        except:
            s = u"「%s」の実行に失敗しました。設定の [シナリオ] > [外部アプリ] > [エディタ] に適切なエディタを指定してください。" % (os.path.basename(cw.cwpy.setting.editor))
            dlg = cw.dialog.message.ErrorMessage(self, s)
            cw.cwpy.frame.move_dlg(dlg)
            dlg.ShowModal()
            dlg.Destroy()

    def convert_scenario(self):
        if not self.list:
            return
        header = self.list[self.index]
        if not isinstance(header, cw.header.ScenarioHeader) or header.type <> 1:
            return

        fpath = header.get_fpath()
        fpath = cw.util.get_linktarget(fpath)
        self.conv_scenario(fpath)

    def OnSelect(self, event):
        #貼り紙バグ
        if not self.list or not self.yesbtn.Enabled:
            if not self._paperslide:
                return
        #if not self.list or not self.can_clickcenter():
        #if not self.list or not self.toppanel.SetCursor(cw.cwpy.rsrc.cursors["CURSOR_ARROW"]):

        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_YES)
        self.ProcessEvent(btnevent)

    def OnCancel(self, event):
        if self.nobtn.GetLabel() == cw.cwpy.msgs["entry_cancel"]:
            cw.cwpy.play_sound("click")

        if self.dirstack and cw.cwpy.setting.show_paperandtree:
            self.BackPaper()
        else:
            btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.nobtn.GetId())
            self.ProcessEvent(btnevent)

    def OnDestroy(self, event):
        self.db.close()
        if self.bookmarkmenu:
            self.bookmarkmenu.Destroy()

    def _on_narrowcondition(self):
        #cw.cwpy.setting.scenario_narrow = self.narrow.GetValue()
        cw.cwpy.setting.scenario_narrowtype = self.narrow_type.GetSelection()
        cw.cwpy.setting.scenario_sorttype = self.sort.GetSelection()
        self.update_narrowcondition()

    def draw(self, update=False):
        self._draw_impl(update)

    def _get_bg(self):
        if self._bg:
            return self._bg
        path = "Table/Bill"
        path = cw.util.find_resource(cw.util.join_paths(cw.cwpy.skindir, path), cw.cwpy.rsrc.ext_img)
        self._bg = cw.util.load_wxbmp(path, can_loaded_scaledimage=True)
        return self._bg

    def get_detailtext(self):
        lines = []
        if cw.cwpy.setting.show_paperandtree or not (self.tree and self.tree.IsShown()):
            s1 = self._get_paperdetailtext()
        else:
            s1 = u""

        if self.tree and self.tree.IsShown():
            s2 = self._get_treedetailtext()
        else:
            s2 = u""

        if s1:
            lines.append(s1)
            if s2:
                lines.append(u"-" * 38)

        if s2:
            lines.append(s2)

        if lines and not lines[-1].endswith(u"\n"):
            lines.append(u"")

        return u"\n".join(lines)

    def _get_paperdetailtext(self):
        if not self.list:
            return u""

        lines = []
        if isinstance(self.list[self.index], cw.header.ScenarioHeader):
            header = self.list[self.index]
            name = header.name
            if header.levelmin and header.levelmax:
                if header.levelmin == header.levelmax:
                    level = u"%s" % (header.levelmax)
                else:
                    level = u"%s～%s" % (header.levelmin, header.levelmax)
            elif header.levelmin:
                level = u"%s～" % (header.levelmin)
            elif header.levelmax:
                level = u"～%s" % (header.levelmax)
            else:
                level = u""
            if level:
                name = u"%s (%s)" % (name, level)
            name = u"[ %s ]" % name
            slen = cw.util.get_strlen(name)
            if slen < 38:
                name += u"-" * (38-slen)
            lines.append(name)
            if header.author:
                name = u"(%s)" % header.author
                slen = cw.util.get_strlen(name)
                if slen < 38:
                    name = u" " * (38-slen) + name
                lines.append(name)
            lines.append(u"")
            lines.append(header.desc)

        else:
            dpath = self.list[self.index]
            if isinstance(dpath, FindResult):
                name = u"[ %s ]" % cw.cwpy.msgs["find_result"]
            else:
                dpath = os.path.basename(dpath)
                if sys.platform == "win32" and dpath.lower().endswith(".lnk"):
                    dpath = os.path.splitext(dpath)[0]
                name = u"[ %s ]" % dpath
            slen = cw.util.get_strlen(name)
            if slen < 38:
                name += u"-" * (38 - slen)
            lines.append(name)

            for name in self.names:
                addition = ""
                if isinstance(name, cw.header.ScenarioHeader):
                    header = name
                    name = name.name
                    if self.sort.GetSelection() == 2:
                        # 整列条件: 作者名
                        if header.author:
                            addition = u"(%s)" % (header.author)
                    elif self.sort.GetSelection() == 4:
                        # 整列条件: 更新日時
                        addition = u"[%s]" % (self._formatted_mtime(header.mtime, False))
                    elif header.levelmin or header.levelmax:
                        levelmin = str(header.levelmin) if header.levelmin else " "
                        levelmax = str(header.levelmax) if header.levelmax else " "
                        if levelmin == levelmax:
                            addition = u"[%s]" % (levelmin)
                        else:
                            addition = u"[%s～%s]" % (levelmin, levelmax)
                    if self.is_playing(header) or self.is_complete(header) or self.is_invisible(header):
                        pass
                else:
                    if isinstance(dpath, FindResult):
                        name = u"[%s]" % (os.path.basename(name))
                if addition:
                    name += u" %s" % addition
                lines.append(name)

        if lines and not lines[-1].endswith(u"\n"):
            lines.append(u"")

        return u"\n".join(lines)

    def _get_treedetailtext(self):
        if not self.list:
            return u""

        lines = []
        if self.tree and self.tree.IsShown():
            lines.append(u"[%s]" % os.path.basename(self.scedir))
            vline = u"│"
            pline = u"├"
            lline = u"└"
            def recurse(parent, tab):
                item, cookie = self.tree.GetFirstChild(parent)
                while item.IsOk():
                    s = self.tree.GetItemText(item)
                    data = self.tree.GetItemPyData(item)
                    if not data is None:
                        index, header = data
                        if not isinstance(header, cw.header.ScenarioHeader):
                            s = u"[%s]" % (s)
                    parent2 = item
                    item, cookie = self.tree.GetNextChild(parent, cookie)
                    if item.IsOk():
                        lines.append(tab + pline + s)
                    else:
                        lines.append(tab + lline + s)
                    if self.tree.IsExpanded(parent2):
                        if item.IsOk():
                            recurse(parent2, tab + vline + u" ")
                        else:
                            recurse(parent2, tab + u"   ")

            recurse(self.tree.root, u" ")

        return u"\n".join(lines)

    def _draw_impl(self, update=False, dc=None):
        if update:
            self.enable_btn()

            if cw.cwpy.setting.show_paperandtree:
                processing = self._processing
                self._processing = True
                self.select_treeitem(self.index)
                self._processing = processing
            else:
                if self.tree.IsShown():
                    self.select_treeitem(self.index)
                    return

        if not dc:
            dc = select.Select.draw(self, update)

        # 背景
        if cw.cwpy.setting.show_paperandtree or (self.addctrlbtn and not self.addctrlbtn.GetToggle()):
            yp = 0
        else:
            yp = 1
        csize = self.GetClientSize()
        colour = wx.Colour(32, 32, 32)
        dc.SetPen(wx.Pen(colour))
        dc.SetBrush(wx.Brush(colour))
        dc.DrawRectangle(0, 0, csize[0], csize[1])
        bmp = cw.wins(self._get_bg())
        bmpw, bmph = bmp.GetSize()
        dc.DrawBitmap(bmp, 0, yp, False)

        # リストが空だったら描画終了
        if not self.list:
            return

        if not isinstance(self.list[self.index], cw.header.ScenarioHeader):
            dpath = self.list[self.index]

            if update:
                if isinstance(dpath, FindResult):
                    self.names = dpath.headers
                else:
                    if self.updatenames_thr:
                        self.updatenames_thr.quit = True
                        self.updatenames_thr = None
                    self.names = [u"読込中..."]
                    self.updatenames_thr = UpdateNamesThread(self, self.nowdir, dpath, self.dirstack[:],
                                                             startdir=dpath, expandedset=set(),
                                                             skintype=cw.cwpy.setting.skintype)
                    self.updatenames_thr.start()

            # Folder.bmpチェック
            if isinstance(dpath, FindResult):
                scan_folder_bmp = ""
            else:
                scan_folder_bmp = os.path.join(cw.util.get_linktarget(dpath), u"Folder.bmp")
            if scan_folder_bmp and os.path.isfile(scan_folder_bmp):
                # Folder.bmp表示
                folder_bmp = cw.util.load_wxbmp(scan_folder_bmp, True, can_loaded_scaledimage=True)
                bmp2 = cw.wins(folder_bmp)
                size = bmp2.GetSize()
                pos = (cw.wins(200), cw.wins(60)+yp)
                pos = cw.util.get_centerposition(size, pos)
                cw.imageretouch.wxblit_2bitbmp_to_card(dc, bmp2, pos[0], pos[1], True, bitsizekey=folder_bmp)

            else:
                # ディレクトリ名
                dc.SetFont(cw.cwpy.rsrc.get_wxfont("scenario", pixelsize=cw.wins(21)))
                if isinstance(dpath, FindResult):
                    s = cw.cwpy.msgs["find_result"]
                else:
                    s = os.path.basename(dpath)
                    if s.lower().endswith(".lnk"):
                        s = s[0:-len(".lnk")]
                maxwidth = bmpw-cw.wins(135)-cw.wins(5)
                cw.util.draw_witharound(dc, s, cw.wins(135), cw.wins(65)+yp, maxwidth=maxwidth)
                # フォルダ画像
                bmp = cw.cwpy.rsrc.dialogs["FOLDER"]
                dc.DrawBitmap(bmp, cw.wins(65), cw.wins(30)+yp, True)
                if isinstance(dpath, FindResult):
                    # 検索アイコン
                    bmp = cw.cwpy.rsrc.dialogs["FIND_SCENARIO3"]
                    dc.DrawBitmap(bmp, cw.wins(108), cw.wins(65)+yp, True)
                else:
                    if sys.platform == "win32" and dpath.lower().endswith(".lnk"):
                        # リンクシンボル
                        bmp = cw.cwpy.rsrc.dialogs["LINK"]
                        dc.DrawBitmap(bmp, cw.wins(63), cw.wins(65)+yp, False)

            # contents
            dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgtitle", pixelsize=cw.wins(16)))
            s = cw.cwpy.msgs["contents"]
            w = dc.GetTextExtent(s)[0]
            dc.DrawText(s, (bmpw-w)/2, cw.wins(110)+yp)
            # 中身
            font = cw.cwpy.rsrc.get_wxfont("dlglist", pixelsize=cw.wins(14), adjustsize=True)
            font2 = cw.cwpy.rsrc.get_wxfont("dlglist", pixelsize=cw.wins(12))

            names = self._narrow_scenario(self.names)
            if len(names) > 13:
                names = names[0:12]
                names.append(cw.cwpy.msgs["history_etc"])

            y = cw.wins(130)
            for name in names:
                addition = ""
                if isinstance(name, cw.header.ScenarioHeader):
                    header = name
                    name = name.name
                    if self.sort.GetSelection() == 2:
                        # 整列条件: 作者名
                        if header.author:
                            addition = u"(%s)" % (header.author)
                    ## FIXME: ファイル名の表示は横長になりすぎるので保留
                    ##elif self.sort.GetSelection() == 3:
                    ##    # 整列条件: ファイル名
                    ##    fname = header.fname
                    ##    if sys.platform == "win32" and fname.lower().endswith(".lnk"):
                    ##        fname = os.path.splitext(fname)[0]
                    ##    addition = fname
                    elif self.sort.GetSelection() == 4:
                        # 整列条件: 更新日時
                        addition = u"[%s]" % (self._formatted_mtime(header.mtime, False))
                    elif header.levelmin or header.levelmax:
                        levelmin = str(header.levelmin) if header.levelmin else " "
                        levelmax = str(header.levelmax) if header.levelmax else " "
                        if levelmin == levelmax:
                            addition = u"[%s]" % (levelmin)
                        else:
                            addition = u"[%s～%s]" % (levelmin, levelmax)
                    if self.is_playing(header) or self.is_complete(header) or self.is_invisible(header):
                        dc.SetTextForeground((128, 128, 128))
                    else:
                        dc.SetTextForeground((0, 0, 0))
                else:
                    if isinstance(dpath, FindResult):
                        name = u"[%s]" % (os.path.basename(name))
                    dc.SetTextForeground((0, 0, 0))

                dc.SetFont(font)
                size = dc.GetTextExtent(name)
                space = cw.wins(3)
                if addition:
                    dc.SetFont(font2)
                    size2 = dc.GetTextExtent(addition)
                    x = (bmpw - (size[0]+space+size2[0])) / 2
                    x += cw.wins(10) # 左に寄って見えるので若干右寄りにする
                else:
                    x = (bmpw - size[0]) / 2

                dc.SetFont(font)
                dc.DrawText(name, x, y+yp)

                if addition:
                    dc.SetFont(font2)
                    dc.SetTextForeground((128, 128, 128))
                    x2 = x + space + size[0]
                    y2 = y + ((size[1] - size2[1]) / 2) + 1
                    dc.DrawText(addition, x2, y2+yp)

                y += cw.wins(15)

            self._enable_btn2(dpath, dc=dc)
        else:
            header = self.list[self.index]

            # 見出し画像
            wxbmps = header.get_wxbmps()
            for bmp, bmp_noscale, info in zip(wxbmps[0], wxbmps[1], header.imgpaths):
                # デフォルトは左上位置固定(CardWirthとの互換性維持)
                if info.postype == "Center":
                    bx = (bmpw-bmp.GetWidth()) // 2
                    by = (bmph-bmp.GetHeight()) // 2
                    cw.imageretouch.wxblit_2bitbmp_to_card(dc, bmp, bx, by+yp, True,
                                                           bitsizekey=bmp_noscale)
                else:
                    # info.postype in ("TopLeft", "Default")
                    cw.imageretouch.wxblit_2bitbmp_to_card(dc, bmp, cw.wins(163), cw.wins(70)+yp, True,
                                                           bitsizekey=bmp_noscale)

            # シナリオ名
            dc.SetFont(cw.cwpy.rsrc.get_wxfont("scenario", pixelsize=cw.wins(21)))
            s = header.name
            w = dc.GetTextExtent(s)[0]
            maxwidth = bmpw - cw.wins(5)*2
            if maxwidth < w:
                cw.util.draw_witharound(dc, s, cw.wins(5), cw.wins(35)+yp, maxwidth=maxwidth)
            else:
                cw.util.draw_witharound(dc, s, (bmpw-w)/2, cw.wins(35)+yp)

            # 解説文
            dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlglist", pixelsize=cw.wins(14)))
            s = header.desc
            y = cw.wins(180)
            for l in s.splitlines():
                dc.DrawText(l, cw.wins(65), y+yp)
                y += cw.wins(15)
            # 対象レベル
            dc.SetTextForeground(wx.Colour(0, 128, 128, 255))
            dc.SetFont(cw.cwpy.rsrc.get_wxfont("targetlevel",
                                            style=wx.FONTSTYLE_ITALIC, pixelsize=cw.wins(16)))
            levelmax = str(header.levelmax) if header.levelmax else ""
            levelmin = str(header.levelmin) if header.levelmin else ""

            if levelmax or levelmin:
                if levelmin == levelmax:
                    s = cw.cwpy.msgs["target_level_1"] % (levelmin)
                else:
                    s = cw.cwpy.msgs["target_level_2"] % (levelmin, levelmax)

                w = dc.GetTextExtent(s)[0]
                dc.DrawText(s, (bmpw-w)/2, cw.wins(15)+yp)

            self._enable_btn2(header, dc=dc)

        # ページ数を表示
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgtitle", pixelsize=cw.wins(15)))
        s = str(self.index+1) if self.list else str(0)
        s = s + "/" + str(len(self.list))
        w = dc.GetTextExtent(s)[0]
        cw.util.draw_witharound(dc, s, bmpw-w-cw.wins(190), cw.wins(340))

        if update:
            fc = wx.Window.FindFocus()
            if fc <> self.narrow:
                buttonlist = filter(lambda button: button.IsEnabled(), self.buttonlist)
                if buttonlist:
                    buttonlist[0].SetFocus()

    def _enable_btn2(self, header, dc=None):
        bmpw = self.toppanel.GetClientSize()[0]
        if isinstance(header, cw.header.ScenarioHeader):
            # 進行中チェック
            if self.is_playing(header):
                if dc:
                    bmp = cw.cwpy.rsrc.dialogs["PLAYING"]
                    w = bmp.GetSize()[0]
                    dc.DrawBitmap(bmp, (bmpw-w)/2, cw.wins(152), True)
            # 済み印存在チェック
            elif self.is_complete(header):
                if dc:
                    bmp = cw.cwpy.rsrc.dialogs["COMPLETE"]
                    w = bmp.GetSize()[0]
                    dc.DrawBitmap(bmp, (bmpw-w)/2, cw.wins(175), True)
            # クーポン存在チェック
            elif self.is_invisible(header):
                if dc:
                    bmp = cw.cwpy.rsrc.dialogs["INVISIBLE"]
                    w = bmp.GetSize()[0]
                    dc.DrawBitmap(bmp, (bmpw-w)/2, cw.wins(100), True)

    def is_playing(self, header):
        return header.get_fpath() in self.nowplayingpaths

    def is_complete(self, header):
        return header.name in self.stamps

    def is_invisible(self, header):
        if not header.coupons:
            return False

        num = 0

        for coupon in header.coupons.splitlines():
            if coupon:
                num += min(1, self.coupons.get(coupon, 0))

        return num < header.couponsnum

    def update_narrowcondition(self):
        if not self._update_narrowparams():
            return

        self._processing = True
        self._no_treechangedsound = True
        selected = self.list[self.index] if self.list else None
        if self.tree.IsShown():
            selitem = self.tree.GetSelection()
            if not selitem:
                self._processing = False
                return
            paritem = self.tree.GetItemParent(selitem)
            def recurse(parent):
                index, nowdir = self.tree.GetItemPyData(parent)
                nowdir = self._get_linktarget(nowdir)
                if not nowdir in self.scetable:
                    return

                item, cookie = self.tree.GetFirstChild(parent)
                delitems = []
                while item.IsOk():
                    data = self.tree.GetItemPyData(item)
                    if not data is None:
                        index, header = data
                        if isinstance(header, cw.header.ScenarioHeader):
                            delitems.append(item)
                        elif isinstance(header, FindResult) or self.tree.IsExpanded(item):
                            recurse(item)
                    item, cookie = self.tree.GetNextChild(parent, cookie)
                for item in delitems:
                    self.tree.Delete(item)

                for index, header in enumerate(self._narrow_scenario(self.scetable[nowdir])):
                    if isinstance(header, cw.header.ScenarioHeader):
                        item = self.create_treeitem(index, parent, header)
                        if isinstance(selected, cw.header.ScenarioHeader) and\
                                selected.dpath == header.dpath and selected.fname == header.fname:
                            self.tree.SelectItem(item)

            self.Freeze()
            self.tree.Hide()
            recurse(self.tree.root)
            self.tree.Show()
            self.Thaw()
            self.Layout()
            # スクロールしないほうが操作性がよい
            #item = self.tree.GetSelection()
            #if item and not self.tree.IsVisible(item):
            #    self.tree.ScrollTo(item)

        if self.toppanel.IsShown():
            self.list = self.scetable[self._get_linktarget(self.nowdir)]
            self.list = self._narrow_scenario(self.list)

        self._processing = False

        # 選択のやり直し
        if selected and selected in self.list:
            self.index = self.list.index(selected)
            if self.toppanel.IsShown():
                dc = wx.ClientDC(self.toppanel)
                dc = wx.BufferedDC(dc)
                self._draw_impl(False, dc)
        elif cw.cwpy.setting.show_paperandtree:
            self._tree_selchanged()
            self.draw(True)
        else:
            self.index = max(0, min(self.index, len(self.list)-1))
            if self.toppanel.IsShown():
                self.draw(True)

        self._update_saveddirstack()

    def create_treeitems(self, treeitem):
        # 再描画を抑止して軽くする
        # self.tree.Freeze()にはほとんど効果が認められなかったので
        # 予めツリーを閉じるようにする
        self.tree.Freeze()
        self.tree.Hide()

        self.tree.DeleteChildren(treeitem)
        index, nowdir = self.tree.GetItemPyData(treeitem)
        nowdir = self._get_linktarget(nowdir)
        itemlist = []
        dpaths = []

        if not nowdir in self.scetable:
            self.scetable[nowdir] = self._get_nowlist(nowdir, update=True)

        for index, header in enumerate(self._narrow_scenario(self.scetable[nowdir])):
            if isinstance(header, cw.header.ScenarioHeader):
                item = self.create_treeitem(index, treeitem, header)
                itemlist.append(item)
            elif isinstance(header, FindResult):
                item = self._create_findresultitem(index, treeitem, header)
                itemlist.append(item)
                dpaths.append("/find_result")
            else:
                dpath = header
                name = os.path.basename(dpath)
                image = self.tree.imgidx_dir
                if sys.platform == "win32" and name.lower().endswith(".lnk"):
                    name = cw.util.splitext(name)[0]
                item = self.tree.AppendItem(treeitem, name, image)
                self.tree.SetItemPyData(item, (index, dpath))
                child = self.tree.AppendItem(item, u"読込中...")
                self.tree.SetItemPyData(child, None)
                self.tree.Collapse(item)
                itemlist.append(item)
                dpaths.append(dpath)

        if not treeitem is self.tree.root:
            if treeitem.IsOk() and not self.tree.IsExpanded(treeitem):
                self.tree.Expand(treeitem)
        self.tree.Show()
        self.tree.Thaw()
        self.Layout()

        return itemlist, dpaths

    def _create_findresultitem(self, index, treeitem, findresult):
        image = self.tree.imgidx_findresult
        item = self.tree.InsertItemBefore(treeitem, index, cw.cwpy.msgs["find_result"], image)
        self.tree.SetItemPyData(item, (index, findresult))
        if findresult.headers:
            self.create_treeitems(item)
        else:
            child = self.tree.AppendItem(item, cw.cwpy.msgs["find_notfound"])
            self.tree.SetItemPyData(child, None)
        return item

    def _formatted_mtime(self, mtime, showtime):
        d = datetime.datetime.fromtimestamp(mtime)
        if showtime:
            return d.strftime("%Y-%m-%d %H:%M")
        else:
            return d.strftime("%Y-%m-%d")

    def create_treeitem(self, index, treeitem, header):
        name = header.name
        image = self.tree.imgidx_summary

        if self.is_playing(header):
            image = self.tree.imgidx_playing
        elif self.is_complete(header):
            image = self.tree.imgidx_complete
        elif self.is_invisible(header):
            image = self.tree.imgidx_invisible
        #一覧表示なら省略する
        if cw.cwpy.setting.show_paperandtree:
            name = u"%s" % (name)
        elif header.levelmin <> 0 or header.levelmax <> 0:
            if header.levelmin == header.levelmax:
                name = u"[    %2d] %s" % (header.levelmin, name)
            else:
                levelmin = str(header.levelmin) if header.levelmin else ""
                levelmax = str(header.levelmax) if header.levelmax else ""
                name = u"[%2s～%2s] %s" % (levelmin, levelmax, name)

        if self.sort.GetSelection() == 4:
            # 日時による整列中
            name = u"%s (%s)" % (name, self._formatted_mtime(header.mtime, True))
        elif self.sort.GetSelection() == 3:
            # ファイル名による整列中
            fname = header.fname
            if sys.platform == "win32" and fname.lower().endswith(".lnk"):
                fname = os.path.splitext(fname)[0]
            name = u"%s (%s)" % (name, fname)
        elif self.sort.GetSelection() == 2 and header.author:
            # 作者名による整列中
            name = u"%s (%s)" % (name, header.author)

        item = self.tree.AppendItem(treeitem, name, image)
        self.tree.SetItemPyData(item, (index, header))
        return item

    def show_tree(self):
        # ツリーを初期化する
        self.tree.DeleteChildren(self.tree.root)

        treeitem = self.tree.root
        itemlist = []
        dirstack = self.dirstack[:]
        while True:
            itemlist, dpaths = self.create_treeitems(treeitem)

            if dirstack:
                _pardir, selname = dirstack.pop(0)
                index = -1
                for i, dpath in enumerate(dpaths):
                    if dpath.startswith("/"):
                        if dpath == selname:
                            index = i
                            break
                    elif os.path.normcase(selname) == os.path.normcase(os.path.basename(dpath)):
                        index = i
                        break
                if index == -1:
                    break
                treeitem = itemlist[index]
                self.tree.DeleteChildren(treeitem)
            else:
                if itemlist:
                    treeitem = itemlist[self.index]
                    self.tree.SelectItem(treeitem)
                else:
                    if not treeitem is self.tree.root:
                        self.tree.SelectItem(treeitem)
                        self._tree_selchanged()

                # 検索結果ディレクトリを選択中であれば展開する
                data = self.tree.GetItemPyData(treeitem)
                if data and isinstance(data[1], FindResult):
                    self.tree.Expand(treeitem)
                break

    def OnTreeItemExpanded(self, event):
        if self._processing:
            return

        selitem = event.GetItem()
        self._expand_tree(selitem)

    def _expand_tree(self, selitem):
        data = self.tree.GetItemPyData(selitem)
        if data is None or isinstance(data[1], FindResult):
            return
        _index, dpath = data
        self._expandeditem(selitem, startdir=dpath, expandedset=set())

    def _expandeditem(self, selitem, startdir, expandedset):
        if not self.tree.IsShown():
            return
        if self._processing:
            return

        data = self.tree.GetItemPyData(selitem)
        if data and isinstance(data[1], FindResult):
            # 検索結果に対しては何もしない
            return

        item, _cookie = self.tree.GetFirstChild(selitem)
        data = self.tree.GetItemPyData(item)
        if not data is None:
            # 読込済み
            return

        _index, dpath = self.tree.GetItemPyData(selitem)
        ndpath = cw.util.get_linktarget(dpath)
        ndpath = os.path.abspath(ndpath)
        ndpath = os.path.normpath(ndpath)
        ndpath = os.path.normcase(ndpath)
        if ndpath in expandedset:
            return
        expandedset.add(ndpath)

        if self.updatenames_thr:
            self.updatenames_thr.quit = True
            self.updatenames_thr = None
        if self.nowdir == dpath:
            self.names = [u"読込中..."]
        paritem = self.tree.GetItemParent(selitem)
        dirstack = self.get_dirstack(paritem)
        self.updatenames_thr = UpdateNamesThread(self, dpath, dpath, dirstack,
                                                 startdir=startdir, expandedset=expandedset,
                                                 skintype=cw.cwpy.setting.skintype)
        self.updatenames_thr.start()

    def OnTreeItemCollapsed(self, event):
        if not self.tree.IsShown():
            return
        item = event.GetItem()
        self._collapse_tree(item)

    def _collapse_tree(self, item):
        # 一旦リストをクリアして次に開いた時に再読込を行う
        data = self.tree.GetItemPyData(item)
        if data and isinstance(data[1], FindResult):
            # 検索結果はクリアしない
            return
        nowdir = self._get_linktarget(data[1])
        if not nowdir in self.scetable:
            self.tree.Collapse(item)
            return
        del self.scetable[nowdir]
        self.tree.DeleteChildren(item)
        child = self.tree.AppendItem(item, u"読込中...")
        self.tree.SetItemPyData(child, None)
        self.tree.Collapse(item)

    def OnTreeSelChanged(self, event):
        if self._processing:
            return
        if not self or not self.tree:
            return
        if not (self.tree.IsShown() and self.tree.IsShownOnScreen()):
            return
        self._tree_selchanged()

        if cw.cwpy.setting.show_paperandtree:
            if not self._no_treechangedsound:
                cw.cwpy.play_sound("page")
            self.draw(True)

    def _tree_selchanged(self):
        selitem = self.tree.GetSelection()
        if not selitem:
            return
        paritem = self.tree.GetItemParent(selitem)

        if self.tree.GetItemPyData(selitem) is None:
            # "読込中..."なので一つ上の階層を選択
            selitem = paritem
            paritem = self.tree.GetItemParent(selitem)
        if not paritem:
            return

        _index, self.nowdir = self.tree.GetItemPyData(paritem)
        self.index, _pathorheader = self.tree.GetItemPyData(selitem)

        self.list = self._get_nowlist(update=False)
        self.scetable[self._get_linktarget(self.nowdir)] = self.list
        self.list = self._narrow_scenario(self.list)

        self.dirstack = self.get_dirstack(paritem)
        self._update_saveddirstack()
        self.enable_btn()

    def get_dirstack(self, paritem):
        dirstack = []
        while paritem:
            _i, parpath = self.tree.GetItemPyData(paritem)
            _i, selpath = self.tree.GetItemPyData(paritem)
            if isinstance(parpath, FindResult):
                parpath = self.scedir
            else:
                parpath = os.path.dirname(parpath)
            if isinstance(selpath, FindResult):
                selpath = "/find_result"
            else:
                selpath = os.path.basename(selpath)
            dirstack.insert(0, (parpath, selpath))

            paritem = self.tree.GetItemParent(paritem)
        return dirstack[1:]

    def select_treeitem(self, index):
        item = self.tree.GetSelection()
        if not item:
            return
        paritem = self.tree.GetItemParent(item)
        item, cookie = self.tree.GetFirstChild(paritem)
        i = 0
        while item.IsOk():
            if i == index:
                self.tree.SelectItem(item)
                self.index = index
                break
            item, cookie = self.tree.GetNextChild(paritem, cookie)
            i += 1

    def updated_names(self, dpath, dirstack, startdir, expandedset):
        if self.toppanel.IsShown():
            self.Refresh()

        if not self.tree.IsShown():
            return

        if not self.tree.IsShownOnScreen():
            return

        # dpathからツリーアイテムを検索
        parent = self.tree.root
        item = None
        dirstack.append(("", dpath))
        while dirstack:
            paritem = parent
            item, cookie = self.tree.GetFirstChild(paritem)
            if not item.IsOk():
                break

            parent = None
            while item.IsOk():
                _i, data = self.tree.GetItemPyData(item)
                if not data:
                    break
                if isinstance(data, (cw.header.ScenarioHeader, FindResult)):
                    if dirstack[0][1] == "/find_result":
                        parent = item
                        dirstack.pop(0)
                        break
                else:
                    name = os.path.normcase(os.path.basename(data))
                    if name == os.path.normcase(os.path.basename(dirstack[0][1])):
                        parent = item
                        dirstack.pop(0)
                        break
                item, cookie = self.tree.GetNextChild(paritem, cookie)

            if not parent:
                break

        if item and item.IsOk() and self.tree.IsExpanded(item):
            # ディレクトリの内容を表示
            self.create_treeitems(item)

        # 次のディレクトリを展開する
        ##baseitem = item
        ##
        ##def expand(item):
        ##    data = self.tree.GetItemPyData(item)
        ##    if not data is None:
        ##        index, header = data
        ##        if not isinstance(header, (cw.header.ScenarioHeader, FindResult)):
        ##            ndpath = cw.util.get_linktarget(header)
        ##            ndpath = os.path.abspath(ndpath)
        ##            ndpath = os.path.normpath(ndpath)
        ##            ndpath = os.path.normcase(ndpath)
        ##            if ndpath in expandedset:
        ##                return False
        ##
        ##            processing = self._processing
        ##            self._processing = True
        ##            self.tree.Expand(item)
        ##            self._processing = processing
        ##            self._expandeditem(item, startdir, expandedset)
        ##            return True
        ##    return False
        ##
        ### サブディレクトリを優先して展開
        ##item, cookie = self.tree.GetFirstChild(baseitem)
        ##while item.IsOk():
        ##    if expand(item):
        ##        return
        ##    item, cookie = self.tree.GetNextChild(item, cookie)
        ##
        ### サブディレクトリがない場合は次のアイテムを選択
        ### それもない場合は上位ディレクトリへ遡る
        ##while baseitem and baseitem.IsOk():
        ##    data = self.tree.GetItemPyData(baseitem)
        ##    if data and data[1] == startdir:
        ##        return
        ##
        ##    item = self.tree.GetNextSibling(baseitem)
        ##    if item and item.IsOk():
        ##        if expand(item):
        ##            return
        ##    # 一つ上へ辿って次のフォルダを探す
        ##    baseitem = self.tree.GetItemParent(baseitem)

    def _narrow_scenario(self, headers):
        """設定に応じて表示しないシナリオを除去する。"""
        ntype, narrow, donarrow, level, _unfitness, _complete, _invisible, _sort = self._get_narrowparams()
        dseq = []
        seq = []
        for header in headers:
            if not self._is_showing(header, ntype, narrow, donarrow, level):
                continue
            if isinstance(header, cw.header.ScenarioHeader):
                seq.append(header)
            else:
                dseq.append(header)

        return dseq + self._sort_headers(seq)

    def _update_narrowparams(self):
        t = self._get_narrowparams()
        if t == self._last_narrowparams:
            return False
        else:
            self._last_narrowparams = t
            return True

    def is_showing(self, header):
        ntype, narrow, donarrow, level, _unfitness, _complete, _invisible, _sort = self._get_narrowparams()
        return self._is_showing(header, ntype, narrow, donarrow, level)

    def _get_narrowparams(self):
        if cw.cwpy.setting.show_unfitnessscenario:
            level = 0
        else:
            pcards = cw.cwpy.get_pcards("unreversed")
            level = sum([pcard.level for pcard in pcards]) / len(pcards)

        narrow = self.narrow.GetValue().lower()
        donarrow = bool(narrow) and self.narrow.IsShown()
        ntype = self.narrow_type.GetSelection()
        if ntype == 3 and donarrow:
            # レベル
            try:
                narrow = int(narrow)
            except:
                narrow = ""
        return ntype, narrow, donarrow, level, cw.cwpy.setting.show_unfitnessscenario,\
               cw.cwpy.setting.show_completedscenario, cw.cwpy.setting.show_invisiblescenario, \
               self.sort.GetSelection()

    def _is_showing(self, header, ntype, narrow, donarrow, level):
        if isinstance(header, cw.header.ScenarioHeader):
            if not cw.cwpy.setting.show_unfitnessscenario and not (ntype == 3 and donarrow) and\
                    ((header.levelmin <> 0 and level < header.levelmin) or\
                     (header.levelmax <> 0 and header.levelmax < level)):
                return False
            if not cw.cwpy.setting.show_completedscenario and self.is_complete(header):
                return False
            if not cw.cwpy.setting.show_invisiblescenario and self.is_invisible(header):
                return False

            if donarrow:
                if ntype == 0:
                    # タイトルで絞り込み
                    if not narrow in header.name.lower():
                        return False
                elif ntype == 1:
                    # 解説で絞り込み
                    if not narrow in header.desc.lower():
                        return False
                elif ntype == 2:
                    # 作者名で絞り込み
                    if not narrow in header.author.lower():
                        return False
                elif ntype == 3:
                    # 対象レベルで絞り込み
                    if not (header.levelmin <= narrow <= header.levelmax):
                        return False
                elif ntype == 4:
                    # ファイル名で絞り込み
                    if not narrow in header.fname.lower():
                        return False
                else:
                    assert False
        return True

    def _sort_headers(self, seq):
        sort = self.sort.GetSelection()
        if sort == 0:
            # 対象レベル。最初からソート済み
            pass
        elif sort == 1:
            # タイトル
            cw.util.sort_by_attr(seq, "name", "levelmin", "levelmax", "author", "fname", "mtime_reversed")
        elif sort == 2:
            # 作者名
            cw.util.sort_by_attr(seq, "author", "levelmin", "levelmax", "name", "fname", "mtime_reversed")
        elif sort == 3:
            # ファイル名
            cw.util.sort_by_attr(seq, "fname", "levelmin", "levelmax", "name", "author", "mtime_reversed")
        elif sort == 4:
            # 更新日時
            cw.util.sort_by_attr(seq, "mtime_reversed", "levelmin", "levelmax", "name", "author", "fname")
        return seq

    def enable_btn(self):
        if self._processing:
            return

        self.opendirbtn.Enable(self._can_opendir())
        if self.editorbtn:
            self.editorbtn.Enable(self._can_editor())

        # リストが空だったらボタンを無効化
        if not self.list:
            self.yesbtn.Enable(False)
            self.infobtn.Enable(False)
            if self.viewbtn:
                self.viewbtn.Enable()
            self.nobtn.Enable()
            self.rightbtn.Disable()
            self.right2btn.Disable()
            self.leftbtn.Disable()
            self.left2btn.Disable()
            self.SetTitle(cw.cwpy.msgs["select_scenario_title"])
            return

        self.texts = self.get_texts()
        if len(self.list) == 1:
            self.infobtn.Enable(bool(self.texts))
            if self.viewbtn:
                self.viewbtn.Enable()
            self.nobtn.Enable()
            self.rightbtn.Disable()
            self.right2btn.Disable()
            self.leftbtn.Disable()
            self.left2btn.Disable()
        else:
            self.infobtn.Enable(bool(self.texts))
            if self.viewbtn:
                self.viewbtn.Enable()
            self.nobtn.Enable()
            self.rightbtn.Enable()
            self.right2btn.Enable()
            self.leftbtn.Enable()
            self.left2btn.Enable()

        selected = self.list[self.index]

        # 状況によってボタンのテキストを更新
        if self.viewbtn:
            if self.tree.IsShown():
                self.viewbtn.SetLabel(cw.cwpy.msgs["scenario_one"])
            else:
                self.viewbtn.SetLabel(cw.cwpy.msgs["scenario_tree"])

        if not self.list or isinstance(selected, cw.header.ScenarioHeader) or not self.toppanel.IsShown():
            self.yesbtn.SetLabel(cw.cwpy.msgs["decide"])
        else:
            self.yesbtn.SetLabel(cw.cwpy.msgs["see"])

        if self.dirstack and not self.tree.IsShown():
            self.nobtn.SetLabel(cw.cwpy.msgs["return"])
        else:
            self.nobtn.SetLabel(cw.cwpy.msgs["entry_cancel"])

        enable = True
        if not self.list:
            enable = False
        elif isinstance(selected, cw.header.ScenarioHeader):
            # 進行中チェック
            if self.is_playing(selected):
                if not cw.cwpy.debug:
                    enable = False
            # 済み印存在チェック
            elif self.is_complete(selected):
                if not cw.cwpy.debug:
                    enable = False
            # クーポン存在チェック
            elif self.is_invisible(selected):
                if not cw.cwpy.debug:
                    enable = False
        elif isinstance(selected, FindResult):
            if self.tree.IsShown():
                enable = False
        else:
            dpath = selected
            if not self.toppanel.IsShown() or not os.path.isdir(cw.util.get_linktarget(dpath)):
                enable = False
        self.yesbtn.Enable(enable)

        # 選択中のファイル名またはディレクトリ名を表示
        if isinstance(selected, cw.header.ScenarioHeader):
            fname = selected.fname
            author = selected.author
        elif isinstance(selected, FindResult):
            fname = cw.cwpy.msgs["find_result"]
            author = ""
        else:
            fname = os.path.basename(selected)
            author = ""
        if sys.platform == "win32" and cw.util.splitext(fname)[1].lower() == ".lnk":
            fname = cw.util.splitext(fname)[0]
        name = u"貼紙を見る [ %s ]" % (fname)
        if author:
            name = u"%s (%s)" % (name, author)
        self.SetTitle(name)

    def get_dpaths(self, dpath):
        """
        クラシックなシナリオ以外のフォルダの一覧を返す。
        (ショートカット類も含む)
        """
        seq = []

        try:
            dpath2 = cw.util.get_linktarget(dpath)
            if os.path.isdir(dpath2):
                for dname in os.listdir(dpath2):
                    path = cw.util.join_paths(dpath2, dname)
                    if self.is_listitem(path) and not self.is_scenario(path):
                        seq.append(path)
        except Exception:
            cw.util.print_ex()

        cw.util.sort_by_attr(seq)
        return seq

    def is_listitem(self, path):
        """
        指定されたパスが選択可能ならTrueを返す。
        """
        path = cw.util.get_linktarget(path)
        return os.path.isdir(path) or self.is_scenario(path)

    def is_scenario(self, path):
        """
        指定されたパスがシナリオならTrueを返す。
        """
        return cw.scenariodb.is_scenario(path)

    def get_texts(self):
        """
        選択中シナリオに同梱されている
        テキストファイルのファイル名とデータのリストを返す。
        """
        if not self.list:
            return []

        seq = []
        if isinstance(self.list[self.index], cw.header.ScenarioHeader):
            header = self.list[self.index]
            path = header.get_fpath()
            path = cw.util.get_linktarget(path)
            if os.path.isfile(path):
                # 圧縮ファイル内から取得
                if path.lower().endswith(".cab"):
                    dpath = cw.util.join_paths(cw.tempdir, u"Cab")
                    if not os.path.isdir(dpath):
                        os.makedirs(dpath)
                    s = "expand \"%s\" -f:%s \"%s\"" % (path, "*.txt", dpath)
                    try:
                        encoding = sys.getfilesystemencoding()
                        if subprocess.call(s.encode(encoding), shell=True) == 0:
                            for dpath2, _dnames, fnames in os.walk(dpath):
                                for fname in fnames:
                                    fname = cw.util.decode_zipname(fname)
                                    if fname.lower().endswith(".txt"):
                                        dpath2 = cw.util.decode_zipname(dpath2)
                                        fpath = cw.util.join_paths(dpath2, fname)
                                        if os.path.isfile(fpath):
                                            cw.util.add_winauth(fpath)
                                            with open(fpath, "rb") as f:
                                                content = f.read()
                                                f.close()
                                            seq.append(text.ReadmeData(fname, content))
                    finally:
                        for fpath in os.listdir(dpath):
                            fpath = cw.util.decode_zipname(fpath)
                            fpath = cw.util.join_paths(dpath, fpath)
                            cw.util.remove(fpath)

                else:
                    with cw.util.zip_file(path, "r") as z:
                        names = [name for name in z.namelist() if name.lower().endswith(".txt")]

                        for name in names:
                            data = z.read(name)
                            name = os.path.basename(name)
                            name = cw.util.decode_zipname(name)
                            seq.append(text.ReadmeData(name, data))
                        z.close()

            elif os.path.isdir(path):

                # フォルダ内から取得
                paths = []
                for dpath, _dnames, fnames in os.walk(path):
                    for fname in fnames:
                        if fname.lower().endswith(".txt"):
                            fpath = cw.util.join_paths(dpath, fname)
                            if os.path.isfile(fpath):
                                paths.append(fpath)

                for fpath in paths:
                    with open(fpath, "rb") as f:
                        data = f.read()
                        f.close()
                    name = cw.util.relpath(fpath, path)
                    name = cw.util.join_paths(name)
                    seq.append(text.ReadmeData(name, data))

        elif not isinstance(self.list[self.index], FindResult):
            dpath = cw.util.get_linktarget(self.list[self.index])
            if os.path.isdir(dpath):
                for fname in os.listdir(dpath):
                    if os.path.splitext(fname)[1].lower().endswith(".txt"):
                        fpath = cw.util.join_paths(dpath, fname)
                        with open(fpath, "rb") as f:
                            data = f.read()
                            f.close()
                        seq.append(text.ReadmeData(fname, data))

        return seq

    def conv_scenario(self, path):
        """
        CardWirthのシナリオデータを変換。
        """
        # CardWirthのシナリオデータか確認
        if not os.path.isfile(cw.util.join_paths(path, "Summary.wsm")):

            s = u"カードワースのシナリオのディレクトリではありません。"
            dlg = message.ErrorMessage(self, s)
            self.Parent.move_dlg(dlg)
            dlg.ShowModal()
            dlg.Destroy()
            return

        # 変換確認ダイアログ
        cw.cwpy.play_sound("click")
        s = u"「" + os.path.basename(path) + u"」を変換します。\nよろしいですか？"
        dlg = message.YesNoMessage(self, cw.cwpy.msgs["message"], s)
        self.Parent.move_dlg(dlg)

        if not dlg.ShowModal() == wx.ID_OK:
            dlg.Destroy()
            return

        dlg.Destroy()
        # シナリオデータ
        cwdata = cw.binary.cwscenario.CWScenario(
            path, cw.util.join_paths(cw.tempdir, u"OldScenario"), cw.cwpy.setting.skintype,
            materialdir="Material", image_export=True)

        # 変換可能なデータか確認
        if not cwdata.is_convertible():
            s = u"CardWirth ver1.20以上対応の\nシナリオしか変換できません。"
            dlg = message.ErrorMessage(self, s)
            self.Parent.move_dlg(dlg)
            dlg.ShowModal()
            dlg.Destroy()
            return

        # シナリオデータ読み込み
        cwdata.load()

        thread = cw.binary.ConvertingThread(cwdata)
        thread.start()

        # プログレスダイアログ表示
        dlg = cw.dialog.progress.ProgressDialog(self,
            cwdata.name + u"の変換", "", maximum=cwdata.maxnum+2)

        zpaths = [""]
        def progress():
            while not thread.complete:
                wx.CallAfter(dlg.Update, cwdata.curnum, cwdata.message)
                time.sleep(0.001)
            wx.CallAfter(dlg.Update, cwdata.curnum+1, u"シナリオを圧縮しています...")
            # zip圧縮
            temppath = thread.path
            zpath = os.path.basename(temppath) + ".wsn"
            zpath = cw.util.join_paths(self.nowdir, zpath)
            zpath = cw.util.dupcheck_plus(zpath, False)
            cw.util.compress_zip(temppath, zpath, unicodefilename=True)
            # tempを削除
            wx.CallAfter(dlg.Update, cwdata.curnum+2, u"一時フォルダを削除しています...")
            cw.util.remove(temppath)
            zpaths[0] = zpath
            wx.CallAfter(dlg.Destroy)
        thread2 = threading.Thread(target=progress)
        thread2.start()
        self.Parent.move_dlg(dlg)
        dlg.ShowModal()
        zpath = zpaths[0]

        # エラーログ表示
        if cwdata.errorlog:
            dlg = cw.dialog.etc.ErrorLogDialog(self, cwdata.errorlog)
            self.Parent.move_dlg(dlg)
            dlg.ShowModal()
            dlg.Destroy()

        cw.cwpy.play_sound("harvest")
        # 変換完了ダイアログ
        s = u"データの変換が完了しました。"
        dlg = message.Message(self, cw.cwpy.msgs["message"], s, mode=2)
        self.Parent.move_dlg(dlg)
        dlg.ShowModal()
        dlg.Destroy()
        # 更新処理
        self.db.insert_scenario(zpath, skintype=cw.cwpy.setting.skintype)
        self.list = self._get_nowlist(update=True)
        self.scetable[self._get_linktarget(self.nowdir)] = self.list
        self.list = self._narrow_scenario(self.list)
        self.index = 0

        # 変換したシナリオのインデックスを取得
        header = None
        for index, lheader in enumerate(self.list):
            if not hasattr(lheader, "fname"):
                continue

            if os.path.basename(zpath) == lheader.fname:
                self.index = index
                header = lheader
                break

        # ツリー表示中の場合は追加
        if self.tree.IsShown() and header:
            name = header.name
            image = self.tree.imgidx_summary
            if self.is_playing(header):
                image = self.tree.imgidx_playing
            elif self.is_complete(header):
                image = self.tree.imgidx_complete
            elif self.is_invisible(header):
                image = self.tree.imgidx_invisible
            parent = self.tree.GetSelection()
            prev = None
            i = 0
            item, cookie = self.tree.GetFirstChild(parent)
            while item.IsOk():
                if i == self.index:
                    prev = item
                    break
                item, cookie = self.tree.GetNextChild(item, cookie)
                i += 1
            if prev:
                item = self.tree.InsertItem(parent, prev, name, image)
            else:
                item = self.tree.AppendItem(parent, name, image)
            self.tree.SelectItem(item)
            self.tree.SetItemPyData(item, (self.index, header))

        cw.cwpy.play_sound("page")
        self.draw(True)
        self.enable_btn()

    def OnOk(self, event):
        if not self.list:
            return

        if self._quit:
            return
        self._quit = True

        self.Enable(False)
        self.Show(False)
        cw.cwpy.frame.ok_scenarioselect(self)

    def OnCancel2(self, event):
        if self._quit:
            return
        self._quit = True

        # キャンセルしても最後の選択は記憶する
        cw.cwpy.setting.lastscenario, cw.cwpy.setting.lastscenariopath = self.get_selected()
        cw.cwpy.frame.kill_dlg(None)
        cw.cwpy.frame.append_killlist(self)


class FindResult(object):
    def __init__(self):
        self.headers = []


class UpdateNamesThread(threading.Thread):

    def __init__(self, dlg, nowdir, dpath, dirstack, startdir, expandedset, skintype):
        threading.Thread.__init__(self)
        self.dlg = dlg
        self.nowdir = nowdir
        self.dpath = dpath
        self.dirstack = dirstack
        self.dpaths = dlg.get_dpaths(dpath)
        self.quit = False
        self.startdir = startdir
        self.expandedset = expandedset
        self.skintype = skintype

    def run(self):
        """ScenarioSelectで現在表示中のディレクトリ内の
        シナリオ・ディレクトリのリストを生成する。
        """
        self._start()

    @synclock(_lockupdatescenario)
    def _start(self):
        if self.quit: return
        # dpathの中にあるシナリオをDBに登録
        db = cw.scenariodb.Scenariodb()
        db.update(self.dpath, skintype=self.skintype)
        if self.quit: return
        # dpathの中にあるシナリオ名のリスト
        headers = db.search_dpath(self.dpath, skintype=self.skintype)
        # dpathの中にあるディレクトリ名のリスト
        dnames = []

        if self.quit: return
        for path in self.dpaths:
            if path.lower().endswith(".lnk"):
                path = path[0:-len(".lnk")]
            dname = u"[%s]" % (os.path.basename(path))
            dnames.append(dname)
        def func():
            if self.dlg:
                if self.dlg.nowdir == self.nowdir:
                    self.dlg.names = dnames + headers
                if self.quit: return
                wx.CallAfter(self.dlg.updated_names, self.dpath, self.dirstack, self.startdir, self.expandedset)
                self.dlg.updatenames_thr = None
        cw.cwpy.frame.exec_func(func)

def main():
    pass

if __name__ == "__main__":
    main()
