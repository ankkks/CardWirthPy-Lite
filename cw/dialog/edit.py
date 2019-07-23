#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import threading
import time
import shutil
import wx
import wx.combo
import colorsys

import cw


#-------------------------------------------------------------------------------
#　パーティ情報変更ダイアログ
#-------------------------------------------------------------------------------

class PartyEditor(wx.Dialog):
    def __init__(self, parent, party=None):
        wx.Dialog.__init__(self, parent, -1, cw.cwpy.msgs["party_information"], size=(cw.wins(312),cw.wins(203)),
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        #サイザーでfitしているので現状サイズを指定できない　
        self.cwpy_debug = False
        if party:
            self.party = party
        else:
            self.party = cw.cwpy.ydata.party

        # パーティ名入力ボックス
        self.textctrl = wx.TextCtrl(self, size=cw.wins((240, 24)))
        self.textctrl.SetMaxLength(18)
        self.textctrl.SetValue(self.party.name)
        font = cw.cwpy.rsrc.get_wxfont("inputname", pixelsize=cw.wins(16))
        self.textctrl.SetFont(font)

        # 所持金パネル
        if self.party.is_adventuring():
            self.panel = MoneyViewPanel(self, self.party)
            #self.panel2 = None
        else:
            self.panel = MoneyEditPanel(self, self.party)
            #self.panel2 = MoneyViewPanel(self, self.party)
        

        # レベルアップの停止
        self.suspend_levelup = cw.util.CWBackCheckBox(self, -1, cw.cwpy.msgs["suspend_levelup"])
        self.suspend_levelup.SetToolTipString(cw.cwpy.msgs["suspend_levelup_description"])
        self.suspend_levelup.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle2", pixelsize=cw.wins(15)))
        self.suspend_levelup.SetValue(self.party.is_suspendlevelup)

        # btn
        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                        cw.wins((100, 28)), cw.cwpy.msgs["decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                        cw.wins((100, 28)), cw.cwpy.msgs["entry_cancel"])

        self._do_layout()
        self._bind()

    def _bind(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        self.Bind(wx.EVT_CHECKBOX, self.OnSuspendLevelUp)
        def recurse(ctrl):
            if not isinstance(ctrl, (wx.TextCtrl, wx.SpinCtrl)):
                ctrl.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
            for child in ctrl.GetChildren():
                recurse(child)
        recurse(self)
        self.backid = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnCancel, id=self.backid)
        seq = [
            (wx.ACCEL_NORMAL, wx.WXK_BACK, self.backid),
            (wx.ACCEL_NORMAL, ord('_'), self.backid),
        ]
        self.accels = seq
        cw.util.set_acceleratortable(self, seq)            

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)

        sizer_btn.Add(self.okbtn, 0, 0, 0)
        sizer_btn.Add(self.cnclbtn, 0, wx.LEFT, cw.wins(20))

        sizer_v1.Add(cw.wins((0, 18)), 0, wx.CENTER, 0)
        sizer_v1.Add(self.textctrl, 0, wx.CENTER|wx.TOP, cw.wins(5))
        sizer_v1.Add(cw.wins((0, 18)), 0, wx.CENTER|wx.TOP, cw.wins(10))
        sizer_v1.Add(self.panel, 0, wx.CENTER|wx.TOP, cw.wins(5))
        #sizer_v1.Add(self.panel2, 0, wx.CENTER|wx.TOP, cw.wins(5))
        sizer_v1.Add(self.suspend_levelup, 0, wx.ALIGN_RIGHT|wx.TOP, cw.wins(10))
        sizer_v1.Add(sizer_btn, 0, wx.CENTER|wx.TOP, cw.wins(13))

        sizer.Add(sizer_v1, 0, wx.ALL, cw.wins(15))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnSuspendLevelUp(self, event):
        cw.cwpy.play_sound("page")

    def OnOk(self, event):
        cw.cwpy.play_sound("harvest")
        name = self.textctrl.GetValue()
        money = self.panel.value

        def func(self, party, suspend_levelup):
            update = False
            if name <> party.name:
                party.set_name(name)
                update = True

            if suspend_levelup <> party.suspend_levelup:
                party.suspend_levelup(suspend_levelup)

            if money <> party.money:
                pmoney = money - party.money
                ymoney = party.money - money
                cw.cwpy.ydata.set_money(ymoney, blink=True)
                party.set_money(pmoney, blink=True)
                update = True

            if update:
                party.write()
                cw.cwpy.draw(True)

            def func(self):
                if self:
                    btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_OK)
                    self.ProcessEvent(btnevent)
            cw.cwpy.frame.exec_func(func, self)
        cw.cwpy.exec_func(func, self, self.party, self.suspend_levelup.GetValue())

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)
        # text
        dc.SetTextForeground(wx.BLACK)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(16)))
        s = cw.cwpy.msgs["party_name"]
        left = (dc.GetSize()[0] - dc.GetTextExtent(s)[0]) // 2
        dc.DrawText(s, left, cw.wins(15))
        s = cw.cwpy.msgs["party_money"]
        left = (dc.GetSize()[0] - dc.GetTextExtent(s)[0]) // 2
        dc.DrawText(s, left, cw.wins(73))

class MoneyEditPanel(wx.Panel):
    def __init__(self, parent, party):
        wx.Panel.__init__(self, parent, style=wx.RAISED_BORDER)
        self.party = party
        self.value = self.party.money
        maxvalue = self.party.money + cw.cwpy.ydata.money
        if maxvalue > 9999999:
            minvalue = maxvalue - 9999999
            maxvalue = 9999999
        else:
            minvalue = 0
        # パーティ所持金変更スライダ
        page = 100
        self.slider = SliderWithButton(self, self.value, minvalue, maxvalue, page, cw.wins(130))
        # パーティ所持金変更スピン
        self.spinctrl = wx.SpinCtrl(self, -1, "", size=(cw.wins(98), cw.wins(20)))
        self.spinctrl.SetForegroundColour(wx.WHITE)
        self.spinctrl.SetBackgroundColour(wx.Colour(0, 0, 128))
        self.spinctrl.SetFont(cw.cwpy.rsrc.get_wxfont("sbarpanel", pixelsize=cw.wins(15)))
        self.spinctrl.SetRange(minvalue, maxvalue)
        self.spinctrl.SetValue(self.value)
        # 宿金庫変更スピン
        self.spinctrl2 = wx.SpinCtrl(self, -1, "", size=(cw.wins(98), cw.wins(20)))#style=wx.NO_BORDER
        self.spinctrl2.SetFont(cw.cwpy.rsrc.get_wxfont("sbarpanel", pixelsize=cw.wins(15)))
        self.spinctrl2.SetForegroundColour(wx.WHITE)
        self.spinctrl2.SetBackgroundColour(wx.Colour(0, 64, 0))
        self.spinctrl2.SetRange(minvalue, maxvalue)
        self.spinctrl2.SetValue(cw.cwpy.ydata.money)
        # bmp
        bmp = cw.cwpy.rsrc.dialogs["MONEYP"]
        self.bmp_pmoney = cw.util.CWPyStaticBitmap(self, -1, [bmp], [bmp])
        self.bmp_pmoney.SetToolTipString( cw.cwpy.msgs["party_money"] )
        bmp = cw.cwpy.rsrc.dialogs["MONEYY"]
        self.bmp_ymoney = cw.util.CWPyStaticBitmap(self, -1, [bmp], [bmp])
        self.bmp_ymoney.SetToolTipString( cw.cwpy.msgs["base_money"] )
        # text
        font = cw.cwpy.rsrc.get_wxfont("paneltitle2", pixelsize=cw.wins(14))
        #self.text_party.SetFont(font)
        #self.text_yado.SetFont(font)

        self.spinctrl.Enable(minvalue < maxvalue)
        self.spinctrl2.Enable(minvalue < maxvalue)

        self._do_layout()
        self._bind()

    def _bind(self):
        self.spinctrl.Bind(wx.EVT_SPINCTRL, self.OnSpinCtrl)
        self.spinctrl2.Bind(wx.EVT_SPINCTRL, self.OnSpinCtrl2)
        self.slider.slider.Bind(wx.EVT_SLIDER, self.OnSlider)

    def OnSlider(self, event):
        value = self.slider.slider.GetValue()
        self.spinctrl.SetValue(value)
        self.spinctrl2.SetValue(self.spinctrl2.GetMax() + self.spinctrl2.GetMin() - value)
        self.value = value
        self.slider._enable()

    def OnSpinCtrl(self, event):
        value = self.spinctrl.GetValue()
        self.slider.set_value(value)
        self.spinctrl2.SetValue(self.spinctrl2.GetMax() + self.spinctrl2.GetMin() - value)
        self.value = value
        self.slider._enable()

    def OnSpinCtrl2(self, event):
        value = self.spinctrl.GetMax() + self.spinctrl.GetMin() - self.spinctrl2.GetValue()
        self.slider.set_value(value)
        self.spinctrl.SetValue(value)
        self.value = value
        self.slider._enable()

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_h1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_v1 = wx.BoxSizer(wx.VERTICAL)#BMPの並び
        sizer_h2 = wx.BoxSizer(wx.HORIZONTAL)#所持金BMP
        sizer_h3 = wx.BoxSizer(wx.HORIZONTAL)#共有BMP
        sizer_v2 = wx.BoxSizer(wx.VERTICAL) #所持金入力
        sizer_v3 = wx.BoxSizer(wx.VERTICAL) #共有入力

        #sizer_v3.Add(self.text_yado, 0, wx.CENTER|wx.TOP, cw.wins(3))
        sizer_v3.Add(self.spinctrl2, 0, wx.CENTER, cw.wins(0))

        #sizer_v2.Add(self.text_party, 0, wx.CENTER, cw.wins(0))
        sizer_v2.Add(self.spinctrl, 0, wx.CENTER, cw.wins(0))

        sizer_h3.Add(self.bmp_ymoney, 0, wx.CENTER, cw.wins(0))
        sizer_h3.Add(sizer_v3, 1, wx.CENTER|wx.LEFT, cw.wins(5))

        sizer_h2.Add(self.bmp_pmoney, 0, wx.CENTER, cw.wins(0))
        sizer_h2.Add(sizer_v2, 1, wx.CENTER|wx.LEFT, cw.wins(5))

        sizer_v1.Add(sizer_h3, 0, wx.CENTER|wx.EXPAND, cw.wins(0))
        sizer_v1.Add(sizer_h2, 0, wx.CENTER|wx.EXPAND, cw.wins(0))

        sizer_h1.Add(self.slider, 0, wx.CENTER, cw.wins(0))
        sizer_h1.Add(sizer_v1, 0, wx.CENTER|wx.LEFT, cw.wins(5))

        sizer.Add(sizer_h1, 0, wx.ALL, cw.wins(5))
        self.SetSizer(sizer)
        #sizer.Fit(self)
        self.Layout()

