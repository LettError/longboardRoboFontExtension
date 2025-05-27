"""
    Successor to Skateboard and Superpolator
    Fast, interactive previews of glyphs in a designspace.
    
    erik@letterror.com
    October 2024
    
    We Love Git
"""

import importlib
import ufoProcessor.ufoOperator
importlib.reload(ufoProcessor.ufoOperator)
import ezui
import math, time, os, traceback
import AppKit
import webbrowser

from random import randint, choice, random

import merz

from mojo.UI import inDarkMode

from mojo.events import (
    setActiveEventTool,
    getActiveEventTool,
    publishEvent,
    postEvent
)

from mojo.extensions import ExtensionBundle, getExtensionDefault, setExtensionDefault
from mutatorMath.objects.mutator import Location

from mojo.subscriber import (
    Subscriber,
    registerGlyphEditorSubscriber,
    unregisterGlyphEditorSubscriber,
    registerSubscriberEvent
)

from mojo.roboFont import OpenWindow, RGlyph

from fontTools.pens.basePen import BasePen
from fontTools.ufoLib.glifLib import writeGlyphToString
from fontTools.designspaceLib import InstanceDescriptor

from datetime import datetime


eventID = "com.letterror.longboardNavigator"
navigatorLocationChangedEventKey = eventID + "navigatorLocationChanged.event"
navigatorUnitChangedEventKey = eventID + "navigatorUnitChanged.event"
navigatorActiveEventKey = eventID + "navigatorActive.event"
navigatorInactiveEventKey = eventID + "navigatorInctive.event"

toolID = "com.letterror.longboard"
containerKey = toolID + ".layer"
previewContainerKey = toolID + ".preview.layer"
statsContainerKey = toolID + ".stats.layer"
copiedGlyphLocationLibKey = toolID + ".location"

settingsChangedEventKey = toolID + ".settingsChanged.event"
operatorChangedEventKey = toolID + ".operatorChanged.event"
interactionSourcesLibKey = toolID + ".interactionSources"

# Extension defaults example
#https://robofont.com/documentation/how-tos/mojo/read-write-defaults/
extensionDefaultKey = toolID + ".defaults"

from mojo.events import (
    installTool,
    BaseEventTool,
)


def glyphEditorIsInZoom():
    # detect if we're zooming at the moment
    tool = getActiveEventTool()
    return bool(tool._zooming)

# kink analysis
def pt(*p):
    return [(q.x, q.y) for q in p]

def dotProduct(v1, v2):
    return sum(x*y for x, y in zip(v1, v2))
    
def norm(v):
    l = math.sqrt(v[0]**2+v[1]**2)
    return v[0]/l, v[1]/l

def findKinks(glyph, res=3):
    results = []
    contours = glyph.contours
    for ci, c in enumerate(contours):
        points = c.points
        lp = len(points)
        for pi, pt2 in enumerate(points):
            if not pt2.smooth: continue
            pt1 = points[pi-1]
            pt3 = points[(pi+1)%lp]
            if pt3.type == "offcurve" or pt1.type == "offcurve":
                p1, p2, p3 = pt(pt1, pt2, pt3) #unpack them from RF points
                # v1 is p1 / p2
                # v2 is p2 / p3 ?
                # endpoint - startpoint
                v1 = norm((p2[0]-p1[0], p2[1]-p1[1]))
                v2 = norm((p3[0]-p2[0], p3[1]-p2[1]))
                dp = round(dotProduct(v1, v2), res)
                if dp < 1:
                    results.append((ci, p1, p2, p3, (1-dp)*100))
    return results
    
    
class LongboardNavigatorTool(BaseEventTool):
    def setup(self):
        pass

    def getToolbarTip(self):
        return "Longboard Navigator"

    def getToolbarIcon(self):
        ## return the toolbar icon
        return toolbarIcon


longBoardToolBundle = ExtensionBundle("Longboard")
toolbarIcon = longBoardToolBundle.getResourceImage("icon", ext='pdf')


class CollectorPen(BasePen):
    def __init__(self, glyphSet, path=None):
        self.offset = 0,0
        self.onCurves = []
        self.offCurves = []
        self.startPoints = []
        self._pointIndex = 0
        BasePen.__init__(self, glyphSet)
    def setOffset(self, x=0,y=0):
        self.offset = x, y
    def _moveTo(self, pos):
        mp = (pos[0]+self.offset[0], pos[1]+self.offset[1])
        self.onCurves.append(mp)
        self.startPoints.append(mp)
        self._pointIndex += 1
    def _lineTo(self, pos):
        self.onCurves.append((pos[0]+self.offset[0], pos[1]+self.offset[1]))
        self._pointIndex += 1
    def _curveToOne(self, a, b, c):
        self.offCurves.append((a[0]+self.offset[0], a[1]+self.offset[1]))
        self.offCurves.append((b[0]+self.offset[0], b[1]+self.offset[1]))
        self.onCurves.append((c[0]+self.offset[0], c[1]+self.offset[1]))
        self._pointIndex += 3
    def _closePath(self):
        pass
        
def getLocationsForFont(font, doc):
    # theoretically, a single UFO can be a source in different discrete locations
    discreteLocations = []
    continuousLocations = []
    for s in doc.sources:
        if s.path == font.path:
            cl, dl = doc.splitLocation(s.location)
            if dl is not None:
                discreteLocations.append(dl)
            if cl is not None:
                continuousLocations.append(cl)
    return continuousLocations, discreteLocations

def copyPreviewToClipboard(operator, useVarlib=True, roundResult=True):
    # copy the text of the current preview to the clipboard
    currentPreviewLocation = operator.getPreviewLocation()
    glyph = CurrentGlyph()
    if glyph is None:
        return None
    name = glyph.name
    mathGlyph = operator.makeOneGlyph(name, location=currentPreviewLocation, useVarlib=useVarlib)
    if mathGlyph is not None:
        clipboardGlyph = RGlyph()
        mathGlyph.extractGlyph(clipboardGlyph.asDefcon())
        clipboardGlyph.lib[copiedGlyphLocationLibKey] = currentPreviewLocation
        if roundResult:
            clipboardGlyph.round()
        clipboardGlyph.copyToPasteboard()
        return True
    return False



