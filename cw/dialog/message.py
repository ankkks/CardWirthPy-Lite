#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wx

import cw


#-------------------------------------------------------------------------------
#　メッセージダイアログ
#-------------------------------------------------------------------------------

class Message(wx.Dialog):
    """
    メッセージダイアログ。
    mode=1だと「はい」「いいえ」。mode=2だと「閉じる」。
    """
    def __init__(self, parent, name, text, mode=2):
        wx.Dialog.__init__(self, parent, -1, name, size=cw.wins((355, 120)),
                            style=wx.CAPTION|wx.SYSTEM_MENU|wx.CLOSE_BOX)
        self.cwpy_debug = False
        self.basetext = text
        self.text = cw.util.txtwrap(text, mode=6)
        self.mode = mode

        dc = wx.ClientDC(self)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(15)))
        w, h, _lineheight = dc.GetMultiLineTextExtent(self.text)
        self._textheight = h
        dw = cw.wins(349)
        dh = cw.wins(68)
        dw = max(dw, w + cw.wins(10)*2)
        dh = max(dh, h + cw.wins(68))

        self.SetClientSize((dw, dh))

        if self.mode == 1:
            # yes and no
            self.yesbtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_OK, cw.wins((120, 30)), cw.cwpy.msgs["yes"])
            self.nobtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL, cw.wins((120, 30)), cw.cwpy.msgs["no"])
            self.buttons = (self.yesbtn, self.nobtn)
        elif self.mode == 2:
            # close
            self.closebtn = cw.cwpy.rsrc.create_wxbutton(self, wx.ID_CANCEL, cw.wins((120, 30)), cw.cwpy.msgs["close"])
            self.buttons = (self.closebtn,)
        else:
            assert False

        # layout
        self._do_layout()
        # bind
        self.Bind(wx.EVT_RIGHT_UP, self.OnCancel)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        copyid = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnCopyDetail, id=copyid)
        seq = [
            (wx.ACCEL_CTRL, ord('C'), copyid),
        ]
        cw.util.set_acceleratortable(self, seq)

    def OnCopyDetail(self, event):
        cw.cwpy.play_sound("equipment")
        s = [u"[Window Title]", self.GetTitle(), u"", u"[Content]", self.basetext, u""]
        b = []
        for button in self.buttons:
            b.append(u"[%s]" % button.GetLabelText())
        s.append(u" ".join(b))
        cw.util.to_clipboard(u"\n".join(s))

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
        # massage
        dc.SetTextForeground(wx.BLACK)
        dc.SetFont(cw.cwpy.rsrc.get_wxfont("dlgmsg", pixelsize=cw.wins(15)))
        dc.DrawLabel(self.text, (0, cw.wins(12), csize[0], self._textheight), wx.ALIGN_CENTER)

    def _do_layout(self):
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1.Add((cw.wins(0), self._textheight + cw.wins(24)), 0, 0, 0)
        sizer_1.Add(sizer_2, 1, wx.EXPAND, 0)
        csize = self.GetClientSize()

        if self.mode == 1:
            margin = (csize[0] - self.yesbtn.GetSize()[0] * 2) / 3
            sizer_2.Add(self.yesbtn, 0, wx.LEFT, margin)
            sizer_2.Add(self.nobtn, 0, wx.LEFT|wx.RIGHT, margin)
        elif self.mode == 2:
            margin = (csize[0] - self.closebtn.GetSize()[0]) / 2
            sizer_2.Add(self.closebtn, 0, wx.LEFT, margin)

        self.SetSizer(sizer_1)
        self.Layout()

class YesNoMessage(Message):
    def __init__(self, parent, name, text):
        Message.__init__(self, parent, name, text, 1)

class ErrorMessage(Message):
    def __init__(self, parent, text):
        cw.cwpy.play_sound("error")
        Message.__init__(self, parent, cw.cwpy.msgs["error_message"], text, 2)

def main():
    pass

if __name__ == "__main__":
    main()
