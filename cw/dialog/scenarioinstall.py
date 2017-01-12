#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import threading
import time
import itertools
import wx

import cw

import message

#-------------------------------------------------------------------------------
#　シナリオインストールダイアログ
#-------------------------------------------------------------------------------

class ScenarioInstall(wx.Dialog):
    """
    シナリオインストールダイアログ。
    """
    def __init__(self, parent, db, headers, skintype, scedir):
        assert 0 < len(headers)

        # ダイアログボックス作成
        wx.Dialog.__init__(self, parent, -1, u"シナリオのインストール", size=cw.wins((420, 400)),
                            style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX|wx.RESIZE_BORDER)
        self.SetDoubleBuffered(True)
        self.db = db
        self.skintype = skintype
        self.headers = headers
        self.scedir = scedir

        # メッセージ
        if 1 < len(headers):
            self.text = u"%s本のシナリオの移動先を選択してください。" % (len(headers))
        else:
            name = headers[0].name
            if headers[0].author:
                name += u"(%s)" % headers[0].author
            self.text = u"「%s」の移動先を選択してください。" % (name)

        # フォルダの作成
        bmp = cw.cwpy.rsrc.dialogs["DIRECTORY"]
        self.createdirbtn = cw.cwpy.rsrc.create_wxbutton(self, -1, (cw.wins(24), cw.wins(24)), bmp=bmp)
        self.createdirbtn.SetToolTip(wx.ToolTip(cw.cwpy.msgs["create_directory"]))

        # フォルダ選択用ツリー
        self.tree = wx.TreeCtrl(self, -1, size=(-1, -1),
            style=wx.BORDER|wx.TR_SINGLE|wx.TR_DEFAULT_STYLE)
        self.tree.SetFont(cw.cwpy.rsrc.get_wxfont("tree", pixelsize=cw.wins(15)-1))
        self.tree.SetDoubleBuffered(True)
        self.tree.imglist = wx.ImageList(cw.wins(16), cw.wins(16))
        self.tree.imgidx_dir = self.tree.imglist.Add(cw.cwpy.rsrc.dialogs["DIRECTORY"])
        name = os.path.basename(scedir)
        if sys.platform == "win32" and name.lower().endswith(".lnk"):
            name = cw.util.splitext(name)[0]
        self.tree.root = self.tree.AddRoot(name, self.tree.imgidx_dir)
        self.tree.SetItemPyData(self.tree.root, scedir)
        self.tree.SetImageList(self.tree.imglist)
        self.tree.SelectItem(self.tree.root)

        # 前回の選択を復元する
        dirstack = cw.cwpy.setting.installed_dir.get(scedir, [])
        if not dirstack and os.path.normcase("A") == os.path.normcase("a"):
            # 大文字・小文字を区別しないファイルシステム
            for key, value in cw.cwpy.setting.installed_dir.iteritems():
                if os.path.normcase(key) == os.path.normcase(scedir):
                    dirstack = value
                    break
        self._create_treeitems(self.tree.root, dirstack)
        self.tree.Expand(self.tree.root)

        # インストール・キャンセルボタン
        self.yesbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_OK, cw.wins((120, 30)), u"インストール")
        self.yesbtn.SetToolTipString(create_installdesc(headers))
        self.nobtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL, cw.wins((120, 30)), cw.cwpy.msgs["cancel"])
        self.buttons = (self.yesbtn, self.nobtn)

        # layout
        self._resize()
        self._do_layout()
        # bind
        self.tree.Bind(wx.EVT_TREE_ITEM_EXPANDED, self.OnTreeItemExpanded)
        self.tree.Bind(wx.EVT_TREE_ITEM_COLLAPSED, self.OnTreeItemCollapsed)
        self.createdirbtn.Bind(wx.EVT_BUTTON, self.OnCreateDirBtn)
        self.yesbtn.Bind(wx.EVT_BUTTON, self.OnInstallBtn)
        self.nobtn.Bind(wx.EVT_BUTTON, self.OnCancel)

        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        for child in self.GetChildren():
            child.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)

    def _do_layout(self):
        sizer_1 = wx.BoxSizer(wx.VERTICAL)

        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2.AddStretchSpacer(1)
        sizer_2.Add((cw.wins(0), self._textheight + cw.wins(24)), 0, 0, 0)
        sizer_2.Add(self.createdirbtn, 0, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER, cw.wins(10))
        sizer_1.Add(sizer_2, 0, wx.EXPAND, wx.LEFT|wx.RIGHT, cw.wins(10))

        sizer_1.Add(self.tree, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, cw.wins(8))

        sizer_3 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_3.AddStretchSpacer(1)
        for i, button in enumerate(self.buttons):
            sizer_3.Add(button, 0, 0, 0)
            sizer_3.AddStretchSpacer(1)

        sizer_1.Add(sizer_3, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, cw.wins(12))

        self.SetSizer(sizer_1)
        self.Layout()

    def _create_treeitems(self, treeitem, dirstack=[]):
        """treeitemが示すディレクトリのサブディレクトリを読み込む。
        シナリオフォルダは除外される。
        """
        self.tree.Freeze()
        self.tree.DeleteChildren(treeitem)
        dpath = self.tree.GetItemPyData(treeitem)

        for dir in get_dpaths(dpath):
            name = os.path.basename(dir)
            image = self.tree.imgidx_dir
            if sys.platform == "win32" and name.lower().endswith(".lnk"):
                name = cw.util.splitext(name)[0]
            item = self.tree.AppendItem(treeitem, name, image)
            self.tree.SetItemPyData(item, dir)
            if dirstack and os.path.normcase(os.path.basename(dir)) == os.path.normcase(dirstack[0]):
                if 1 < len(dirstack):
                    self._create_treeitems(item, dirstack[1:])
                    self.tree.Expand(item)
                    continue
                self.tree.SelectItem(item)
            self.tree.AppendItem(item, u"読込中...")
        self.tree.Thaw()

    def OnTreeItemExpanded(self, event):
        selitem = event.GetItem()
        self._create_treeitems(selitem)

    def OnTreeItemCollapsed(self, event):
        if not self.tree.IsShown():
            return
        item = event.GetItem()
        self.tree.DeleteChildren(item)
        self.tree.AppendItem(item, u"読込中...")

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

    def OnResize(self, event):
        if not self.tree.IsShown():
            return

        self._resize()

        self._do_layout()
        self.Refresh()

    def _resize(self):
        """
        テキストの折り返し位置を計算する。
        """
        dc = wx.ClientDC(self)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(15)))
        csize = self.GetClientSize()
        btnw = self.createdirbtn.GetSize()[0]
        self._wrapped_text = cw.util.wordwrap(self.text, csize[0]-cw.wins(20)-btnw-cw.wins(10), lambda s: dc.GetTextExtent(s)[0])
        _w, self._textheight, _lineheight = dc.GetMultiLineTextExtent(self._wrapped_text)

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)
        # massage
        dc.SetTextForeground(wx.BLACK)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(15)))
        dc.DrawLabel(self._wrapped_text, (cw.wins(10), cw.wins(12), csize[0], self._textheight), wx.ALIGN_LEFT)

    def OnCreateDirBtn(self, event):
        selitem = self.tree.GetSelection()
        if not selitem.IsOk():
            return
        dpath = self.tree.GetItemPyData(selitem)
        if not dpath:
            return

        dpath = create_dir(self, dpath)
        if dpath:
            cw.cwpy.play_sound("harvest")
            self._create_treeitems(selitem)
            self.tree.Expand(selitem)
            dpath = os.path.abspath(dpath)
            dpath = os.path.normpath(dpath)
            dpath = os.path.normcase(dpath)

            item, cookie = self.tree.GetFirstChild(selitem)
            while item.IsOk():
                dpath2 = self.tree.GetItemPyData(item)
                dpath2 = os.path.abspath(dpath2)
                dpath2 = os.path.normpath(dpath2)
                dpath2 = os.path.normcase(dpath2)
                if dpath == dpath2:
                    self.tree.SelectItem(item)
                    if not self.tree.IsVisible(item):
                        self.tree.ScrollTo(item)
                    break

                item, cookie = self.tree.GetNextChild(selitem, cookie)

    def OnInstallBtn(self, event):
        selitem = self.tree.GetSelection()
        if not selitem.IsOk():
            return
        dstpath = self.tree.GetItemPyData(selitem)
        if not dstpath:
            return

        failed, paths, cancelled = install_scenario(self, self.headers, dstpath, self.db, self.skintype)

        if paths:
            if 1 < len(paths):
                s = u"%s本のシナリオをインストールしました。" % (len(paths))
            else:
                header = self.db.search_path(paths[0])
                if not header:
                    return
                name = header.name
                if header.author:
                    name += u"(%s)" % header.author
                s = u"「%s」をインストールしました。" % (name)

            cw.cwpy.play_sound("harvest")
            dlg = message.Message(self, cw.cwpy.msgs["message"], s, mode=2)
            self.Parent.move_dlg(dlg)
            ret = dlg.ShowModal()
            dlg.Destroy()

        if cancelled:
            return

        cw.cwpy.setting.installed_dir[self.scedir] = self.get_dirstack(selitem)

        self.Close()

    def get_dirstack(self, paritem):
        """指定されたアイテムまでの経路を返す。
        """
        dirstack = []
        while paritem and paritem.IsOk():
            selpath = self.tree.GetItemPyData(paritem)
            selpath = os.path.basename(selpath)
            dirstack.append(selpath)
            paritem = self.tree.GetItemParent(paritem)

        dirstack.reverse()
        return dirstack[1:]