class LongBoardUIController(Subscriber, ezui.WindowController):
    #    [X] Only show designspace current font is part of @onlyShowRelevantDesignspace
    #    [X] Discrete location follows current font @useDiscreteLocationOfCurrentFont

    previewsFolderName = "previews"
    
    def build(self):
        # LongBoardUIController
        content = """

        (interestingLocations ...)      @interestingLocationsPopup

        | ----------------- |           @axesTable
        | xx | tf | pu | av |
        | ----------------- |

        * Accordion: Tools              @tools 

        > ----
        > * HorizontalStack             @toolsStack        
        >> * VerticalStack              @toolsColumn1
        >>> (Add New Instance)          @addInstance
        >>> (Make Preview UFO)          @makePreviewUFO
        >>> (Copy Glyph to Clipboard)   @copyClipboard
        >> * VerticalStack              @toolsColumn2
        >>> (Default Location)          @resetPreview
        >>> (Random Location)           @randomPreview

        > ----
        > * HorizontalStack             @geometryStack       
        >> (X MutatorMath X| VarLib )   @mathModelButton
        >> [ ] Allow Extrapolation      @allowExtrapolation

        * Accordion: Show              @appearance 

        > ----
        > * HorizontalStack             @appearanceStack       
        >> * VerticalStack              @appearanceColumn1
        >>> ( {align.horizontal.left.fill} |X {align.horizontal.center.fill} X| {align.horizontal.right.fill} ) @alignPreviewButton
        >>> ( {text.alignleft} |X {text.aligncenter} X| {text.alignright} ) @alignStatsButton
        >>> --X-- Haziness              @hazeSlider
        >> * VerticalStack              @appearanceColumn2
        >>> [X] Show Measurements       @showMeasurements
        >>> [X] Show Kinks              @showKinks
        >>> [X] Show Stats              @showStats
        >>> [ ] Show Sources            @showSources
        >>> [ ] Show Vectors            @showVectors

        * Accordion: About              @about     
        > ----
        > ((( 􀍟 LettError | 􁅁 Designspace Help | 􀊵 Sponsor )))   @linksButton
        #> (Test Apply State)           @testApplyState

        """
        wantUIWidth = 400
        halfWidth = wantUIWidth / 2
        descriptionData = dict(
            axesTable=dict(
                height=100,
                width=wantUIWidth,
                items = [],
                columnDescriptions = [
                    dict(
                        identifier="textValue",
                        title="Axis",
                        editable=True
                    ),
                    dict(
                        identifier="popUpValue",
                        title="Move",
                        editable=True,
                        cellDescription=dict(
                            cellType="PopUpButton",
                            cellClassArguments=dict(
                                # 􀞒􀞓􂁣􂁤􂁥
                                # 􂁦􂁧􂁨
                                items=["Horizontal", "Vertical", "Ignore"]
                            )
                        )
                    ),
                    dict(
                        identifier="axisValue",
                        title="Axis Value",
                        editable=True,
                    ),
                ],
            ),
            toolsColumn1=dict(
                width=halfWidth
            ),
            toolsColumn2=dict(
                width=halfWidth
            ),
            appearanceColumn1=dict(
                width=halfWidth,
            ),
            tools=dict(
                closed=True,
                width=wantUIWidth,
            ),
            about=dict(
                closed=True,
                width=wantUIWidth,
            ),
            links=dict(
                width=wantUIWidth,
            ),
            hazeSlider=dict(
                minValue=0.08,
                maxValue=0.8,
                value=0.5,
                width='fill',
            ),
            mathModelButton=dict(
                width=halfWidth,
                segmentDescriptions=[
                    {"width": halfWidth/2, "text": "MutatorMath"},
                    {"width": halfWidth/2, "text": "VarLib"},
                ],
            ),
            #( 􀥖 |X 􀥗 X| 􀥘 ) @alignPreviewButton
            alignPreviewButton=dict(
                width=halfWidth,
            ),
            #( 􀥖 |X 􀥗 X| 􀥘 ) @alignStatsButton  􀌀􀌁􀌂
            alignStatsButton=dict(
                width=halfWidth,
            ),
            addInstance=dict(
                width='fill',
            ),
            makePreviewUFO=dict(
                width='fill',
            ),
            resetPreview=dict(
                width='fill',
            ),
            randomPreview=dict(
                width='fill',
            ),
            copyClipboard=dict(
                width='fill',
            ),
            interestingLocationsPopup=dict(
                width='fill',
            ),
        )
        self.w = ezui.EZWindow(
            title= f"🛹",
            content=content,
            descriptionData=descriptionData,
            controller=self,
            size='auto'
        )
        self.operator = None
        self.axisValueDigits = 3
        self.interestingLocations = []    # list of the locations stored in the popup;
        self.enableActionButtons(False)
        self.wantsVarLib = False
        self.previewAlign = "center"
            
    def enableActionButtons(self, state):
        # enable or disable the action buttons
        try:
            self.w.getItem("addInstance").enable(state)
            self.w.getItem("makePreviewUFO").enable(state)
            self.w.getItem("copyClipboard").enable(state)
            self.w.getItem("makePreviewUFO").enable(state)
            self.w.getItem("resetPreview").enable(state)
            self.w.getItem("randomPreview").enable(state)
            self.w.getItem("interestingLocationsPopup").enable(state)
            self.w.getItem("mathModelButton").enable(state)
            self.w.getItem("alignPreviewButton").enable(state)
            self.w.getItem("hazeSlider").enable(state)
            # make sure to remove items that are no longer part of the UI
            # otherwise I have to bother Tal with dumb questions.
        except AttributeError:
            print(f"LongBoard reports (b):")
            print(traceback.format_exc())
            pass
    
    def collectSettingsState(self, save=False):
        # collect the state of all checkers to store in defaults
        # goal: store all settings in this dict
        # save dict to defaults
        # read dict from prefs
        # exchange dict between controller and subscriber
        # save=True: don't include values that start with underscore
        # Such values need to go to the subscriber, but don't need to be saved.
        #@@
        info = {}
        info["allowExtrapolation"] = self.w.getItem('allowExtrapolation').get()==1
        info["showSources"] = self.w.getItem('showSources').get()==1
        info["showVectors"] = self.w.getItem('showVectors').get()==1
        info["showMeasurements"] = self.w.getItem('showMeasurements').get()==1
        info["showKinks"] = self.w.getItem('showKinks').get()==1
        info["showStats"] = self.w.getItem('showStats').get()==1
        info["wantsVarLib"] = self.w.getItem("mathModelButton").get() == 1
        info['hazeSlider'] = self.w.getItem('hazeSlider').get()
        info['alignPreview'] = ['left', 'center', 'right'][self.w.getItem('alignPreviewButton').get()]
        info['alignStats'] = ['left', 'center', 'right'][self.w.getItem('alignStatsButton').get()]
        info['toolsClosed'] = self.w.getItem('tools').getClosed()
        info['appearanceClosed'] = self.w.getItem('tools').getClosed()
        info['aboutClosed'] = self.w.getItem('about').getClosed()
        if not save:
            # values for the subscriber, but not for the defaults
            # the preferred drag directions
            if self.operator is not None:
                info['_dragDirections'] = self.operator.lib[interactionSourcesLibKey]
                continuousAxisNames = []
                discreteAxisNames = []
                for aD in self.operator.getOrderedContinuousAxes():
                    continuousAxisNames.append(aD.name)    
                for aD in self.operator.getOrderedDiscreteAxes():
                    discreteAxisNames.append(aD.name)
                info['_discreteAxisNames'] = discreteAxisNames
                info['_continuousAxisNames'] = continuousAxisNames
        return info
    
    def applySettingsState(self, info):
        # apply all the values in the info dict to their places
        self.w.getItem('allowExtrapolation').set(info["allowExtrapolation"])
        self.w.getItem('showSources').set(info["showSources"])
        self.w.getItem('showVectors').set(info["showVectors"])
        self.w.getItem('showMeasurements').set(info["showMeasurements"])
        self.w.getItem('showKinks').set(info["showKinks"])
        self.w.getItem('showStats').set(info["showStats"])
        self.w.getItem('hazeSlider').set(info["hazeSlider"])
        self.w.getItem('tools').setClosed(info["toolsClosed"])
        self.w.getItem('appearance').setClosed(info["appearanceClosed"])
        self.w.getItem('about').setClosed(info["aboutClosed"])
        if info["wantsVarLib"]:
            self.w.getItem("mathModelButton").set(1)
        else:
            self.w.getItem("mathModelButton").set(0)
        if 'alignPreview' in info:
            value = None
            if info['alignPreview'] == "left":
                value = 0
            elif info['alignPreview'] == "center":
                value = 1
            elif info['alignPreview'] == "right":
                value = 2
            if value != None:
                self.w.getItem('alignPreviewButton').set(value)

        if 'alignStats' in info:
            if info['alignStats'] == "left":
                value = 0
            elif info['alignStats'] == "center":
                value = 1
            elif info['alignStats'] == "right":
                value = 2
            if value != None:
                self.w.getItem('alignStatsButton').set(value)
                
    def testApplyStateCallback(self, sender=None):
        # randomise settings for the checkers
        print("randomising all the settings")
        def chooseOne():
            return randint(0, 1)
        def chooseTrue():
            return choice([True, False])
        def chooseFactor():
            return random()
        testSettingsDict = {
            'allowExtrapolation': chooseOne(),
            'previewAlign': 'center',
            'showSources': chooseOne(),
            'showVectors': chooseOne(),
            'showMeasurements': chooseOne(),
            'showKinks': chooseOne(),
            'showStats': chooseOne(),
            'wantsVarLib': chooseTrue(),
            'hazeSlider': chooseFactor(),
            'alignPreview': choice(['left', 'center', 'right']),
            'alignStats': choice(['left', 'center', 'right']),
            'toolsClosed': chooseTrue(),
            'aboutClosed': chooseTrue(),
            'appearanceClosed': chooseTrue(),
            }
        self.applySettingsState(testSettingsDict)
        
    def locationToString(self, location):
        t = []
        for name in sorted(location.keys()):
            t.append(f"{name}_{location[name]:3.2f}")
        return "_".join(t)
    
    def designspaceEditorDidCloseDesignspace(self, info):
        self.w.getItem("axesTable").set([])
        self.w.setTitle("🛹")
        self.enableActionButtons(False)
    
    def designspaceEditorDidOpenDesignspace(self, info):
        print("designspaceEditorDidOpenDesignspace", info)
        self.enableActionButtons(True)
    
    def linksButtonCallback(self, sender):
        links = ["https://letterror.com", "https://superpolator.com", "https://github.com/sponsors/letterror"]
        webbrowser.open(links[sender.get()])

    def makePreviewUFOCallback(self, sender):
        # Make a ufo for the current preview location and open it up.
        # Why in longboard and not in DSE? Because it is more about evaluating the
        # current location than it is about adding a new instance to the designspace.
        # Make the UFO filename as Skateboard did it. 
            
        if self.operator is None: return
        if self.operator.path is None: return
        self.operator.loadFonts()
        ufoNameMathTag = "MM"
        currentPreviewLocation = self.operator.getPreviewLocation()
        currentPreviewContinuous, currentPreviewDiscrete = self.operator.splitLocation(currentPreviewLocation)
        defaultFont = self.operator.findDefaultFont(discreteLocation=currentPreviewDiscrete)
        instanceDescriptor = InstanceDescriptor()
        instanceDescriptor.familyName = defaultFont.info.familyName
        instanceDescriptor.styleName = self.locationToString(currentPreviewLocation)
        instanceDescriptor.location = currentPreviewLocation
        # 
        now = datetime.now() # current date and time
        date = now.strftime("%Y-%m-%d-%H-%M-%S")
        # location
        locationString = self.operator.locationToDescriptiveString(currentPreviewLocation)
        # fileName
        operatorFileName = self.getOperatorFileName(self.operator)

        ufoName = f"Preview_{instanceDescriptor.familyName}-{instanceDescriptor.styleName}_{ufoNameMathTag}_{date}.ufo"
        docFolder = os.path.dirname(self.operator.path)
        previewFolder = os.path.join(docFolder, self.previewsFolderName)
        if not os.path.exists(previewFolder):
            os.makedirs(previewFolder)
        ufoPath = os.path.join(previewFolder, ufoName)
        useVarlibState = self.operator.useVarlib
        extrapolateState = self.operator.extrapolate
        self.operator.useVarlib = False
        self.operator.extrapolate = True
        try:
            font = self.operator.makeInstance(instanceDescriptor, decomposeComponents=False)
        except:
            self.showMessage("LongBoard can not make the preview UFO.", informativeText="I'm printing the traceback in the Output.")
            print(f"LongBoard reports:")
            print(traceback.format_exc())
            return
        self.operator.useVarlib = useVarlibState
        self.operator.extrapolate = extrapolateState
        
        if self.operator.useVarlib:
            model = "VarLib"
        else:
            model = "MutatorMath"
        font.info.note = f"Preview UFO generated by LongBoard, using {model}, from designspace {operatorFileName} at coordinates {locationString}, on date {date}."
        font.save(ufoPath)
        font.close()
        OpenFont(ufoPath, showInterface=True)

    def alignPreviewButtonCallback(self, sender):
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())

    def alignStatsButtonCallback(self, sender):
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())

    def mathModelButtonCallback(self, sender):
        # switch to the preferred math model for the previews
        # 0: calculate preview with MutatorMath
        # 1: calculate preview with VarLib
        if sender.get() == 0:
            self.wantsVarLib = False
        else:
            self.wantsVarLib = True
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())
            
    def copyRoundedClipboardCallback(self, sender):
        # copy the text of the current preview to the clipboard
        result = copyPreviewToClipboard(self.operator, useVarlib=self.wantsVarLib, roundResult=True)
        #print("copyClipboardCallback reports", result)

    def resetPreviewCallback(self, sender=None):
        # set the preview location to the default.
        currentPreviewLocation = self.operator.getPreviewLocation()
        currentPreviewContinuous, currentPreviewDiscrete = self.operator.splitLocation(currentPreviewLocation)
        defaultLocation = self.operator.newDefaultLocation(bend=True, discreteLocation=currentPreviewDiscrete)
        self.operator.setPreviewLocation(defaultLocation)
        self.operator.changed()
    
    def randomPreviewCallback(self, sender):
        # set the preview location to a random value.
        # extrapolate a bit if allowExtrapolation is checked.
        if self.w.getItem("allowExtrapolation").get() == 1:
            extra = 0.2
        else:
            extra = 0
        randomLocation = self.operator.randomLocation(extrapolate=extra)
        self.operator.setPreviewLocation(randomLocation)
        self.operator.changed()
        
    def addInstanceCallback(self, sender):
        # add an instance to the current designspace.
        currentLocation = self.operator.getPreviewLocation()
        if currentLocation is None: return
        # first check if this location already has an instance
        for instance in self.operator.instances:
            if instance.location is None: continue
            if currentLocation == instance.location:
                self.showMessage("Longboard can not add instance:", informativeText=f'Designspace already has an instance at this location.', alertStyle='informational', )
                return
        # then add the instance
        self.operator.addInstanceDescriptor(
            designLocation = currentLocation,
            styleName = self.locationToString(currentLocation),
            )
        self.operator.changed()

    def interestingLocationsPopupCallback(self, sender):
        selectedIndex = sender.get()    # skip the first item, it is text
        for i, item in enumerate(self.interestingLocations):
            location, name = item
        if selectedIndex == 0:
            # it is the placeholder text. Don't change anything
            return
        selectionLocation = self.interestingLocations[selectedIndex][0]
        self.operator.setPreviewLocation(selectionLocation)
        self.operator.changed()
    
    def axesTableEditCallback(self, sender):
        # LongBoardUIController
        # callback for the interaction sources table
        # maybe it can have a less generic name than "tableEditCallback"
        # tableEditCallback [{'textValue': 'weight', 'popUpValue': 0}]
        prefs = []
        locationFromTable = {}
        for axis in self.w.getItem("axesTable").get():
            axisName = axis['textValue']
            try:
                axisValue = round(float(str(axis['axisValue'])), self.axisValueDigits)
            except ValueError:
                axisValue = None
            if axisValue is not None:
                locationFromTable[axisName] = axisValue
            if axis['popUpValue'] == 0:     # horizontal
                prefs.append((axisName, "horizontal"))
            elif axis['popUpValue'] == 1:     # vertical
                prefs.append((axisName, "vertical"))
            elif axis['popUpValue'] == 2:     # vertical
                prefs.append((axisName, "ignore"))
        # where is the operatr coming from?
        # can we broadcast this new location to the world?
        if self.operator is not None:
            self.operator.lib[interactionSourcesLibKey] = prefs
            currentPreviewLocation = self.operator.getPreviewLocation()
            currentPreviewLocation.update(locationFromTable)
            self.operator.setPreviewLocation(currentPreviewLocation)
            self.operator.changed()
        
    def started(self):
        # LongBoardUIController
        self.w.open()
        registerGlyphEditorSubscriber(LongboardEditorView)
        # look for settings in the extention defaults
        extensionDefaults = getExtensionDefault(extensionDefaultKey, fallback=None)
        if extensionDefaults is not None:
            self.applySettingsState(extensionDefaults)
        # maybe a glypheditor is open, maybe not.
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())

    def destroy(self):
        # LongBoardUIController
        # store the settings as extension defaults
        setExtensionDefault(extensionDefaultKey, self.collectSettingsState(save=True))
        unregisterGlyphEditorSubscriber(LongboardEditorView)
    
    def glyphEditorDidSetGlyph(self, info):
        # LongBoardUIController
        # send the settings info to the subscriber
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())

    def getAxisScales(self):
        scales = {}
        if self.operator is None:
            return 0.025    # !
        for aD in self.operator.getOrderedContinuousAxes():
            aD_minimum = aD.map_forward(aD.minimum)
            aD_maximum = aD.map_forward(aD.maximum)
            scales[aD.name] = (aD_maximum - aD_minimum)
        return scales
        
    def navigatorLocationChanged(self, info):
        # LongBoardUIController
        # receive notifications about the navigator location changing.
        # scale mouse movement to "increment units"
        # operator has the axes data
        # glypheditor has the viewscale
        # UI has the axis masks
        # sort extrapolation here?
        # or post the filter table when it changes
        # and handle everything in glypheditor?
        lastEvent = info["lowLevelEvents"][-1]
        view = lastEvent.get('view')
        offset = view.offset()
        viewScale = view.scale()
        popOptions = ['horizontal', 'vertical', None]
        data = info["lowLevelEvents"][-1].get('data')
        nav = data['horizontal'], data['vertical']

        # @@_mouse_drag_updating_data
        editorObject = data['editor']

        unit = {}
        for axis in self.w.getItem("axesTable").get():
            name = axis['textValue']
            if axis['popUpValue'] == 0:     # horizontal
                unit[name] = data['horizontal']
            elif axis['popUpValue'] == 1:     # vertical
                unit[name] = data['vertical']
            # and for ignore we don't pass anything
        axisScales = self.getAxisScales()
        extreme = []
        for axisName, offset in unit.items():
            if axisName in editorObject.previewLocation_dragging:
                value = editorObject.previewLocation_dragging[axisName]
                # @@ how to  handle anisotropy here?
                if type(value) == tuple: 
                    value = value[0]
                value += (offset/1000) * axisScales[axisName]/25 # slightly less subjective
                # Explanation: the 1000 is a value that relates to the screen and the number
                # of pixels we want to move in order to travel along the whole axis.
                # The axisScales[axisName] value is the span of the min axis / max axis value.
                editorObject.previewLocation_dragging[axisName] = value
        # check for clipping here
        if self.w.getItem("allowExtrapolation").get() == 0:
            # AttributeError: 'NoneType' object has no attribute 'map_forward'
            try:
                clipped = self.operator.clipDesignLocation(editorObject.previewLocation_dragging)
            except AttributeError:
                clipped = editorObject.previewLocation_dragging
            editorObject.previewLocation_dragging = clipped
        # update the instance outline, but not a rebuild, just move the points
        editorObject.updateInstanceOutline(rebuild=False)
    
    def getOperatorFileName(self, operator):
        if operator.path is None:
            return "Unsaved"
        fileName = os.path.basename(operator.path)
        fileName = os.path.splitext(fileName)[0]
        return fileName

    def relevantOperatorChanged(self, info):
        # LongBoardUIController
        # @@ from https://robofont.com/documentation/reference/api/mojo/mojo-subscriber/#mojo.subscriber.registerSubscriberEvent
        self.operator = info["lowLevelEvents"][0].get('operator')
        operatorFileName = self.getOperatorFileName(self.operator)
        glyph = info["lowLevelEvents"][0].get('glyph')
        if self.operator is None:
            self.showMessage("No designspace?", informativeText=f'Open a designspace in DesignspaceEdit', alertStyle='informational', )
            self.enableActionButtons(False)
            return
        glyphName = None
        if glyph is not None:
            self.enableActionButtons(True)
            glyphName = glyph.name
        currentLocation = self.operator.getPreviewLocation()
        if not currentLocation:
            # the operator can return an empty location.
            # let's reset it to the default location for this designspace and try again.
            self.resetPreviewCallback()
            return

        # ask operator for the interaction sources stored in its lib
        items = []
        prefs = []
        interactionSourcesPref = self.operator.lib.get(interactionSourcesLibKey)
        #interactionSourcesPref = None    # reset prefs
        # check if there are any new axes that aren't listed in the prefs
        seen = []
        if interactionSourcesPref is not None:
            for axisName, interaction in interactionSourcesPref:
                seen.append(axisName)
                v = 2
                roundedValue = None
                if interaction == "horizontal":
                    v = 0
                elif interaction == "vertical":
                    v = 1
                if not axisName in currentLocation:
                    axisValue = "-"
                else:
                    value = currentLocation[axisName]
                    if type(value) is tuple:
                        roundedValue = round(value[0], self.axisValueDigits), round(value[1], self.axisValueDigits)
                    else:
                        roundedValue = round(value, self.axisValueDigits)
                items.append(dict(textValue=axisName, popUpValue=v, axisValue=roundedValue))
            for axisRecord in self.operator.getOrderedContinuousAxes():
                # an axis may have been added since the last time
                # this pref was saved. So check if we have seen all of them.
                if axisRecord.name in seen: continue
                aD_minimum, aD_default, aD_maximum =  self.operator.getAxisExtremes(axisRecord)
                items.append(dict(textValue=axisRecord.name, popUpValue=2, axisValue=aD_default))
        else:
            v = 0
            for axisObject in self.operator.getOrderedContinuousAxes():
                axisValue = currentLocation.get(axisObject.name)
                axisValue = "-"
                axisWarning = ""
                items.append(dict(textValue=axisObject.name, popUpValue=v, axisWarning=axisWarning, axisValue='-'))
                if v == 0:
                    prefs.append((axisObject.name, "horizontal"))
                elif v == 1:
                    prefs.append((axisObject.name, "vertical"))
                elif v == 2:
                    prefs.append((axisObject.name, "ignore"))
                v += 1
                v = max(v, 2)
            self.operator.lib[interactionSourcesLibKey] = prefs
            self.operator.changed()
        self.w.getItem("axesTable").set(items)
        #collect interesting locations here
        currentIndex = 0
        itemIndex = 0
        interestingLocations = [(None, f"Interesting Locations in {operatorFileName}…")]
        itemIndex += 1
        # add source locations
        for src in self.operator.sources:
            if src.location is not None:
                if src.layerName is not None:
                    layerName = f", layer {src.layerName}"
                else:
                    layerName = ""
                interestingLocations.append((src.location, f"🟠 {os.path.basename(src.path)}{layerName}"))
            itemIndex += 1
        # add instance locations
        for instance in self.operator.instances:
            dsloc = instance.getFullDesignLocation(self.operator) # converted
            dsLoc, dsLocDiscrete = self.operator.splitLocation(dsloc)
            if dsloc is not None:
                interestingLocations.append((dsloc, f'🔘 Instance {instance.familyName} {instance.styleName}'))
            itemIndex += 1
        self.interestingLocations = interestingLocations
        self.w.getItem("interestingLocationsPopup").setItems([b for a, b in interestingLocations])
        for itemIndex, item in enumerate(interestingLocations):
            itemLocation, itemLabel = item
            if currentLocation == itemLocation:
                self.w.getItem("interestingLocationsPopup").set(itemIndex)
                break
        if self.operator.path is not None:
            if glyphName is not None:
                self.w.setTitle(f"🛹 {operatorFileName} {glyphName}")
            else:
                self.w.setTitle(f"🛹 {operatorFileName}")
    
    def showPreviewCallback(self, sender):
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())

    def showSourcesCallback(self, sender):
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())

    def showVectorsCallback(self, sender):
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())
    
    def allowExtrapolationCallback(self, sender):
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())
        
    def showMeasurementsCallback(self, sender):
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())
    
    def showKinksCallback(self, sender):
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())
    
    def showStatsCallback(self, sender):
        # LongBoardUIController
        # if the stats are not showing, disable the stats align button.
        self.w.getItem('alignStatsButton').enable(self.w.getItem('showStats').get())
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())
    
    def hazeSliderCallback(self, sender):
        # LongBoardUIController
        postEvent(settingsChangedEventKey, settings=self.collectSettingsState())




# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 



class LongboardEditorView(Subscriber):

    debug = True
    longBoardHazeFactor = 0.5    # check this is the same as the default slider setting
    italicSlantOffsetKey = 'com.typemytype.robofont.italicSlantOffset'

    def setColors(self, active=False):
        # dark mode / light mode
        # active: are we dragging this thing?
        # these might become different colors again
        # so I will keep them as separate attributes for now.
        previewHaze = 0.6
        if active:
            haze = 1
        else:
            haze = self.longBoardHazeFactor
        if self.darkMode:
            fillModel = (.5,.5,.5, .8*haze)
            strokeModel = (1,1,1, haze)
            vectorModel = (.8,.8,.8, .8*haze)
            kinkModel = (1,0,0, haze)
            self.measurementStrokeColor = (0, .8, 1, 1)
            self.measurementFillColor = (0, .8, 1, 1)
        else:
            haze = 1 - self.longBoardHazeFactor
            fillModel = (.5,.5,.5, haze)
            strokeModel = (0,0,0,haze)
            vectorModel = (.2,.2,.2, haze)
            kinkModel = (1,.2,0, haze)
            self.measurementStrokeColor = (0, .25, .5, 1)
            self.measurementFillColor = (0, .25, .5, 1)
        self.sourceStrokeColor = vectorModel
        self.instanceStrokeColor = strokeModel
        self.vectorStrokeColor = vectorModel
        self.kinkStrokeColor = kinkModel
        self.previewFillColor = fillModel
        self.previewStrokeColor = strokeModel
        
    def setPreferences(self):
        # LongboardEditorView
        self.darkMode = inDarkMode()
        self.measurementMarkerSize = 4
        self.measurementStrokeWidth = 1
        self.measurementStrokeDash = (1, 3)
        self.previewStrokeDash = (4, 4)
        self.vectorStrokeDash = (2, 2)
        self.sourceStrokeDash = (1, 2)
        self.instanceStrokeDash = (5, 2)
        self.instanceStrokeDashExtrapolate = (5, 7)
        self.instanceStrokeWidth = 1
        self.kinkStrokeDash = None    #(0, 16)
        self.kinkStrokeWidth = 4
        self.instanceMarkerSize = 4
        self.sourceMarkerSize = 3
        self.measureLineCurveOffset = 50
        self.marginLineHeight = 50    # the height of the margin line in the preview
        self.setColors()
    
    def build(self):
        # LongboardEditorView
        self.setPreferences()
        self.operator = None
        self.currentOperator = None
        self.allowExtrapolation = False    # should we show extrapolation
        self.extrapolating = False    # but are we extrapolating?
        self.showPreview = True
        self.showKinks = True
        self.showVectors = False
        self.showchange = True
        self.previewAlign = "center"
        self.wantsVarLib = False
        self.showSources = False
        self.sourcePens = []
        self.sourceGlyphs = []
        #self.centerAllGlyphs = True
        self.centerFactor = 0    # -1: left, 0: center, 1: right
        self.showVectors = False
        self.showMeasurements = True
        self.showStats = True
        self.statsAlign = "center"
        self.statsRemoveOverlap = True
        self.useDiscreteLocationOfCurrentFont = True
        self.navigatorToolPosition = None
        self.navigatorToolProgress = None
        self.dragging = False
        self.draggingSlowModeFactor = 0.05
        self.preparePreview = False
        self.startInstanceStats = None   # when we start dragging, the initial surface area
        self._lastEventTime = None
        self.previewLocation_dragging = None    # local editing copy of the DSE2 preview location
        self._bar = "-" * 22
        self._dots = len(self._bar)*"."
        self.estimatedStatsTextWidth = 22 * 10

        self.allowExtrapolation = False
        self.longBoardHazeFactor = 0.5
        self.discreteAxisNames = []
        self.continuousAxisNames = []
        self.dragDirections = {}


        glyphEditor = self.getGlyphEditor()
        # container for all layers in the editor window
        self.editorContainer = glyphEditor.extensionContainer(containerKey, location="middleground")
        self.measurementContainer = glyphEditor.extensionContainer(containerKey, location="foreground")

        # container for all layers in the preview window
        # note: different use of the word Preview
        self.previewContainer = glyphEditor.extensionContainer(previewContainerKey, location="preview")
        self.statsContainer = glyphEditor.extensionContainer(statsContainerKey, location="foreground")
        #self.statsTextLayer = self.statsContainer.appendBaseSublayer()

        self.previewPathLayer = self.previewContainer.appendPathSublayer(
            strokeColor = self.previewStrokeColor,
            strokeDash = self.previewStrokeDash,
            strokeWidth = 1,
            fillColor = None,
        )
        self.instancePathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.instanceStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            strokeDash = self.instanceStrokeDash,
            fillColor = None
        )
        self.sourcesPathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.sourceStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None,
            strokeDash = self.sourceStrokeDash,
            strokeCap="round",
        )
        self.kinkPathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.kinkStrokeColor,
            strokeWidth=self.kinkStrokeWidth,
            fillColor = None,
            strokeDash=self.kinkStrokeDash,
            strokeCap="round",
        )
        self.pointsPathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.vectorStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None,
            strokeDash=self.vectorStrokeDash,
            strokeCap="round",
        )
        self.marginsPathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.vectorStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None,
            strokeDash=self.vectorStrokeDash,
            strokeCap="round",
        )
        #self.sourcesMarkerLayer = self.editorContainer.appendBaseSublayer()
        self.instanceMarkerLayer = self.editorContainer.appendBaseSublayer()
        self.measurementsIntersectionsLayer = self.measurementContainer.appendBaseSublayer()
        self.measurementMarkerLayer = self.measurementContainer.appendBaseSublayer()
        self.measurementTextLayer = self.measurementContainer.appendBaseSublayer()

    def glyphEditorWillShowPreview(self, info):
        self.preparePreview = True
        self.updateInstanceOutline()
    
    def glyphEditorWillHidePreview(self, info):
        self.preparePreview = False
        self.updateInstanceOutline()
        
    def glyphEditorDidMouseDown(self, info):
        # LongboardEditorView
        # starting drag
        if info["lowLevelEvents"][-1]["tool"].__class__.__name__ != "LongboardNavigatorTool": return
        self.dragging = True
        self.startInstanceStats = None
        self.setColors(active=True)
        self.navigatorToolPosition = None
        # get the designspace current location and make a local copy
        # then update the local copy while we're dragging
        self.previewLocation_dragging = self.operator.getPreviewLocation()
        self._lastEventTime = None
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)
    
    def glyphEditorDidMouseUp(self, info):
        # LongboardEditorView
        # ending drag
        if info["lowLevelEvents"][-1]["tool"].__class__.__name__ != "LongboardNavigatorTool": return
        self.dragging = False
        self.setColors(active=False)
        self.navigatorToolPosition = None
        self._lastEventTime = None
        if self.operator is not None:
            self.updateInstanceOutline()
            self.operator.setPreviewLocation(self.previewLocation_dragging)
        
    def glyphEditorDidMouseDrag(self, info):
        # LongboardEditorView
        # get the mouse drag from the navigator tool
        # We need the view.scale to "unscale" the mouse delta.
        # Otherwise this could have gone straight to the UI.
        if info["lowLevelEvents"][-1]["tool"].__class__.__name__ != "LongboardNavigatorTool": return
        if not self.operator: return
        #glyphEditorDidMouseDrag {'shiftDown': 131072, 'capLockDown': 0, 'optionDown': 0, 'controlDown': 0, 'commandDown': 0, 'locationInWindow': <CoreFoundation.CGPoint x=308.4765625 y=274.890625>, 'locationInView': <CoreFoundation.CGPoint x=1334.4765625 y=2104.890625>, 'clickCount': 0}
        view = info["lowLevelEvents"][-1].get('view')
        viewScale = view.scale()
        pt = info["lowLevelEvents"][-1]['point']
        sx = pt.x * viewScale
        sy = pt.y * viewScale
        if self.navigatorToolPosition is None:
            self.navigatorToolPosition = [sx, sy]
        self.navigatorToolProgress = sx-self.navigatorToolPosition[0], sy-self.navigatorToolPosition[1]
        self.navigatorToolPosition = [sx, sy]
        event = info["lowLevelEvents"][-1]["event"]
        if self._lastEventTime is None:
            self._lastEventTime = event.timestamp()
            # first even,t can't measure time. just store the value
            return
        t = event.timestamp()
        timeSinceLastEvent = t - self._lastEventTime
        self._lastEventTime = t
        # this is the data we're going to send to the UI
        # the UI knows about the directions and the units
        # we're also going to pass the editor object
        # because the UI needs to call a redraw afterwards
        
        # @@_mouse_drag_updating_data
        dx = self.navigatorToolProgress[0]/timeSinceLastEvent
        dy = self.navigatorToolProgress[1]/timeSinceLastEvent
        if info.get("deviceState").get('shiftDown') == 131072:
            # constrain the movements.
            # shift pressed: clamp x or y
            if abs(dx) > abs(dy):
                dy = 0
            else:
                dx = 0
            print('contrained?', dx, dy)
        if info.get("deviceState").get('commandDown') == 1048576:
            # option pressed: slower speed
            dx *= self.draggingSlowModeFactor
            dy *= self.draggingSlowModeFactor
        data = {
                'editor': self, 
                'previewLocation': self.previewLocation_dragging,
                'horizontal': dx,
                'vertical': dy,
                }
        publishEvent(navigatorLocationChangedEventKey, data=data)
    
    def glyphEditorWantsContextualMenuItems(self, info):
        #@@ 
        # https://robofont.com/documentation/how-tos/subscriber/custom-font-overview-contextual-menu/
        #print("glyphEditorWantsContextualMenuItems", info)
        myMenuItems = [
            ("Copy 🛹 Preview", self.copyPreviewMenuCallback),
            ("Copy 🛹 Preview (Rounded)", self.copyRoundedPreviewMenuCallback),
            "----",
            ("Show 🎁 Location", self.randomLocationMenuCallback),            #("submenu", [("option 3", self.option3Callback)])    # keep for later
        ]
        info["itemDescriptions"].extend(myMenuItems)

    def copyPreviewMenuCallback(self, sender):
        # callback for the glypheditor contextual menu
        result = copyPreviewToClipboard(self.operator, useVarlib=self.wantsVarLib, roundResult=False)

    def copyRoundedPreviewMenuCallback(self, sender):
        # copy the text of the current preview to the clipboard
        result = copyPreviewToClipboard(self.operator, useVarlib=self.wantsVarLib, roundResult=True)
        #print("copyClipboardCallback reports", result)

    def randomLocationMenuCallback(self, sender):
        # callback for the glypheditor contextual menu
        # pop to random location
        randomLocation = self.operator.randomLocation(extrapolate=0.1)
        self.operator.setPreviewLocation(randomLocation)
        self.operator.changed()
            
        
    #def option3Callback(self, sender):
    #    print("option 3 selected")

    def relevantForThisEditor(self, info=None):
        # LongboardEditorView
        # check if the current font belongs to the current designspace.
        # this call is a bit costly.
        # we can store which designspace object 
        #    glyphEditorDidSetGlyph {'subscriberEventName': 'glyphEditorDidSetGlyph', 'lowLevelEvents': [{'view': <DoodleGlyphView: 0x7fa11b4f8c20>, 'glyph': <RGlyph 'O' ('foreground') at 140332211638384>, 'notificationName': 'viewDidChangeGlyph', 'tool': <lib.eventTools.editingTool.EditingTool object at 0x7fa1a0940fd0>}], 'iterations': [{'glyph': <RGlyph 'O' ('foreground') at 140332211638384>, 'glyphEditor': <lib.doodleGlyphWindow.DoodleGlyphWindow object at 0x7fa1a1f7a3d0>, 'locationInGlyph': None, 'deviceState': None, 'NSEvent': None}], 'glyph': <RGlyph 'O' ('foreground') at 140332211638384>, 'glyphEditor': <lib.doodleGlyphWindow.DoodleGlyphWindow object at 0x7fa1a1f7a3d0>, 'locationInGlyph': None, 'deviceState': None, 'NSEvent': None}
        font = None
        ds = None
        # try to find the current space from the glyph
        if info is not None:
            glyphFromNotification = info.get('glyph')
            if glyphFromNotification is not None:
                font = glyphFromNotification.font
                allSpaces = AllDesignspaces(usingFont=font)
                if len(allSpaces)>=1:
                    # assumption
                    self.operator = allSpaces[0]
                    postEvent(operatorChangedEventKey, operator=self.operator)
                    return True, font, allSpaces[0]
        # try to find it from the currentfont
        font = CurrentFont()
        if font.path == None:
            return False, font, None        
        allSpaces = AllDesignspaces(usingFont=font)
        if len(allSpaces)>=1:
            self.operator = allSpaces[0]
            return True, font, allSpaces[0]
        return False, font, None
    
    def destroy(self):
        # LongboardEditorView
        self.editorContainer.clearSublayers()
        self.previewContainer.clearSublayers()
        self.measurementContainer.clearSublayers()
        self.statsContainer.clearSublayers()
        self.currentOperator = None
        
    def glyphEditorDidSetGlyph(self, info):
        # LongboardEditorView
        # when the glyph in the editor has changed
        # get the previewlocation from the designspace
        # rebuild all the layers
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        ds = self.operator
        previewLocation_dragging = ds.getPreviewLocation()
        if previewLocation_dragging is None:
            previewLocation_dragging = ds.newDefaultLocation(bend=True)
            ds.setPreviewLocation(previewLocation_dragging)
        # split into continuous and discrete
        previewContinuous, previewDiscrete = ds.splitLocation(previewLocation_dragging)
        glyphEditor = self.getGlyphEditor()
        editorGlyph = self.getGlyphEditor().getGlyph()
        editorContinuous, editorDiscrete = getLocationsForFont(editorGlyph.font, ds)
        if editorDiscrete not in [[], [None], [None,None], None]:
            if self.useDiscreteLocationOfCurrentFont:
                    if editorDiscrete != previewDiscrete:
                        if editorDiscrete:
                            previewContinuous.update(editorDiscrete[0])
                            ds.setPreviewLocation(previewContinuous)
        else:
            ds.setPreviewLocation(previewContinuous)
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)
    
    def glyphEditorWillClose(self, info):
        #@@
        # https://robofont.com/documentation/reference/api/mojo/mojo-subscriber/
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)

    def designspaceEditorSourceGlyphDidChange(self, info):
        # LongboardEditorView
        # rebuild all the layers
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)

    def checkExtrapolation(self, location):
        # LongboardEditorView
        # check if the axis Value for axis name is in between minimum and maximum
        if self.operator is None: return False
        axes = {ar.name: ar for ar in self.operator.axes}
        for axisName in location:
            axisRecord = axes.get(axisName)
            if axisRecord is None: continue
            if hasattr(axisRecord, "minimum"):
                # probably continuous, discrete axes don't extrapolate
                aD_minimum, aD_default, aD_maximum =  self.operator.getAxisExtremes(axisRecord)
                if not (aD_minimum <= location.get(axisRecord.name) <= aD_maximum): 
                    return True
        return False
        
    def designspaceEditorPreviewLocationDidChange(self, info):
        # LongboardEditorView
        # only update the layers
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        loc = self.previewLocation_dragging = info['location']
        # check extrapolations
        currentPreviewContinuous, currentPreviewDiscrete = self.operator.splitLocation(loc)
        self.extrapolating = self.checkExtrapolation(currentPreviewContinuous)
        self.updateInstanceOutline(rebuild=False)
    
    def glyphDidChangeMeasurements(self, info):
        # LongboardEditorView
        # only update the layers
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        self.updateInstanceOutline(rebuild=True)
    
    def findKinks(self, editorGlyph, previewShift, previewGlyph):
        # LongboardEditorView
        # analyse and draw lines for possible kinks
        # for speed we might want to draw them all in 1 layer
        # but that means we can't show any quantification
        results = findKinks(previewGlyph)
        kinkPen = merz.MerzPen()
        for contourIndex, p1, p2, p3, df in results:
            kinkPen.moveTo(p1)
            kinkPen.lineTo(p2)
            kinkPen.lineTo(p3)
            kinkPen.endPath()
        self.kinkPathLayer.setPath(kinkPen.path)
        
    def drawMeasurements(self, editorGlyph, previewShift, previewGlyph):
        # LongboardEditorView
        # draw intersections for the current measuring beam and the current preview
        # only update the layers
        for measurementIndex, m in enumerate(editorGlyph.measurements):
            if m.startPoint is None or m.endPoint is None:
                continue
            x1, y1 = m.startPoint
            x2, y2 = m.endPoint
            beamData = ((x1,y1),(x2,y2))
            r = previewGlyph.getRepresentation("doodle.Beam", 
                beam=beamData, 
                canHaveComponent=False, 
                italicAngle=editorGlyph.font.info.italicAngle)
            r.intersects.sort()
            for i, mp in enumerate(r.intersects):
                if i == len(r.intersects)-1:
                    break
                mp1 = r.intersects[i]
                mp2 = r.intersects[(i+1)]
                measureLineAngle = math.atan2(mp1[1]-mp2[1], mp1[0]-mp2[0]) - .5*math.pi
                # draw the jumper curve
                bcp1 = mp1[0]
                # layer append or update? 1
                jumperLayerName = f"measurementJumperLine_{editorGlyph.name}_{measurementIndex}_{i}"
                jumperLayer = self.measurementsIntersectionsLayer.getSublayer(jumperLayerName)
                if jumperLayer is None:
                    jumperLayer = self.measurementsIntersectionsLayer.appendPathSublayer(
                        name=jumperLayerName,
                        strokeWidth=self.measurementStrokeWidth,
                        strokeColor=self.measurementStrokeColor,
                        strokeDash = self.measurementStrokeDash,
                        fillColor=None,
                    )
                needlex = math.cos(measureLineAngle) * self.measureLineCurveOffset
                needley = math.sin(measureLineAngle) * self.measureLineCurveOffset
                jumperPen = jumperLayer.getPen(clear=True)
                jumperPen.moveTo(mp1)
                jumperPen.curveTo((mp1[0]+needlex, mp1[1]+needley), (mp2[0]+needlex, mp2[1]+needley), (mp2[0], mp2[1]))
                jumperPen.endPath()
                
                # draw the end markers
                # layer append or update? 2
                measurementMarkerLayerName = f"measurementMarker_{editorGlyph.name}_{measurementIndex}_{i}_start"
                measurementMarkerLayer = self.measurementMarkerLayer.getSublayer(measurementMarkerLayerName)
                if measurementMarkerLayer is None:
                    measurementMarkerLayer = self.measurementMarkerLayer.appendSymbolSublayer(
                        position=mp1,
                        imageSettings = dict(
                            name="oval",
                            size=(self.measurementMarkerSize, self.measurementMarkerSize),
                            fillColor=self.measurementFillColor
                            ),
                        )
                measurementMarkerLayer.setPosition(mp1)
                # layer append or update? 3
                measurementMarkerLayerName = f"measurementMarker_{editorGlyph.name}_{measurementIndex}_{i}_end"
                measurementMarkerLayer = self.measurementMarkerLayer.getSublayer(measurementMarkerLayerName)
                if measurementMarkerLayer is None:
                    measurementMarkerLayer = self.measurementMarkerLayer.appendSymbolSublayer(
                        position=mp2,
                        imageSettings = dict(
                            name="oval",
                            size=(self.measurementMarkerSize, self.measurementMarkerSize),
                            fillColor=self.measurementFillColor
                        ),
                    )
                measurementMarkerLayer.setPosition(mp2)
                # draw the measurement distance text
                # .5 = halfway and that causes overlaps with the normal ruler values
                textOffsetFactor = 0.52    # slightly further out, subjective value.
                textPos = textOffsetFactor*(mp1[0]+mp2[0])+needlex, textOffsetFactor*(mp1[1]+mp2[1])+needley
                dist = math.hypot(mp1[0]-mp2[0], mp1[1]-mp2[1])
                measurementTextLayerName = f"measurementText_{editorGlyph.name}_{measurementIndex}_{i}"
                measurementTextLayer = self.measurementTextLayer.getSublayer(measurementTextLayerName)
                if measurementTextLayer is None:
                    measurementTextLayer= self.measurementTextLayer.appendTextLineSublayer(
                        name=measurementTextLayerName,
                        position=textPos,
                        pointSize=11,
                        fillColor=self.measurementFillColor,
                        horizontalAlignment="center",
                        )
                measurementTextLayer.setText(f"{dist:3.1f}")
                measurementTextLayer.setPosition(textPos)
    
    def prepareSourcesOutlines(self, rebuild=True):
        if self.operator is None:
            return
        ds = self.operator
        editorGlyph = self.getGlyphEditor().getGlyph()
        #self.currentCollectorPen = CollectorPen(glyphSet=editorGlyph.font)
        self.sourcePens = []
        self.sourceGlyphs = []
        cl, dl = getLocationsForFont(editorGlyph.font, ds)
        continuousLocationForCurrentSource = {}
        discreteLocationForCurrentSource = {}
        if cl:
            if cl[0] is not None:
                continuousLocationForCurrentSource = cl[0]
        if dl:
            if dl[0] is not None:
                discreteLocationForCurrentSource = dl[0]
        # draw the source glyphs
        items, unicodes = ds.collectSourcesForGlyph(glyphName=editorGlyph.name, decomposeComponents=True, discreteLocation=discreteLocationForCurrentSource)
        for item in items:
            loc, srcMath, thing = item
            sourcePen = CollectorPen(glyphSet={})
            # do not draw the master we're drawing in
            # 
            sourceGlyph = RGlyph()
            srcMath.extractGlyph(sourceGlyph.asDefcon()) # mathglyph to sourceGlyph
            if self.previewAlign == "center":
                # centering
                shift = .5*editorGlyph.width-.5*sourceGlyph.width
                sourceGlyph.moveBy((shift, 0))
            elif self.previewAlign == "right":
                shift = editorGlyph.width-sourceGlyph.width
                sourceGlyph.moveBy((shift, 0))
                
            sourceGlyph.draw(sourcePen)
            self.sourcePens.append(sourcePen)
            self.sourceGlyphs.append(sourceGlyph)

    def updateSourcesOutlines(self, rebuild=True):
        # draw the previously collected source outlines to a single merz path
        if self.operator is None:
            return
        self.prepareSourcesOutlines(rebuild=rebuild)
        if self.darkMode != inDarkMode():
            self.darkMode = not self.darkMode
        if rebuild:
            self.sourcesPathLayer.setPath(None)
        # merzpen
        sourcePen = merz.MerzPen()
        if self.showSources:
            for sourceGlyphIndex, sourceGlyph in enumerate(self.sourceGlyphs):
                sourceGlyph.draw(sourcePen)
            self.sourcesPathLayer.setPath(sourcePen.path)
    
    def collectGlyphStats(self, glyph):
        # stuff a couple of glyp dimensions in a location
        temp = glyph.copy()
        if self.statsRemoveOverlap:
            temp.removeOverlap()
        return Location(
                width= temp.width,
                leftMargin= temp.leftMargin,
                rightMargin= temp.rightMargin,
                area= temp.area,
            )
        
    def updateInstanceOutline(self, rebuild=True):
        # LongboardEditorView
        # everything necessary to update the preview, time sensitive
        if self.darkMode != inDarkMode():
            self.darkMode = not self.darkMode
        if rebuild:
            # this is set when we're constructing the instance preview
            # for the first time. Clear out everything, rebuild everything
            self.instancePathLayer.clearSublayers()
            self.previewPathLayer.clearSublayers()
            self.statsContainer.clearSublayers()
            #self.statsTextLayer.clearSublayers()
            self.instanceMarkerLayer.clearSublayers()
            self.kinkPathLayer.setPath(None)
            self.marginsPathLayer.setPath(None)
            self.pointsPathLayer.setPath(None)

        self.measurementMarkerLayer.clearSublayers()
        self.measurementsIntersectionsLayer.clearSublayers()
        self.measurementTextLayer.clearSublayers()
        
        if self.operator is None:
            return
        if self.previewLocation_dragging is None:
            return
        editorGlyph = self.getGlyphEditor().getGlyph()
        if editorGlyph is None:
            return

        ds = self.operator
        sourcePens = []
            
        # # boldly assume a font is only in a single discrete location
        cl, dl = getLocationsForFont(editorGlyph.font, ds)
        continuousLocationForCurrentSource = {}
        discreteLocationForCurrentSource = {}
        if cl:
            if cl[0] is not None:
                continuousLocationForCurrentSource = cl[0]
        if dl:
            if dl[0] is not None:
                discreteLocationForCurrentSource = dl[0]

        if self.previewLocation_dragging is not None:
            mathGlyph = ds.makeOneGlyph(editorGlyph.name, location=self.previewLocation_dragging, useVarlib=self.wantsVarLib)
            if editorGlyph is None or mathGlyph is None:
                path = None
                return
            
            previewGlyph = RGlyph()
            mathGlyph.extractGlyph(previewGlyph.asDefcon())
            xMin, yMin, xMax, yMax = previewGlyph.bounds

            shift = 0
            if self.previewAlign == "center":
                #xMin, yMin, xMax, yMax = previewGlyph.bounds
                shift = .5*editorGlyph.width-.5*previewGlyph.width
                previewGlyph.moveBy((shift, 0))
            elif self.previewAlign == "right":
                shift = editorGlyph.width-previewGlyph.width
                previewGlyph.moveBy((shift, 0))

            if self.showStats:
                if self.startInstanceStats == None:
                    self.startInstanceStats = self.collectGlyphStats(previewGlyph)
                else:
                    statsText = ""
                    currentStats = self.collectGlyphStats(previewGlyph)
                    diff = currentStats - self.startInstanceStats
                    wghtPercent = 100 - (100 * self.startInstanceStats['area']) / currentStats['area']
                    wdthPercent = 100 - (100 * self.startInstanceStats['width']) / currentStats['width']
                    wdthAbs = currentStats['width'] - self.startInstanceStats['width']
                    statsText += f"\n\n{self._bar}"
                    continousAxesText = ""
                    discreteAxesText = ""
                    for axisName, axisValue in self.previewLocation_dragging.items():
                        dragIndicator = ""
                        # to show which drag direction this axis responds to
                        if axisName in self.continuousAxisNames:
                            for aN, dD in self.dragDirections:
                                if aN == axisName:
                                    if dD == "horizontal":
                                        dragIndicator = "-"
                                    elif dD == "vertical":
                                        dragIndicator = "|"
                                    else:
                                        dragIndicator = "✕"
                            if type(axisValue) == tuple:
                                # could be anisotropic
                                continousAxesText += f"\n{dragIndicator}\t{axisName[:7]}\t{axisValue[0]:>9.4f}"
                            else:
                                continousAxesText += f"\n{dragIndicator}\t{axisName[:7]}\t{axisValue:>9.4f}"
                        elif axisName in self.discreteAxisNames:
                            discreteAxesText += f"\n:\t{axisName[:7]}\t{int(axisValue):>13d}"
                    statsText += continousAxesText
                    statsText += discreteAxesText
                    statsText += f"\n{self._bar}"
                    statsText += f"\nΔ\tarea \t{wghtPercent:>8.2f}\t%\nΔ\twidth\t{wdthPercent:>8.2f}\t%\nabs\twidth\t{wdthAbs:>8}\tu"
                    statsTextLayerName = f'statsText_{editorGlyph.name}'
                    statsTextLayer = self.statsContainer.getSublayer(statsTextLayerName)
                    # this needs a bit of work..
                    # ideally we'd calculate the width of the string, in local glyph editor units?
                    if self.statsAlign == "left":
                        textPos = (shift, yMin)
                    elif self.statsAlign == "right":
                        textPos = (previewGlyph.width + shift, yMin)
                    elif self.statsAlign == "center":
                        textPos = (0.5 * previewGlyph.width + shift, yMin)
                    if statsTextLayer is None:
                        statsTextLayer= self.statsContainer.appendTextLineSublayer(
                            name=statsTextLayerName,
                            font="Menlo-Regular",
                            position=textPos,
                            pointSize=11,
                            fillColor=self.measurementFillColor,
                            horizontalAlignment=self.statsAlign,
                            )
                    if statsTextLayer is not None:
                        statsTextLayer.setText(statsText)
                        statsTextLayer.setPosition(textPos)
            else:
                self.startInstanceStats = None

            # @@
            self.updateSourceVectors(previewGlyph)

            cpPreview = CollectorPen(glyphSet={})
            previewGlyph.draw(cpPreview)
            if self.showMeasurements:
                self.drawMeasurements(editorGlyph,  shift, previewGlyph)
            if self.showKinks:
                self.findKinks(editorGlyph,  shift, previewGlyph)

            if self.showPreview:
                # 01 stroke instance path in the editor layer
                # layer append or update? 12
                path = previewGlyph.getRepresentation("merz.CGPath")
                instanceLayerName = f'instance_outline_{editorGlyph.name}'
                instanceLayer = self.instancePathLayer.getSublayer(instanceLayerName)
                instanceStrokeDash = self.instanceStrokeDash
                if instanceLayer is None:
                    instanceLayer = self.instancePathLayer.appendPathSublayer(
                        name = instanceLayerName,
                        fillColor=None,
                        strokeColor=self.instanceStrokeColor,
                        strokeWidth=self.instanceStrokeWidth,
                        strokeDash = instanceStrokeDash,
                        strokeCap="round",
                        )
                instanceLayer.setPath(path)
                if self.checkExtrapolation(self.previewLocation_dragging):
                    # we're outside the axis extremes, make the preview outline more stipply
                    # we don't have to rebuild the whole path, just change the strokeDash attr.
                    instanceStrokeDash = self.instanceStrokeDashExtrapolate
                # but then we do need to set it each time.
                instanceLayer.setStrokeDash(instanceStrokeDash)
                
                # set the path in the preview layer as well
                # layer append or update? 13
                previewLayerName = f'instance_preview_{editorGlyph.name}'
                previewLayer = self.previewPathLayer.getSublayer(previewLayerName)
                if previewLayer is None:
                    previewLayer = self.previewPathLayer.appendPathSublayer(
                        name = previewLayerName,
                        strokeColor = self.previewStrokeColor,
                        strokeDash = self.previewStrokeDash,
                        strokeWidth = 1,
                        fillColor = self.previewFillColor,
                        )
                previewLayer.setPath(path)
                
                if self.showVectors:
                    # 03 on curve markers on instance outline
                    for im, m in enumerate(cpPreview.onCurves):
                        # layer append or update? 14 @@
                        onCurveSymbolLayerName = f'preview_onCurve_{editorGlyph.name}_marker_{im}'
                        onCurveSymbolLayer = self.instanceMarkerLayer.getSublayer(onCurveSymbolLayerName)
                        if onCurveSymbolLayer is None:
                            onCurveSymbolLayer = self.instanceMarkerLayer.appendSymbolSublayer(
                                name=onCurveSymbolLayerName,
                                #layer = self.instancePathLayer.getSublayer(layerName),
                                imageSettings = dict(
                                    name="oval", # name of the factory
                                    size=(self.instanceMarkerSize, self.instanceMarkerSize),
                                    fillColor=self.instanceStrokeColor
                                    ),
                                )
                        onCurveSymbolLayer.setPosition(m)
                    # 04 off curve markers on instance outline
                    for im, m in enumerate(cpPreview.offCurves):
                        # layer append or update? 15
                        offCurveSymbolLayerName = f'preview_offCurve_{editorGlyph.name}_marker_{im}'
                        offCurveSymbolLayer = self.instanceMarkerLayer.getSublayer(offCurveSymbolLayerName)
                        if offCurveSymbolLayer is None:
                            offCurveSymbolLayer = self.instanceMarkerLayer.appendSymbolSublayer(
                                name=offCurveSymbolLayerName,
                                imageSettings = dict(
                                    name="oval",
                                    size=(self.instanceMarkerSize, self.instanceMarkerSize),
                                    fillColor=self.instanceStrokeColor
                                ),
                            )
                        offCurveSymbolLayer.setPosition(m)
                    # 05 draw small lines for the left and right margins of the instance outline
                    # show the margin lines at the expected angle
                    italicSlantOffset = editorGlyph.font.lib.get(self.italicSlantOffsetKey, 0)
                    angle = editorGlyph.font.info.italicAngle
                    if angle is None:
                        angle = 0
                    angle = math.radians(90+angle)
                    dx = math.cos(angle) * self.marginLineHeight
                    a = (shift-dx+italicSlantOffset, -self.marginLineHeight)
                    b = (shift+italicSlantOffset, 0)
                    shiftRight = .5*editorGlyph.width +.5*previewGlyph.width
                    c = (shiftRight-dx+italicSlantOffset, -self.marginLineHeight)
                    d = (shiftRight+italicSlantOffset, 0)
                    marginLayerName = f'instance_{editorGlyph.name}_margins'
                    marginLinePath = merz.MerzPen()
                    marginLinePath.moveTo(a)
                    marginLinePath.lineTo(b)
                    marginLinePath.endPath()
                    marginLinePath.moveTo(c)
                    marginLinePath.lineTo(d)
                    marginLinePath.endPath()
                    self.marginsPathLayer.setPath(marginLinePath.path)

    def updateSourceVectors(self, previewGlyph):
        if self.showVectors:
            collectorPen = CollectorPen({})
            previewGlyph.draw(collectorPen)
            vectorPath = merz.MerzPen()
            for sourcePenIndex, s in enumerate(self.sourcePens) :
                for vectorIndex, vector in enumerate(zip(collectorPen.onCurves, s.onCurves)):
                    a, b = vector
                    vectorPath.moveTo(a)
                    vectorPath.lineTo(b)
                    vectorPath.endPath()
            self.pointsPathLayer.setPath(vectorPath.path)
                
    def showSettingsChanged(self, info):
        # LongboardEditorView
        # subscriber callback
        settings = info['lowLevelEvents'][0].get('settings')
        # what to expect in this settings dict from controller.collectSettingsState
        #showSettingsChanged {
            # 'allowExtrapolation': False, 
            # 'showSources': False, 
            # 'showVectors': True, 
            # 'showMeasurements': False, 
            # 'showKinks': True, 
            # 'showStats': False, 
            # 'wantsVarLib': False, 
            # 'hazeSlider': 0.4161512297839245, 
            # 'alignPreview': 'left', 
            # 'alignStats': 'left', 
            # 'toolsClosed': False, 
            # 'aboutClosed': True
            # }
        self.allowExtrapolation = settings["allowExtrapolation"]
        self.showSources = settings["showSources"]
        self.showVectors = settings["showVectors"]
        self.wantsVarLib = settings["wantsVarLib"]
        self.showMeasurements = settings["showMeasurements"]
        self.showKinks = settings["showKinks"]
        self.showStats = settings["showStats"]
        self.previewAlign = settings["alignPreview"]
        self.statsAlign = settings["alignStats"]
        self.longBoardHazeFactor = settings["hazeSlider"]
        self.discreteAxisNames = settings.get("_discreteAxisNames", [])
        self.continuousAxisNames = settings.get("_continuousAxisNames", [])
        self.dragDirections = settings.get('_dragDirections', {})
        self.setPreferences()
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)        

