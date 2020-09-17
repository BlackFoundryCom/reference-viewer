"""
Copyright 2020 Black Foundry.

This file is part of Reference Viewer.

Reference Viewer is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Reference Viewer is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Reference Viewer.  If not, see <https://www.gnu.org/licenses/>.
"""

from dataclasses                import dataclass
from mojo.events                import addObserver, removeObserver
from mojo.extensions            import getExtensionDefault, setExtensionDefault
from AppKit                     import NSImage, NSColor
from lib.UI.toolbarGlyphTools   import ToolbarGlyphTools
from mojo.drawingTools          import save, restore, font, fill, text
from mojo.UI                    import UpdateCurrentGlyphView
from vanilla                    import *
import Cocoa
import os

settingsReferenceViewer = "com.black-foundry.settingsReferenceViewer"

@dataclass
class ReferenceItem:

    _slots_ = ["fontFamily", "size", "color", "x", "y"]

    fontFamily: str
    size: int = 300 
    color: tuple = (0, 0, 0, 1)
    x: int = -300
    y: int = 0

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.fontFamily

    def _dict_(self) -> dict:
        return {k: getattr(self, k) for k in self._slots_}

    @property
    def position(self) -> tuple:
        return (self.x, self.y)

    def pointInside(self, point: tuple) -> bool:
        x, y = point
        x1, y1 = self.x, self.y
        x2 = x1 + self.size 
        y2 = y1 + self.size 
        if x1 <= x <= x2 and y1 <= y <= y2:
            return True
        return False

class FontsList:

    _fonts = None

    @classmethod
    def get(cls) -> list:
        if cls._fonts is None:
            manager = Cocoa.NSFontManager.sharedFontManager()
            cls._fonts = list(manager.availableFontFamilies())
        return cls._fonts

    @classmethod
    def reload(cls):
        cls._fonts = None

class Controller:

    base_path = os.path.dirname(__file__)

    def __init__(self):
        self.settings =[]
        addObserver(self, "buttonToolBar", "glyphWindowWillShowToolbarItems")
        self.settingsWindow = SettingsWindow(self)
        self.drawer = GlyphWindowDrawer(self)
        self.observers = False
        self.activ = False

    def buttonToolBar(self, info):
        toolbarItems = info['toolbarItems']
        
        label = 'Show Reference Viewer'
        identifier = 'ReferenceViewer'
        filename = 'ReferenceIcon.pdf'
        callback = self.buttonStartCallback
        index = -2
        
        imagePath = os.path.join(self.base_path, 'resources', filename)
        image = NSImage.alloc().initByReferencingFile_(imagePath)
        
        view = ToolbarGlyphTools(
            (30, 25), 
            [dict(image=image, toolTip=label)], 
            trackingMode="one"
            )
        
        newItem = dict(
            itemIdentifier = identifier,
            label = label,
            callback = callback,
            view = view
            )
        toolbarItems.insert(index, newItem)

    def addNewReference(self, fontFamily: str):
        self.settings.append(ReferenceItem(fontFamily))

    def buttonStartCallback(self, sender):
        self.currentGlyph = CurrentGlyph()

        if self.activ == True:
            removeObserver(self, "glyphAdditionContextualMenuItems")
            self.activ = False
        else:
            self.activ = True
            addObserver(self, "menuItems", "glyphAdditionContextualMenuItems")
            settings = []
            for setting in getExtensionDefault(settingsReferenceViewer, []):
                 settings.append(ReferenceItem(**setting))
            self.settings = settings

            if not self.settings:
                self.openReferenceViewerSettings(None)

        self.toggleObserver()
        UpdateCurrentGlyphView()

    def toggleObserver(self, remove=False):
        if self.observers or remove:
            removeObserver(self, 'currentGlyphChanged')
            removeObserver(self, 'drawPreview')
            removeObserver(self, 'draw')
            removeObserver(self, 'drawInactive')
        else:
            addObserver(self, 'currentGlyphChanged', 'currentGlyphChanged')
            addObserver(self, 'glyphWindowDraw', 'draw')
            addObserver(self, 'glyphWindowDraw', 'drawInactive')
            addObserver(self, 'glyphWindowDraw', 'drawPreview')
            
        self.observers = not self.observers

    def mouseDown(self, info):
        x, y = info['point']
        for i, font in enumerate(self.settings):
            if font.pointInside((x, y)):
                self.deltax, self.deltay = x - font.x, y - font.y
                addObserver(self, "mouseDragged", "mouseDragged")
                self.settingsSelectedIndex = i
                self.settingsWindow.w.settingsList.setSelection([i])
                return

    def mouseDragged(self, info):
        pointX, pointY = info["point"]
        self.settings[self.settingsSelectedIndex].x = pointX - self.deltax
        self.settings[self.settingsSelectedIndex].y = pointY - self.deltay

    def mouseUp(self, info):
        removeObserver(self, "mouseDragged")

    def currentGlyphChanged(self, info):
        self.currentGlyph = info["glyph"]

    def glyphWindowDraw(self, info):
        if self.currentGlyph is None:
            char = ""
        elif not self.currentGlyph.unicode:
            char = ""
        else:
            char = chr(self.currentGlyph.unicode)
        self.drawer.draw(char, info["scale"])

    def menuItems(self, info):
        menuItems = []
        item = ('Reference Viewer Settings', self.openReferenceViewerSettings)
        menuItems.append(item)
        info["additionContextualMenuItems"].extend(menuItems)

    def openReferenceViewerSettings(self, sender):
        if self.settingsWindow is None:
            self.settingsWindow = SettingsWindow(self)
        self.settingsWindow.open()
        addObserver(self, 'mouseDown', 'mouseDown')
        addObserver(self, 'mouseUp', 'mouseUp')

    def closeReferenceViewerSettings(self):
        settings = [e._dict_() for e in self.settings]
        setExtensionDefault(settingsReferenceViewer, settings)
        self.settingsWindow = None
        removeObserver(self, 'mouseDown') 
        removeObserver(self, 'mouseUp') 