class MoneyViewPanel(wx.Panel):
    def __init__(self, parent, party):
        wx.Panel.__init__(self, parent, style=wx.STATIC_BORDER)
        self.value = party.money
        self.SetBackgroundColour(wx.Colour(0, 0, 128))
        # bmp
        bmp = cw.cwpy.rsrc.dialogs["MONEYP"]
        self.bmp_pmoney = cw.util.CWPyStaticBitmap(self, -1, [bmp], [bmp])
        self.bmp_pmoney.SetToolTipString( cw.cwpy.msgs["party_money"] )
        # text
        self.text_pmoney = wx.StaticText(self, -1, cw.cwpy.msgs["currency"] % (self.value),
                                        size=(cw.wins(88), -1), style=wx.NO_BORDER|wx.ALIGN_CENTRE_HORIZONTAL)
        self.text_pmoney.SetFont(cw.cwpy.rsrc.get_wxfont("sbarpanel", pixelsize=cw.wins(16)))
        self.text_pmoney.SetForegroundColour(wx.WHITE)
        self.text_pmoney.SetBackgroundColour(wx.Colour(0, 0, 128))
        #self.text_party = wx.StaticText(self, -1, cw.cwpy.msgs["party_money"])
        #font = cw.cwpy.rsrc.get_wxfont("paneltitle2", pixelsize=cw.wins(14))
        #self.text_party.SetFont(font)
        self._do_layout()

    def _do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_h1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_v1 = wx.BoxSizer(wx.VERTICAL)

        #sizer_v1.Add(self.text_party, 0, wx.CENTER, cw.wins(0))
        sizer_v1.Add(self.text_pmoney, 2, wx.CENTER|wx.TOP, cw.wins(2))

        sizer_h1.Add(self.bmp_pmoney, 0, wx.CENTER, cw.wins(0))
        sizer_h1.Add(sizer_v1, 0, wx.CENTER|wx.LEFT, cw.wins(5))

        sizer.Add(sizer_h1, 0, wx.ALL, cw.wins(5))
        self.SetSizer(sizer)
        #sizer.Fit(self)
        self.Layout()

#-------------------------------------------------------------------------------
#  汎用ダイアログ
#-------------------------------------------------------------------------------

class NumberEditDialog(wx.Dialog):

    def __init__(self, parent, title, value, minvalue, maxvalue, page):
        wx.Dialog.__init__(self, parent, -1, title,
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.cwpy_debug = False
        self.value = value

        # スライダ
        self.panel = wx.Panel(self, -1, style=wx.RAISED_BORDER)
        self.slider = NumberEditor(self.panel, value, minvalue, maxvalue, page)
        # btn
        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_cancel"])

        self._do_layout()
        self._bind()

    def _bind(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)

    def _do_layout(self):
        sizer_panel = wx.BoxSizer(wx.HORIZONTAL)
        sizer_panel.Add(self.panel, 1, wx.EXPAND|wx.ALL, cw.wins(5))

        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)
        sizer_btn.Add(self.okbtn, 0, 0, cw.wins(0))
        sizer_btn.Add(self.cnclbtn, 0, wx.LEFT, cw.wins(30))

        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v1.Add(sizer_panel, 0, wx.CENTER|wx.TOP, cw.wins(5))
        sizer_v1.Add(sizer_btn, 0, wx.CENTER|wx.TOP, cw.wins(10))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(sizer_v1, 0, wx.ALL, cw.wins(15))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)

    def OnOk(self, event):
        cw.cwpy.play_sound("harvest")
        self.value = self.slider.get_value()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

class Number2EditDialog(wx.Dialog):

    def __init__(self, parent, title,
                 label1, value1, minvalue1, maxvalue1, page1,
                 label2, value2, minvalue2, maxvalue2, page2 ):
        wx.Dialog.__init__(self, parent, -1, title,
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.cwpy_debug = False
        self.value1 = value1
        self.value2 = value2

        # スライダ
        self.panel = wx.Panel(self, -1, style=wx.RAISED_BORDER)
        self.box1 = wx.StaticBox(self.panel, -1, label1)
        self.box1.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle", pixelsize=cw.wins(12)))
        self.box2 = wx.StaticBox(self.panel, -1, label2)
        self.box2.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle", pixelsize=cw.wins(12)))

        self.slider1 = NumberEditor(self.panel, value1, minvalue1, maxvalue1, page1)
        self.slider2 = NumberEditor(self.panel, value2, minvalue2, maxvalue2, page2)

        # btn
        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_cancel"])

        self._do_layout()
        self._bind()

    def _bind(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)

    def _do_layout(self):
        sizer_box1 = wx.StaticBoxSizer(self.box1, wx.HORIZONTAL)
        sizer_box2 = wx.StaticBoxSizer(self.box2, wx.HORIZONTAL)

        sizer_box1.Add(self.slider1, 1, wx.EXPAND|wx.ALL, cw.wins(5))
        sizer_box2.Add(self.slider2, 1, wx.EXPAND|wx.ALL, cw.wins(5))

        sizer_panel = wx.BoxSizer(wx.VERTICAL)
        sizer_panel.Add(sizer_box1, 1, wx.EXPAND|wx.ALL, cw.wins(5))
        sizer_panel.Add(sizer_box2, 1, wx.EXPAND|wx.BOTTOM|wx.ALL, cw.wins(5))
        self.panel.SetSizer(sizer_panel)

        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)
        sizer_btn.Add(self.okbtn, 0, 0, cw.wins(0))
        sizer_btn.Add(self.cnclbtn, 0, wx.LEFT, cw.wins(30))

        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v1.Add(self.panel, 0, wx.CENTER|wx.TOP, cw.wins(5))
        sizer_v1.Add(sizer_btn, 0, wx.CENTER|wx.TOP, cw.wins(10))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(sizer_v1, 0, wx.ALL, cw.wins(15))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)

    def OnOk(self, event):
        cw.cwpy.play_sound("harvest")
        self.value1 = self.slider1.get_value()
        self.value2 = self.slider2.get_value()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