registerSubscriberEvent(
    subscriberEventName=settingsChangedEventKey,
    methodName="showSettingsChanged",
    lowLevelEventNames=[settingsChangedEventKey],
    dispatcher="roboFont",
    delay=0,
    debug=True
)

# The concept of "relevant" operator:
# it is the operator that belongs to the font that belongs to the glyph that is in the editor.
# yes, that means trouble if there are multiple designspaces open in which the current font is active.
registerSubscriberEvent(
    subscriberEventName=operatorChangedEventKey,
    methodName="relevantOperatorChanged",
    lowLevelEventNames=[operatorChangedEventKey],
    dispatcher="roboFont",
    delay=.25,
    documentation="This is sent when the glyph editor subscriber finds there is a new relevant designspace.",
    debug=True
)

registerSubscriberEvent(
    subscriberEventName=navigatorLocationChangedEventKey,
    methodName="navigatorLocationChanged",
    lowLevelEventNames=[navigatorLocationChangedEventKey],
    dispatcher="roboFont",
    delay=0,
    documentation="Posted by the Longboard Navigator Tool to the LongBoardUIController",
    debug=True
)


nt = LongboardNavigatorTool()
installTool(nt)

def launcher():
    OpenWindow(LongBoardUIController) 


if __name__ == '__main__':
  launcher()