class SettingsWindow:

    def __init__(self, controller):
        self.controller = controller

        self.w = HUDFloatingWindow(
            (200, 200), 
            "Reference Viewer Settings",
            )
        self.w.fontManager = ComboBox(
            (10, 10, -40, 20),
            FontsList.get()
            )
        self.w.fontManager.set(FontsList.get()[0])
        self.w.addFont = SquareButton(
            (-40, 10, -10, 20),
            "add",
            callback = self.addFontCallback,
            sizeStyle = "small"
            )
        self.w.addFont.getNSButton().setShowsBorderOnlyWhileMouseInside_(True)
        self.w.settingsList = List(
            (10, 30, -10, 100), 
            self.controller.settings,
            selectionCallback = self.settingsListSelectionCallback,
            enableDelete = True,
            drawFocusRing = False
            )
        self.w.sizeSlider = Slider(
            (10, 140, -10, 20),
            minValue = 10,
            maxValue = 2000,
            value = 300,
            callback = self.sizeSliderCallback
            )
        self.w.sizeSlider.show(0)
        self.w.colorBox = ColorWell(
            (10, 165, -10, -10),
            callback = self.colorBoxCallback
            )
        self.w.colorBox.show(0)
        self.w.settingsList.setSelection([])
        self.w.bind("close", self.windowWillClose)

    def open(self):
        self.w.settingsList.set(self.controller.settings)
        self.w.open()  

    def windowWillClose(self, sender):
        self.controller.closeReferenceViewerSettings()

    def addFontCallback(self, sender: Button):
        fontFamily = self.w.fontManager.get()
        self.controller.addNewReference(fontFamily)
        self.w.settingsList.set(self.controller.settings)
        self.w.settingsList.setSelection([len(self.controller.settings)-1])
        UpdateCurrentGlyphView()

    def settingsListSelectionCallback(self, sender: List):
        self.controller.settings = sender.get()
        sel = sender.getSelection()
        self.w.sizeSlider.show(sel)
        self.w.colorBox.show(sel)
        if not sel: 
            self.font = None
            return
        self.font = sender.get()[sel[0]]
        self.w.sizeSlider.set(self.font.size)
        clr = NSColor.colorWithCalibratedRed_green_blue_alpha_(*self.font.color)
        self.w.colorBox.set(clr)

    def colorBoxCallback(self, sender: ColorWell):
        color = sender.get()
        self.font.color = (
            color.redComponent(),
            color.greenComponent(),
            color.blueComponent(),
            color.alphaComponent()
            )
        UpdateCurrentGlyphView()

    def sizeSliderCallback(self, sender):
        self.font.size = sender.get()
        UpdateCurrentGlyphView()

class GlyphWindowDrawer:

    def __init__(self, controller):
        self.controller = controller

    def draw(self, char: str, scale: float = 1.0):
        save()
        for refFont in self.controller.settings:
            font(str(refFont), refFont.size)
            fill(*refFont.color)
            text(char, refFont.position)
            font(str(refFont), 20)
            text(str(refFont), (refFont.position[0], refFont.position[1]-10))
        restore()

if __name__ == "__main__":
    Controller()