class NumberComboEditDialog(wx.Dialog):

    def __init__(self, parent, title,
                 label1, mlist, selected,
                 label2, value, minvalue, maxvalue, page):
        wx.Dialog.__init__(self, parent, -1, title,
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.cwpy_debug = False
        self.selected = value
        self.value = value

        self.panel = wx.Panel(self, -1, style=wx.RAISED_BORDER)
        self.box1 = wx.StaticBox(self.panel, -1, label1)
        self.box1.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle", pixelsize=cw.wins(12)))
        self.box2 = wx.StaticBox(self.panel, -1, label2)
        self.box2.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle", pixelsize=cw.wins(12)))

        # コンボボックス
        if 1 <= len(mlist) and not isinstance(mlist[0], (str, unicode)):
            self._combo_panel = wx.Panel(self.panel, -1, size=(-1, cw.wins(24)))
            self.combo = wx.combo.BitmapComboBox(self._combo_panel, -1, style=wx.CB_READONLY)
        else:
            self._combo_panel = None
            self.combo = wx.ComboBox(self.panel, -1, style=wx.CB_READONLY)
        self.combo.SetFont(cw.cwpy.rsrc.get_wxfont("combo", pixelsize=cw.wins(14)))
        for li in mlist:
            if isinstance(li, (str, unicode)):
                self.combo.Append(li)
            else:
                self.combo.Append(li[0], li[1])
        self.combo.Select(selected)

        # スライダ
        self.slider = NumberEditor(self.panel, value, minvalue, maxvalue, page)

        # btn
        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_cancel"])

        self._do_layout()
        self._bind()

    def _bind(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)

    def _do_layout(self):
        sizer_box1 = wx.StaticBoxSizer(self.box1, wx.HORIZONTAL)
        sizer_box2 = wx.StaticBoxSizer(self.box2, wx.HORIZONTAL)

        if self._combo_panel:
            sizer_box1.Add(self._combo_panel, 1, wx.EXPAND|wx.ALL, cw.wins(5))
            def func(self):
                if not self:
                    return
                w, h = self._combo_panel.GetSize()
                self.combo.SetPosition(cw.wins((0, 0)))
                self.combo.SetSize((w, h))
                if sys.platform == "win32":
                    import win32api
                    CB_SETITEMHEIGHT = 0x153
                    win32api.SendMessage(self.combo.Handle, CB_SETITEMHEIGHT, -1, cw.wins(24))
            cw.cwpy.frame.exec_func(func, self)
        else:
            sizer_box1.Add(self.combo, 1, wx.EXPAND|wx.ALL, cw.wins(5))

        sizer_box2.Add(self.slider, 1, wx.EXPAND|wx.ALL, cw.wins(5))

        sizer_panel = wx.BoxSizer(wx.VERTICAL)
        sizer_panel.Add(sizer_box1, 0, wx.EXPAND|wx.ALL, cw.wins(5))
        sizer_panel.Add(sizer_box2, 1, wx.BOTTOM|wx.ALL, cw.wins(5))
        self.panel.SetSizer(sizer_panel)

        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)
        sizer_btn.Add(self.okbtn, 0, 0, cw.wins(0))
        sizer_btn.Add(self.cnclbtn, 0, wx.LEFT, cw.wins(30))

        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v1.Add(self.panel, 0, wx.CENTER|wx.TOP, cw.wins(5))
        sizer_v1.Add(sizer_btn, 0, wx.CENTER|wx.TOP, cw.wins(10))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(sizer_v1, 0, wx.ALL, cw.wins(15))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)

    def OnOk(self, event):
        cw.cwpy.play_sound("harvest")
        self.selected = self.combo.GetSelection()
        self.value = self.slider.get_value()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

class SliderWithButton(wx.Panel):
    _repeat_first = 500
    _repeat_second = 20

    """左右ボタンつきのスライダ。"""
    def __init__(self, parent, value, minvalue, maxvalue, page, sliderwidth):
        wx.Panel.__init__(self, parent, -1)
        self.SetDoubleBuffered(True)

        # スライダ
        self.slider = wx.Slider(self, -1, 0, 0, cw.wins(1),
            size=(sliderwidth,cw.wins(28)), style=wx.SL_BOTH|wx.SL_HORIZONTAL|wx.SL_SELRANGE)

        self.slider.SetFont(cw.cwpy.rsrc.get_wxfont("sbarpanel", pixelsize=cw.wins(14)))
        self.slider.SetBackgroundStyle(wx.BG_STYLE_COLOUR)
        self.slider.SetPageSize(page)

        # smallleft
        #bmp = cw.cwpy.rsrc.buttons["LMOVE"]
        bmp = cw.cwpy.rsrc.buttons["LSMALL"]
        self.leftbtn = wx.BitmapButton(self, -1, bmp)
        self.leftbtn.SetMinSize(cw.wins((20, 24)))
        bmp = cw.imageretouch.to_disabledimage(bmp)
        self.leftbtn.SetBitmapDisabled(bmp)
        # smallright
        #bmp = cw.cwpy.rsrc.buttons["RMOVE"]
        bmp = cw.cwpy.rsrc.buttons["RSMALL"]
        self.rightbtn = wx.BitmapButton(self, -1, bmp)
        self.rightbtn.SetMinSize(cw.wins((20, 24)))
        bmp = cw.imageretouch.to_disabledimage(bmp)
        self.rightbtn.SetBitmapDisabled(bmp)

        if maxvalue <= minvalue:
            self.is_enabled = False
            self.slider.SetRange(minvalue, minvalue+1)
            self.slider.SetValue(minvalue)
            self.slider.Disable()
            self.leftbtn.Disable()
            self.rightbtn.Disable()
        else:
            self.is_enabled = True
            self.slider.SetRange(minvalue, maxvalue)
            self.set_max(maxvalue)
            self.set_value(value)

        self._timer = wx.Timer(self)

        self._do_layout()
        self._bind()

    def set_value(self, value):
        if not self.is_enabled:
            return
        self.slider.SetValue(value)
        self._enable()

    def set_max(self, value):
        maxvalue = value
        minvalue = self.slider.GetMin()
        self.is_enabled = minvalue < maxvalue
        if not self.is_enabled:
            self.slider.SetRange(minvalue, minvalue+1)
            self.slider.SetValue(minvalue)
            self._enable()
            return
        n = (maxvalue - minvalue) / 20.0 if 20 < (maxvalue - minvalue) else 1
        self.slider.SetTickFreq(n, 1)
        self.slider.SetMax(value)
        self._enable()

    def set_min(self, value):
        if not self.is_enabled:
            return
        maxvalue = self.slider.GetMax()
        minvalue = value
        n = (maxvalue - minvalue) / 20.0 if 20 < (maxvalue - minvalue) else 1
        self.slider.SetTickFreq(n, 1)
        self.slider.SetMin(value)
        self._enable()

    def _enable(self):
        self.slider.Enable(self.is_enabled)
        self.leftbtn.Enable(self.is_enabled and self.slider.GetMin() < self.slider.GetValue())
        self.rightbtn.Enable(self.is_enabled and self.slider.GetValue() < self.slider.GetMax())

    def _bind(self):
        self.Bind(wx.EVT_BUTTON, self.OnLeftBtn, self.leftbtn)
        self.Bind(wx.EVT_BUTTON, self.OnRightBtn, self.rightbtn)
        self.leftbtn.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDownBtn)
        self.rightbtn.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDownBtn)
        self.leftbtn.Bind(wx.EVT_LEFT_UP, self.OnMouseUpBtn)
        self.rightbtn.Bind(wx.EVT_LEFT_UP, self.OnMouseUpBtn)
        self.leftbtn.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocusBtn)
        self.rightbtn.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocusBtn)

    def _do_layout(self):
        sizer_slider = wx.BoxSizer(wx.HORIZONTAL)
        sizer_slider.Add(self.leftbtn, 0)
        sizer_slider.Add(self.slider, 0)
        sizer_slider.Add(self.rightbtn, 0)

        self.SetSizer(sizer_slider)
        #sizer_slider.Fit(self)
        self.Layout()

    def OnMouseDownBtn(self, event):
        if event.GetId() == self.leftbtn.GetId():
            self._timerfunc = self._on_leftbtn
            self._timerbtn = self.leftbtn
        elif event.GetId() == self.rightbtn.GetId():
            self._timerfunc = self._on_rightbtn
            self._timerbtn = self.rightbtn
        else:
            assert False
        self._timerfunc()
        self.Bind(wx.EVT_TIMER, self.OnTimer1, self._timer)
        self._timer.Start(SliderWithButton._repeat_first, wx.TIMER_ONE_SHOT)
        event.Skip()

    def OnKillFocusBtn(self, event):
        f = wx.Window.FindFocus()
        if f <> self.leftbtn and f <> self.rightbtn:
            self._end()
        event.Skip()

    def OnMouseUpBtn(self, event):
        self._end()
        event.Skip()

    def _end(self):
        self._timer.Stop()
        def func():
            self._timerfunc = None
            self._timerbtn = None
        wx.CallAfter(func)

    def OnTimer1(self, event):
        pos = self.ScreenToClient(wx.GetMousePosition())
        if self._timerbtn.GetRect().Contains(pos):
            self._timerfunc()
        self._timer.Stop()
        self.Bind(wx.EVT_TIMER, self.OnTimer2, self._timer)
        self._timer.Start(SliderWithButton._repeat_second)

    def OnTimer2(self, event):
        pos = self.ScreenToClient(wx.GetMousePosition())
        if self._timerbtn.GetRect().Contains(pos):
            self._timerfunc()

    def OnLeftBtn(self, event):
        if self._timerfunc:
            return
        self._on_leftbtn()

    def OnRightBtn(self, event):
        if self._timerfunc:
            return
        self._on_rightbtn()

    def _on_leftbtn(self):
        value = self.slider.GetValue()
        if self.slider.GetMin() < value:
            self.slider.SetValue(value-1)
            event = wx.PyCommandEvent(wx.wxEVT_COMMAND_SLIDER_UPDATED, self.slider.GetId())
            event.SetInt(value-1)
            self.slider.ProcessEvent(event)
            self._enable()

    def _on_rightbtn(self):
        value = self.slider.GetValue()
        if value < self.slider.GetMax():
            self.slider.SetValue(value+1)
            event = wx.PyCommandEvent(wx.wxEVT_COMMAND_SLIDER_UPDATED, self.slider.GetId())
            event.SetInt(value+1)
            self.slider.ProcessEvent(event)
            self._enable()