def get_dpaths(dpath):
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
                if is_listitem(path) and not cw.scenariodb.is_scenario(path):
                    seq.append(path)
    except Exception:
        cw.util.print_ex()

    cw.util.sort_by_attr(seq)
    return seq


def is_listitem(path):
    """
    指定されたパスがシナリオ選択ダイアログで選択可能ならTrueを返す。
    """
    path = cw.util.get_linktarget(path)
    return os.path.isdir(path) or cw.scenariodb.is_scenario(path)


def to_scenarioheaders(paths, db, skintype):
    """
    pathsをcw.header.ScenarioHeaderに変換する。
    パスがシナリオか否かの判定にシナリオDBを使用する。
    """
    headers = []

    for path in paths:
        def recurse(path):
            if cw.scenariodb.is_scenario(path):
                header = db.search_path(path, skintype=skintype)
                if header:
                    headers.append(header)
            elif os.path.isdir(path):
                for fname in os.listdir(path):
                    recurse(cw.util.join_paths(path, fname))

        recurse(path)

    return headers


def create_dir(parentdialog, dpath):
    cw.cwpy.play_sound("signal")
    name = os.path.basename(dpath)
    if sys.platform == "win32" and name.lower().endswith(".lnk"):
        name = cw.util.splitext(name)[0]
    dpath = cw.util.get_linktarget(dpath)

    s = u"%sに作成する新しいフォルダの名前を入力してください。" % (name)
    dname = cw.util.join_paths(dpath, u"新規フォルダ")
    dname = cw.util.dupcheck_plus(dname, yado=False)
    dname = os.path.basename(dname)
    dlg = cw.dialog.edit.InputTextDialog(parentdialog, u"新規フォルダ",
                                         msg=s,
                                         text=dname)
    cw.cwpy.frame.move_dlg(dlg)
    if dlg.ShowModal() == wx.ID_OK:
        dpath = cw.util.join_paths(dpath, dlg.text)
        dpath = cw.util.dupcheck_plus(dpath, yado=False)
        os.makedirs(dpath)
        return dpath
    else:
        return u""