class NumberEditor(wx.Panel):
    def __init__(self, parent, value, minvalue, maxvalue, page):
        #レベル調節
        wx.Panel.__init__(self, parent, -1)

        #レベル表示
        self.text_level = wx.StaticText(self, -1, "%d / %d" % (value, maxvalue) ,
                                        size=(cw.wins(250), -1), style=wx.BORDER|wx.ALIGN_CENTRE_HORIZONTAL)
        self.text_level.SetFont(cw.cwpy.rsrc.get_wxfont("sbarpanel", pixelsize=cw.wins(16)))
        self.text_level.SetForegroundColour(wx.WHITE)
        self.text_level.SetBackgroundColour(wx.Colour(0, 64, 0))

        # スライダー
        self.slider = SliderWithButton(self, value, minvalue, maxvalue, page, cw.wins(200))

        # スピン
        self.spinlabel = wx.StaticText(self, -1, u"直接入力:")
        self.spinlabel.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg2", pixelsize=cw.wins(14)))
        self.spinctrl = wx.SpinCtrl(self, -1, "", size=(cw.wins(80), -1))
        self.spinctrl.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg2", pixelsize=cw.wins(14)))
        self.spinctrl.SetRange(minvalue, maxvalue)
        self.spinctrl.SetValue(value)

        self.set_min(minvalue)
        self.set_max(maxvalue)
        self.set_value(value)

        self._do_layout()
        self._bind()

    def get_value(self):
        return self.slider.slider.GetValue()

    def set_value(self, value):
        self.slider.set_value(value)
        self.spinctrl.SetValue(value)
        self._enable()

    def set_max(self, value):
        self.slider.set_max(value)
        self.spinctrl.SetRange(self.spinctrl.GetMin(), value)
        self._enable()

    def set_min(self, value):
        self.slider.set_min(value)
        self.spinctrl.SetRange(value, self.spinctrl.GetMax())
        self._enable()

    def _enable(self):
        self.spinctrl.Enable(self.slider.is_enabled)
        s = " %d / %d" % (self.slider.slider.GetValue(), self.spinctrl.GetMax())
        self.text_level.SetLabel(s)
        self.slider._enable()

    def _bind(self):
        self.slider.slider.Bind(wx.EVT_SLIDER, self.OnSlider)
        self.spinctrl.Bind(wx.EVT_SPINCTRL, self.OnSpinCtrl)

    def _do_layout(self):
        sizer_v1 = wx.BoxSizer(wx.VERTICAL)

        sizer_v1.Add(self.text_level, 1, wx.TOP|wx.EXPAND, cw.wins(5))
        self.text_level.SetMaxSize( wx.Size(-1,cw.wins(18)) )
        sizer_v1.Add(self.slider, 1, wx.BOTTOM|wx.EXPAND, cw.wins(5))

        sizer_spinctrl = wx.BoxSizer(wx.HORIZONTAL)
        sizer_spinctrl.Add(self.spinlabel, 0, wx.ALIGN_CENTER|wx.RIGHT, cw.wins(5))
        sizer_spinctrl.Add(self.spinctrl, 0, 0, cw.wins(0))

        sizer_v1.Add(sizer_spinctrl, 0, wx.ALIGN_RIGHT, cw.wins(0))

        self.SetSizer(sizer_v1)
        sizer_v1.Fit(self)
        self.Layout()

    def OnSlider(self, evt):
        self.spinctrl.SetValue(self.slider.slider.GetValue())
        self._enable()

    def OnSpinCtrl(self, evt):
        self.slider.slider.SetValue(self.spinctrl.GetValue())
        self._enable()

class ComboEditDialog(wx.Dialog):

    def __init__(self, parent, title, label, mlist, selected):
        wx.Dialog.__init__(self, parent, -1, title,
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.cwpy_debug = False
        self.selected = selected

        self.panel = wx.Panel(self, -1, style=wx.RAISED_BORDER)
        self.box = wx.StaticBox(self.panel, -1, label)
        self.box.SetFont(cw.cwpy.rsrc.get_wxfont("paneltitle", pixelsize=cw.wins(12)))

        # コンボボックス
        if 1 <= len(mlist) and not isinstance(mlist[0], (str, unicode)):
            self._combo_panel = wx.Panel(self.panel, -1, size=(-1, cw.wins(24)))
            self.combo = wx.combo.BitmapComboBox(self._combo_panel, -1, style=wx.CB_READONLY)
        else:
            self._combo_panel = None
            self.combo = wx.ComboBox(self.panel, -1, style=wx.CB_READONLY)
        self.combo.SetFont(cw.cwpy.rsrc.get_wxfont("combo", pixelsize=cw.wins(14)))
        for li in mlist:
            if isinstance(li, (str, unicode)):
                self.combo.Append(li)
            else:
                self.combo.Append(li[0], li[1])
        self.combo.Select(selected)

        # btn
        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_cancel"])

        self._do_layout()
        self._bind()

    def _bind(self):
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)

    def _do_layout(self):
        sizer_box = wx.StaticBoxSizer(self.box, wx.HORIZONTAL)

        if self._combo_panel:
            sizer_box.Add(self._combo_panel, 1, wx.EXPAND|wx.ALL, cw.wins(5))
            def func(self):
                if not self:
                    return
                w, h = self._combo_panel.GetSize()
                self.combo.SetPosition(cw.wins((0, 0)))
                self.combo.SetSize((w, h))
                if sys.platform == "win32":
                    import win32api
                    CB_SETITEMHEIGHT = 0x153
                    win32api.SendMessage(self.combo.Handle, CB_SETITEMHEIGHT, -1, cw.wins(24))
            cw.cwpy.frame.exec_func(func, self)
        else:
            sizer_box.Add(self.combo, 1, wx.EXPAND|wx.ALL, cw.wins(5))

        sizer_panel = wx.BoxSizer(wx.VERTICAL)
        sizer_panel.Add(sizer_box, 0, wx.EXPAND|wx.ALL, cw.wins(5))
        self.panel.SetSizer(sizer_panel)

        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)
        sizer_btn.Add(self.okbtn, 0, 0, cw.wins(0))
        sizer_btn.Add(self.cnclbtn, 0, wx.LEFT, cw.wins(20))

        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v1.Add(self.panel, 0, wx.EXPAND|wx.TOP, cw.wins(5))
        sizer_v1.Add(sizer_btn, 0, wx.CENTER|wx.TOP, cw.wins(10))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(sizer_v1, 0, wx.ALL, cw.wins(15))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)

    def OnOk(self, event):
        cw.cwpy.play_sound("harvest")
        self.selected = self.combo.GetSelection()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