def install_scenario(parentdialog, headers, dstpath, db, skintype):
    """
    headersをインストールする。
    進捗ダイアログが表示される。
    """
    dstpath = cw.util.get_linktarget(dstpath)

    # インストール済みの情報が見つかったシナリオ
    db_exists = {}

    for header in headers:
        header2 = db.find_scenario(header.name, header.author, skintype=skintype,
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
        dlg = message.YesNoCancelMessage(parentdialog, cw.cwpy.msgs["message"], s)
        cw.cwpy.frame.move_dlg(dlg)
        ret = dlg.ShowModal()
        dlg.Destroy()
        if ret == wx.ID_CANCEL:
            return True, [], True
        elif ret <> wx.ID_YES:
            db_exists.clear()

    # プログレスダイアログ表示
    dlg = cw.dialog.progress.ProgressDialog(parentdialog, u"シナリオのインストール",
                                            "", maximum=len(headers), cancelable=True)

    class InstallThread(threading.Thread):
        def __init__(self, headers, dstpath, db_exists):
            threading.Thread.__init__(self)
            self.headers = headers
            self.dstpath = dstpath
            self.db_exists = db_exists
            self.num = 0
            self.msg = u""
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

                                def func():
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
                                    ret = cw.cwpy.frame.sync_exec(func)
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

                    if os.path.normcase(os.path.normpath(os.path.abspath(fpath))) <> \
                            os.path.normcase(os.path.normpath(os.path.abspath(dst))):
                        if rmpath:
                            cw.util.remove(rmpath, trashbox=True)
                        try:
                            shutil.move(fpath, dst)
                        except:
                            # FIXME: フォルダがロックされていて削除できない場合がある
                            cw.util.print_ex()
                            if os.path.isdir(fpath):
                                for dpath2, dnames, fnames in os.walk(fpath):
                                    if fnames:
                                        raise
                                else:
                                    cw.util.remove(fpath, trashbox=True)
                            else:
                                raise

                    self.updates.add(os.path.dirname(dst))

                    self.paths.append(dst)
                    self.num += 1
                except:
                    cw.util.print_ex(file=sys.stderr)
                    self.failed = header
                    break

    thread = InstallThread(headers, dstpath, db_exists)
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
        dlg = cw.dialog.message.ErrorMessage(parentdialog, s)
        cw.cwpy.frame.move_dlg(dlg)
        dlg.ShowModal()
        dlg.Destroy()

    if not thread.failed and thread.paths:
        for dpath in thread.updates:
            db.update(dpath, skintype=skintype)

    return thread.failed, thread.paths, False


def create_installdesc(headers):
    if 1 < len(headers):
        name = u"%s本のシナリオ" % (len(headers))
    else:
        name = headers[0].fname
    desc = u"%sを選択先のフォルダに移動します。\n" % (name)
    return desc


def main():
    pass

if __name__ == "__main__":
    main()