class ComboEditDialog2(wx.Dialog):
    def __init__(self, parent, title, message, choices):
        wx.Dialog.__init__(self, parent, -1, title, size=cw.wins((-1, -1)),
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.message = cw.util.txtwrap(message, 0, width=40, wrapschars=cw.util.WRAPS_CHARS)
        self.cwpy_debug = False

        self.combo = wx.Choice(self, -1, size=cw.wins((200, -1)), choices=choices)
        font = cw.cwpy.rsrc.get_wxfont("combo", pixelsize=cw.wins(16))
        self.combo.SetFont(font)
        self.selected = 0
        self.combo.Select(self.selected)

        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                        cw.wins((100, 30)), cw.cwpy.msgs["decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                        cw.wins((100, 30)), cw.cwpy.msgs["entry_cancel"])
        self._do_layout()
        self._bind()

        w = cw.wins(318)
        h = self.okbtn.GetSize()[1] + self.okbtn.GetPosition()[1] + cw.wins(10)
        self.SetClientSize((w, h))

    def OnOk(self, event):
        cw.cwpy.play_sound("harvest")
        self.selected = self.combo.GetSelection()
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_OK)
        self.ProcessEvent(btnevent)

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)
        # text
        dc.SetTextForeground(wx.BLACK)
        font = cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(15))
        dc.SetFont(font)
        s = self.message
        w, _h, _lineheight = dc.GetMultiLineTextExtent(s)
        dc.DrawText(s, (csize[0]-w)/2, cw.wins(10))

    def _bind(self):
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def _do_layout(self):
        dc = wx.ClientDC(self)
        self._textwidth, self._textheight, _lineheight = dc.GetMultiLineTextExtent(self.message)

        csize = cw.wins(318), cw.wins(0)
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_1.Add((cw.wins(0), cw.wins(20)+self._textheight), 0, 0, cw.wins(0))
        margin = (csize[0] - self.combo.GetSize()[0]) / 2
        sizer_1.Add(self.combo, 0, wx.LEFT|wx.RIGHT, margin)
        sizer_1.Add(cw.wins((0, 10)), 0, 0, cw.wins(0))

        margin = (csize[0] - self.okbtn.GetSize()[0] * 2) / 3
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2.Add(self.okbtn, 0, wx.LEFT, margin)
        sizer_2.Add(self.cnclbtn, 0, wx.LEFT|wx.RIGHT, margin)

        sizer_1.Add(sizer_2, 0, wx.EXPAND, cw.wins(0))
        sizer_1.Add(cw.wins((0, 10)), 0, 0, cw.wins(0))

        self.SetSizer(sizer_1)
        self.Layout()

#-------------------------------------------------------------------------------
#  レベル調節ダイアログ
#-------------------------------------------------------------------------------

class LevelEditDialog(wx.Dialog):
    def __init__(self, parent, mlist, selected, party=None):
        wx.Dialog.__init__(self, parent, -1, cw.cwpy.msgs["regulate_level_title"],
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.cwpy_debug = False

        self.panel = wx.Panel(self, -1, style=wx.RAISED_BORDER)

        self.list = mlist
        self.party = party

        # 対象者
        self.targets = [u"全員"]
        for ccard in self.list:
            self.targets.append(ccard.get_name())
        self.target = wx.ComboBox(self.panel, -1, choices=self.targets, style=wx.CB_READONLY)
        self.target.SetFont(cw.cwpy.rsrc.get_wxfont("combo", pixelsize=cw.wins(14)))
        self.target.Select(max(selected, -1) + 1)
        # smallleft
        bmp = cw.cwpy.rsrc.buttons["LSMALL"]
        self.leftbtn = cw.cwpy.rsrc.create_wxbutton(self.panel, -1, cw.wins((20, 20)), bmp=bmp)
        # smallright
        bmp = cw.cwpy.rsrc.buttons["RSMALL"]
        self.rightbtn = cw.cwpy.rsrc.create_wxbutton(self.panel, -1, cw.wins((20, 20)), bmp=bmp)

        minvalue = 1
        maxvalue = self.get_maxlevel()

        # スライダ
        self.slider = NumberEditor(self.panel, maxvalue, minvalue, maxvalue, 2)

        # btn
        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                      cw.wins((80, 24)), cw.cwpy.msgs["decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                      cw.wins((80, 24)), cw.cwpy.msgs["entry_cancel"])

        self._select_target()

        self._do_layout()
        self._bind()

    def get_selected(self):
        index = self.target.GetSelection()
        if index <= 0:
            return self.list
        else:
            return [self.list[index-1]]

    def get_currentlevel(self):
        level = None

        for ccard in self.get_selected():
            if level is None:
                level = ccard.level
            elif level <> ccard.level:
                level = None
                break

        if level is None:
            return self.get_maxlevel()
        else:
            return level

    def get_maxlevel(self):
        maxvalue = 0
        for ccard in self.get_selected():
            maxvalue = max(maxvalue, ccard.get_limitlevel())

        return maxvalue

    def _select_target(self):
        self.slider.set_max(self.get_maxlevel())
        self.slider.set_value(self.get_currentlevel())

    def _bind(self):
        self.Bind(wx.EVT_COMBOBOX, self.OnSelectTarget, self.target)
        self.Bind(wx.EVT_BUTTON, self.OnLeftBtn, self.leftbtn)
        self.Bind(wx.EVT_BUTTON, self.OnRightBtn, self.rightbtn)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)

    def _do_layout(self):
        sizer_combo = wx.BoxSizer(wx.HORIZONTAL)
        sizer_combo.Add(self.leftbtn, 0, wx.EXPAND)
        sizer_combo.Add(self.target, 1, wx.LEFT|wx.RIGHT|wx.EXPAND, border=cw.wins(5))
        sizer_combo.Add(self.rightbtn, 0, wx.EXPAND)

        sizer_panel = wx.BoxSizer(wx.VERTICAL)
        sizer_panel.Add(sizer_combo, 0, wx.EXPAND|wx.ALL, cw.wins(5))
        sizer_panel.Add(self.slider, 1, wx.BOTTOM|wx.ALL, cw.wins(5))
        self.panel.SetSizer(sizer_panel)

        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)
        sizer_btn.Add(self.okbtn, 0, 0, cw.wins(0))
        sizer_btn.Add(self.cnclbtn, 0, wx.LEFT, cw.wins(25))

        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v1.Add(self.panel, 0, wx.CENTER|wx.TOP, cw.wins(5))
        sizer_v1.Add(sizer_btn, 0, wx.CENTER|wx.TOP, cw.wins(10))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(sizer_v1, 0, wx.ALL, cw.wins(5))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def OnSelectTarget(self, event):
        self._select_target()

    def OnLeftBtn(self, event):
        index = self.target.GetSelection()
        if index <= 0:
            self.target.SetSelection(len(self.list))
        else:
            self.target.SetSelection(index - 1)
        self._select_target()

    def OnRightBtn(self, event):
        index = self.target.GetSelection()
        if len(self.list) <= index:
            self.target.SetSelection(0)
        else:
            self.target.SetSelection(index + 1)
        self._select_target()

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)

    def OnOk(self, event):
        def func(seq, level, party):
            update = False
            for ccard in seq:
                clevel = min(level, ccard.get_limitlevel())
                if ccard.level == clevel:
                    continue

                ccard.set_level(clevel, regulate=True, backpack_party=party)
                #PyLite:レベル上限所持判定
                ccard.get_levelmax()
                ccard.is_edited = True
                if hasattr(ccard, "cardimg") and hasattr(ccard.cardimg, "set_levelimg"):
                    update = True
                    cw.cwpy.play_sound("harvest")
                    cw.animation.animate_sprite(ccard, "hide")
                    ccard.cardimg.set_levelimg(ccard.level)
                    ccard.update_image()
                    cw.animation.animate_sprite(ccard, "deal")

            if not update:
                cw.cwpy.play_sound("harvest")

        selected = self.get_selected()
        level = self.slider.get_value()
        cw.cwpy.exec_func(func, selected, level, self.party)

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)


#-------------------------------------------------------------------------------
#  背景色変更ダイアログ
#-------------------------------------------------------------------------------

class BackColorEditDialog(wx.Dialog):
    def __init__(self, parent, ccard):
        wx.Dialog.__init__(self, parent, -1, cw.cwpy.msgs["edit_bgcolor"],
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX|wx.MINIMIZE_BOX)
        self.cwpy_debug = False

        self.huepanel = wx.Panel(self, -1, size=cw.wins((181, 32)))
        self.huepanel.SetDoubleBuffered(True)
        self.saturationpanel = wx.Panel(self, -1, size=cw.wins((181, 32)))
        self.saturationpanel.SetDoubleBuffered(True)
        self.valuepanel = wx.Panel(self, -1, size=cw.wins((181, 32)))
        self.valuepanel.SetDoubleBuffered(True)

        self.presetcolor_list = []
        self.presetcolor_names = [cw.cwpy.msgs["edit_bgcolor_preset"]]
        if os.path.isfile("Data/BackColors.xml"):
            try:
                data = cw.data.xml2element("Data/BackColors.xml")
                for e in data:
                    if e.tag == "PresetColor":
                        r = e.getattr(".", "r", "")
                        g = e.getattr(".", "g", "")
                        b = e.getattr(".", "b", "")
                        name = u"%s" % (e.text)
                        if r and g and b and name:
                            r = max(0, min(192, int(r)))
                            g = max(0, min(192, int(g)))
                            b = max(0, min(192, int(b)))
                            self.presetcolor_list.append((name, r, g, b))
                            self.presetcolor_names.append(name)
            except:
                pass
        else:
            #PyLite:設定ファイルが無くてもサンプルを用意
            samplecolors = [[u"Navy(デフォルト)", 0, 0, 128],
                            [u"Maroon", 128, 0, 0],
                            [u"Green", 0, 128, 0],
                            [u"Black", 0, 0, 0]]
            self.presetcolor_list += samplecolors
            self.presetcolor_names += [x[0] for x in samplecolors]

        self.colorchoice = wx.Choice(self, choices=self.presetcolor_names)
        self.colorchoice.SetFont(cw.cwpy.rsrc.get_wxfont("combo", pixelsize=cw.wins(14)))
        self.colorchoice.SetSelection(0)

        self.is_select_huepanel = True
        self.is_select_saturationpanel = False
        self.is_select_valuepanel = False

        self.dragging_huepanel = False
        self.dragging_saturationpanel = False
        self.dragging_valuepanel = False

        self.ccard = ccard
        self.hsv = self.rgb2hsv(self.get_rgblist())

        # btn
        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                      cw.wins((100, 30)), cw.cwpy.msgs["entry_cancel"])


        # ドラッグ中に離されたらドラッグを中止する
        self._destroyed = False

        def func():
            while not self._destroyed:
                time.sleep(0.001)
                if self.dragging_huepanel or self.dragging_saturationpanel or self.dragging_valuepanel:
                    def end_drag(self):
                        if not self:
                            return
                        st = wx.GetMouseState()
                        if not st.LeftIsDown():
                            self.dragging_huepanel = False
                            self.dragging_saturationpanel = False
                            self.dragging_valuepanel = False
                    cw.cwpy.frame.exec_func(end_drag, self)

        thr = threading.Thread(target=func)
        thr.start()

        self._do_layout()
        self._bind()

    def hsv2rgb(self, hsv):
        return list(map(lambda x: round(x * 256), colorsys.hsv_to_rgb(hsv[0], hsv[1], hsv[2])))

    def rgb2hsv(self, rgb):
        #PyLite：TODO：Python3の整数除算 Floatにする
        return colorsys.rgb_to_hsv(rgb[0] / 256.0, rgb[1] / 256.0, rgb[2] / 256.0)

    def get_rgblist(self):
        r = cw.util.numwrap(self.ccard.data.getint("Property/BackColor", "r", -1), -1, 192)
        g = cw.util.numwrap(self.ccard.data.getint("Property/BackColor", "g", -1), -1, 192)
        b = cw.util.numwrap(self.ccard.data.getint("Property/BackColor", "b", -1), -1, 192)

        if r == -1 or g == -1 or b == -1:
            r = 0
            g = 0
            b = 128
        return (r, g, b)

    def _bind(self):
        self.huepanel.Bind(wx.EVT_PAINT, self.OnPaintHuePanel)
        self.huepanel.Bind(wx.EVT_LEFT_DOWN, self.OnLeftClickHuePanel)
        self.huepanel.Bind(wx.EVT_MOTION, self.OnDragHuePanel)
        self.huepanel.Bind(wx.EVT_LEFT_UP, self.OnReleaseHuePanel)
        self.huepanel.Bind(wx.EVT_KILL_FOCUS, self.OnReleaseHuePanel)
        self.huepanel.Bind(wx.EVT_SET_FOCUS, self.OnSetFocusHuePanel)
        self.huepanel.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocusHuePanel)
        self.huepanel.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDownHuePanel)
        # wx.EVT_KEY_DOWNではカーソルキーが反応しない

        self.saturationpanel.Bind(wx.EVT_PAINT, self.OnPaintSaturationPanel)
        self.saturationpanel.Bind(wx.EVT_LEFT_DOWN, self.OnLeftClickSaturationPanel)
        self.saturationpanel.Bind(wx.EVT_MOTION, self.OnDragSaturationPanel)
        self.saturationpanel.Bind(wx.EVT_LEFT_UP, self.OnReleaseSaturationPanel)
        self.saturationpanel.Bind(wx.EVT_KILL_FOCUS, self.OnReleaseSaturationPanel)
        self.saturationpanel.Bind(wx.EVT_SET_FOCUS, self.OnSetFocusSaturationPanel)
        self.saturationpanel.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocusSaturationPanel)
        self.saturationpanel.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDownSaturationPanel)

        self.valuepanel.Bind(wx.EVT_PAINT, self.OnPaintValuePanel)
        self.valuepanel.Bind(wx.EVT_LEFT_DOWN, self.OnLeftClickValuePanel)
        self.valuepanel.Bind(wx.EVT_MOTION, self.OnDragValuePanel)
        self.valuepanel.Bind(wx.EVT_LEFT_UP, self.OnReleaseValuePanel)
        self.valuepanel.Bind(wx.EVT_KILL_FOCUS, self.OnReleaseValuePanel)
        self.valuepanel.Bind(wx.EVT_SET_FOCUS, self.OnSetFocusValuePanel)
        self.valuepanel.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocusValuePanel)
        self.valuepanel.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDownValuePanel)

        self.colorchoice.Bind(wx.EVT_CHOICE, self.OnChoicePreset)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        def recurse(ctrl):
            if not isinstance(ctrl, (wx.TextCtrl, wx.SpinCtrl)):
                ctrl.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
            for child in ctrl.GetChildren():
                recurse(child)
        recurse(self)

    def _do_layout(self):
        sizer_panel = wx.BoxSizer(wx.VERTICAL)
        sizer_panel.Add(self.huepanel, 1, wx.CENTER | wx.ALL, cw.wins(5))
        sizer_panel.Add(self.saturationpanel, 1, wx.CENTER | wx.ALL, cw.wins(5))
        sizer_panel.Add(self.valuepanel, 1, wx.CENTER | wx.ALL, cw.wins(5))

        sizer_panel.Add(self.colorchoice, 0, wx.CENTER, 0)

        sizer_btn = wx.BoxSizer(wx.HORIZONTAL)
        sizer_btn.Add(self.okbtn, 0, 0, cw.wins(0))
        sizer_btn.Add(self.cnclbtn, 0, wx.LEFT, cw.wins(30))

        sizer_v1 = wx.BoxSizer(wx.VERTICAL)
        sizer_v1.Add(sizer_panel, 0, wx.CENTER|wx.TOP, cw.wins(5))
        sizer_v1.Add(sizer_btn, 0, wx.CENTER|wx.TOP, cw.wins(10))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(sizer_v1, 0, wx.ALL, cw.wins(15))
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def update_panels(self):
        self.huepanel.Refresh()
        self.saturationpanel.Refresh()
        self.valuepanel.Refresh()

    def OnLeftClickHuePanel(self, evt):
        h = evt.GetX() / cw.UP_WIN / 180.0
        self.hsv = (h, self.hsv[1], self.hsv[2])
        self.dragging_huepanel = True
        self.huepanel.SetFocus()
        self.update_panels()

    def OnSetFocusHuePanel(self, evt):
        self.is_select_huepanel = True
        self.huepanel.Refresh()

    def OnKillFocusHuePanel(self, evt):
        self.is_select_huepanel = False
        self.huepanel.Refresh()

    def OnDragHuePanel(self, evt):
        if self.dragging_huepanel:
            h = evt.GetX() / cw.UP_WIN / 180.0
            self.hsv = (h, self.hsv[1], self.hsv[2])
            self.update_panels()

    def OnReleaseHuePanel(self, evt):
        self.dragging_huepanel = False

    def OnKeyDownHuePanel(self, evt):
        keycode = evt.GetKeyCode()
        if keycode == wx.WXK_LEFT:
            h = max(self.hsv[0] - 0.05, 0)
            self.hsv = (h, self.hsv[1], self.hsv[2])
            self.update_panels()
        elif keycode == wx.WXK_RIGHT:
            h = min(self.hsv[0] + 0.05, 1)
            self.hsv = (h, self.hsv[1], self.hsv[2])
            self.update_panels()
        else:
            evt.Skip()

    def OnPaintHuePanel(self, evt):
        self.draw_huepanel()

    def draw_huepanel(self, update=False):
        if update:
            dc = wx.ClientDC(self.huepanel)
        else:
            dc = wx.PaintDC(self.huepanel)
        hsize = self.huepanel.GetClientSize()

        # カラースケールの入力
        for i in range(0, 362, 2):
            #PyLite:Python3除算
            h = i / 360.0
            s = self.hsv[1]
            v = self.hsv[2]
            rgb = self.hsv2rgb((h, s, v))
            #rgb = map(int, self.hsv2rgb((h, s, v)))
            #PyLite:wx.Colourを指定する必要がない？
            dc.SetBrush(wx.Brush(rgb))
            dc.SetPen(wx.Pen(rgb))
            #dc.SetBrush(wx.Brush(wx.Colour(rgb)))
            #dc.SetPen(wx.Pen(wx.Colour(rgb)))
            dc.DrawRectangle(cw.wins(i // 2), cw.wins(0), cw.wins(2), hsize[1])

        # パネルを選んでいれば枠線の記入
        if self.is_select_huepanel:
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.SetPen(wx.Pen(colour="white", style=wx.PENSTYLE_DOT))
            dc.DrawRectangle(cw.wins(2), cw.wins(2), hsize[0] - cw.wins(4), hsize[1] - cw.wins(4))

        # 選択値に丸印
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen("white"))
        dc.DrawCircle(cw.wins(self.hsv[0] * 180), hsize[1] // 2, hsize[1] // 4)

    def OnLeftClickSaturationPanel(self, evt):
        s = evt.GetX() / cw.UP_WIN / 180.0
        self.hsv = (self.hsv[0], s, self.hsv[2])
        self.dragging_saturationpanel = True
        self.saturationpanel.SetFocus()
        self.update_panels()

    def OnSetFocusSaturationPanel(self, evt):
        self.is_select_saturationpanel = True
        self.saturationpanel.Refresh()

    def OnKillFocusSaturationPanel(self, evt):
        self.is_select_saturationpanel = False
        self.saturationpanel.Refresh()

    def OnDragSaturationPanel(self, evt):
        if self.dragging_saturationpanel:
            s = evt.GetX() / cw.UP_WIN / 180.0
            self.hsv = (self.hsv[0], s, self.hsv[2])
            self.update_panels()

    def OnReleaseSaturationPanel(self, evt):
        self.dragging_saturationpanel = False

    def OnKeyDownSaturationPanel(self, evt):
        keycode = evt.GetKeyCode()
        if keycode == wx.WXK_LEFT:
            s = max(self.hsv[1] - 0.05, 0)
            self.hsv = (self.hsv[0], s, self.hsv[2])
            self.update_panels()
        elif keycode == wx.WXK_RIGHT:
            s = min(self.hsv[1] + 0.05, 1)
            self.hsv = (self.hsv[0], s, self.hsv[2])
            self.update_panels()
        else:
            evt.Skip()

    def OnPaintSaturationPanel(self, evt):
        self.draw_saturationpanel()

    def draw_saturationpanel(self, update=False):
        if update:
            dc = wx.ClientDC(self.saturationpanel)
            dc = wx.BufferedDC(dc, self.saturationpanel.GetClientSize())
        else:
            dc = wx.PaintDC(self.saturationpanel)
        ssize = self.saturationpanel.GetClientSize()

        # スケールの入力
        for i in range(0, 181):
            h = self.hsv[0]
            s = i / 180.0
            v = self.hsv[2]
            rgb = self.hsv2rgb((h, s, v))
            dc.SetBrush(wx.Brush(rgb))
            dc.SetPen(wx.Pen(rgb))
            dc.DrawRectangle(cw.wins(i), cw.wins(0), cw.wins(2), ssize[1])

        # パネルを選んでいれば枠線の記入
        if self.is_select_saturationpanel:
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.SetPen(wx.Pen(colour="white", style=wx.PENSTYLE_DOT))
            dc.DrawRectangle(cw.wins(2), cw.wins(2), ssize[0] - cw.wins(4), ssize[1] - cw.wins(4))

        # 選択値に丸印
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen("white"))
        dc.DrawCircle(cw.wins(self.hsv[1] * 180), ssize[1] // 2, ssize[1] // 4)

    def OnLeftClickValuePanel(self, evt):
        #v = 0.125 + (evt.GetX() / cw.UP_WIN) / 480.0
        v = (evt.GetX() / cw.UP_WIN) / 240.0
        self.hsv = (self.hsv[0], self.hsv[1], v)
        self.dragging_valuepanel = True
        self.valuepanel.SetFocus()
        self.update_panels()

    def OnSetFocusValuePanel(self, evt):
        self.is_select_valuepanel = True
        self.valuepanel.Refresh()

    def OnKillFocusValuePanel(self, evt):
        self.is_select_valuepanel = False
        self.valuepanel.Refresh()

    def OnDragValuePanel(self, evt):
        if self.dragging_valuepanel:
            #v = 0.125 + (evt.GetX() / cw.UP_WIN) / 480.0
            v = (evt.GetX() / cw.UP_WIN) / 240.0
            self.hsv = (self.hsv[0], self.hsv[1], v)
            self.update_panels()

    def OnReleaseValuePanel(self, evt):
        self.dragging_valuepanel = False

    def OnKeyDownValuePanel(self, evt):
        keycode = evt.GetKeyCode()
        if keycode == wx.WXK_LEFT:
            #v = max(self.hsv[2] - 0.01875, 0.125)
            v = max(self.hsv[2] - 0.02, 0)
            self.hsv = (self.hsv[0], self.hsv[1], v)
            self.update_panels()
        elif keycode == wx.WXK_RIGHT:
            #v = min(self.hsv[2] + 0.01875, 0.5)
            v = min(self.hsv[2] + 0.02, 0.75)
            self.hsv = (self.hsv[0], self.hsv[1], v)
            self.update_panels()
        else:
            evt.Skip()

    def OnPaintValuePanel(self, evt):
        self.draw_valuepanel()

    def draw_valuepanel(self, update=False):
        if update:
            dc = wx.ClientDC(self.valuepanel)
            dc = wx.BufferedDC(dc, self.valuepanel.GetClientSize())
        else:
            dc = wx.PaintDC(self.valuepanel)
        vsize = self.valuepanel.GetClientSize()

        # スケールの入力
        # 明度を0.125～0.5の間で選択する
        for i in range(0, 181):
            h = self.hsv[0]
            s = self.hsv[1]
            #v = 0.125 + i / 480.0
            v = i / 240.0
            rgb = self.hsv2rgb((h, s, v))
            dc.SetBrush(wx.Brush(rgb))
            dc.SetPen(wx.Pen(rgb))
            dc.DrawRectangle(cw.wins(i), cw.wins(0), cw.wins(2), vsize[1])

        # パネルを選んでいれば枠線の記入
        if self.is_select_valuepanel:
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.SetPen(wx.Pen(colour="white", style=wx.PENSTYLE_DOT))
            dc.DrawRectangle(cw.wins(2), cw.wins(2), vsize[0] - cw.wins(4), vsize[1] - cw.wins(4))

        # 選択値に丸印
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen("white"))
        #dc.DrawCircle(cw.wins((self.hsv[2] - 0.125) * 480), vsize[1] // 2, vsize[1] // 4)
        dc.DrawCircle(cw.wins((self.hsv[2]) * 240.0), vsize[1] // 2, vsize[1] // 4)

    def OnChoicePreset(self, evt):
        index = self.colorchoice.GetSelection()
        if index > 0:
            selected = self.colorchoice.GetString(index)
            for name, r, g, b in self.presetcolor_list:
                if name == selected:
                    self.hsv = self.rgb2hsv((r, g, b))
                    self.update_panels()

    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)

    def OnOk(self, event):
        def func(ccard, rgb):
            if not ccard.data.find("Property/BackColor") is None:
                ccard.data.edit("Property/BackColor", int(rgb[0]), "r")
                ccard.data.edit("Property/BackColor", int(rgb[1]), "g")
                ccard.data.edit("Property/BackColor", int(rgb[2]), "b")
            else:
                e = cw.data.make_element("BackColor", "")
                ccard.data.insert("Property", e, 0)
                ccard.data.edit("Property/BackColor", int(rgb[0]), "r")
                ccard.data.edit("Property/BackColor", int(rgb[1]), "g")
                ccard.data.edit("Property/BackColor", int(rgb[2]), "b")
            if cw.cwpy.ydata:
                cw.cwpy.ydata.changed()

            cw.cwpy.play_sound("harvest")
            cw.animation.animate_sprite(ccard, "hide")
            cw.animation.animate_sprite(ccard, "deal")

        cw.cwpy.exec_func(func, self.ccard, self.hsv2rgb(self.hsv))

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        cw.cwpy.play_sound("click")
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

    def OnDestroy(self, event):
        self._destroyed = True

#-------------------------------------------------------------------------------
# テキスト入力ダイアログ
#-------------------------------------------------------------------------------

class InputTextDialog(wx.Dialog):
    def __init__(self, parent, title, msg, text="", maxlength=0, addition="", addition_func=None):
        wx.Dialog.__init__(self, parent, -1, title, size=cw.wins((318, 180)),
                style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.cwpy_debug = False
        msg = cw.util.txtwrap(msg, mode=6)
        self.msg = msg

        dc = wx.ClientDC(self)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(15)))
        w, h, _lineheight = dc.GetMultiLineTextExtent(self.msg)
        self._textheight = h
        self.SetClientSize((max(w + cw.wins(10)*2, cw.wins(312)), cw.wins(97)+h))

        self.textctrl = wx.TextCtrl(self, size=(cw.wins(175), -1))
        self.textctrl.SetMaxLength(maxlength)
        self.textctrl.SetValue(text)
        self.textctrl.SelectAll()
        font = cw.cwpy.rsrc.get_wxfont("inputname", pixelsize=cw.wins(16))
        self.textctrl.SetFont(font)

        if addition:
            dc = wx.ClientDC(self)
            font = cw.cwpy.rsrc.get_wxfont("button", pixelsize=cw.wins(14))
            dc.SetFont(font)
            s = cw.cwpy.msgs["auto"]
            tw = dc.GetTextExtent(s)[0] + cw.wins(16)
            self.addition = cw.cwpy.rsrc.create_wxbutton(self, -1, (tw, cw.wins(20)), s)
            self.addition.SetFont(font)
            self.addition_func = addition_func
        else:
            self.addition = None
            self.addition_func = None

        self.okbtn = cw.cwpy.rsrc.create_wxbutton(self, -1,
                                                        cw.wins((100, 30)), cw.cwpy.msgs["decide"])
        self.cnclbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL,
                                                        cw.wins((100, 30)), cw.cwpy.msgs["entry_cancel"])
        self.okbtn.Enable(bool(text))
        self._do_layout()
        self._bind()

    def OnInput(self, event):
        self.text = self.textctrl.GetValue()

        if self.text:
            self.okbtn.Enable()
        else:
            self.okbtn.Disable()

    def OnAddition(self, event):
        self.textctrl.SetValue(self.addition_func())

    def OnOk(self, event):
        self.text = self.textctrl.GetValue()
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_OK)
        self.ProcessEvent(btnevent)

    def OnCancel(self, event):
        self.text = u""
        btnevent = wx.PyCommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_CANCEL)
        self.ProcessEvent(btnevent)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        # background
        bmp = cw.cwpy.rsrc.dialogs["CAUTION"]
        csize = self.GetClientSize()
        cw.util.fill_bitmap(dc, bmp, csize)
        # text
        dc.SetTextForeground(wx.BLACK)
        font = cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(15))
        dc.SetFont(font)
        s = self.msg
        w, h, _lineheight = dc.GetMultiLineTextExtent(self.msg)
        dc.DrawLabel(self.msg, (0, cw.wins(10), csize[0], h), wx.ALIGN_CENTER)

    def _bind(self):
        self.Bind(wx.EVT_TEXT, self.OnInput, self.textctrl)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.okbtn)
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        if self.addition:
            self.Bind(wx.EVT_BUTTON, self.OnAddition, self.addition)

    def _do_layout(self):
        csize = self.GetClientSize()
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1.Add((cw.wins(0), cw.wins(20)+self._textheight), 0, 0, cw.wins(0))
        tw = self.textctrl.GetSize()[0]
        if self.addition:
            tw += self.addition.GetSize()[0]
        margin = (csize[0] - tw) / 2
        if self.addition:
            sizer_h = wx.BoxSizer(wx.HORIZONTAL)
            sizer_h.Add(self.textctrl, 0, wx.CENTER, cw.wins(0))
            sizer_h.Add(self.addition, 0, wx.CENTER, cw.wins(0))
            sizer_1.Add(sizer_h, 0, wx.LEFT|wx.RIGHT, margin)
        else:
            sizer_1.Add(self.textctrl, 0, wx.LEFT|wx.RIGHT, margin)
        sizer_1.Add(cw.wins((0, 12)), 0, 0, cw.wins(0))
        sizer_1.Add(sizer_2, 1, wx.EXPAND, cw.wins(0))

        margin = (csize[0] - self.okbtn.GetSize()[0] * 2) / 3
        sizer_2.Add(self.okbtn, 0, wx.LEFT, margin)
        sizer_2.Add(self.cnclbtn, 0, wx.LEFT|wx.RIGHT, margin)

        self.SetSizer(sizer_1)
        self.Layout()

def main():
    pass

if __name__ == "__main__":
    main()
