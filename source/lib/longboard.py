"""
    Successor to Skateboard and Superpolator
    Fast, interactive previews of glyphs in a designspace.
    
    erik@letterror.com
    May 2024
"""

import ezui
import math, time, os, traceback
import AppKit

from mojo.UI import inDarkMode

from mojo.events import (
    setActiveEventTool,
    getActiveEventTool,
    publishEvent,
    postEvent
)

from mojo.extensions import ExtensionBundle

from mojo.subscriber import (
    Subscriber,
    registerGlyphEditorSubscriber,
    unregisterGlyphEditorSubscriber,
    registerSubscriberEvent
)

from fontTools.pens.basePen import BasePen
from fontTools.ufoLib.glifLib import writeGlyphToString
from fontTools.designspaceLib import InstanceDescriptor


eventID = "com.letterror.longboardNavigator"
navigatorLocationChangedEventKey = eventID + "navigatorLocationChanged.event"
navigatorUnitChangedEventKey = eventID + "navigatorUnitChanged.event"
navigatorActiveEventKey = eventID + "navigatorActive.event"
navigatorInactiveEventKey = eventID + "navigatorInctive.event"

toolID = "com.letterror.longboard"
containerKey = toolID + ".layer"
previewContainerKey = toolID + ".preview.layer"

settingsChangedEventKey = toolID + ".settingsChanged.event"
operatorChangedEventKey = toolID + ".operatorChanged.event"
interactionSourcesLibKey = toolID + ".interactionSources"

longBoardVersion = "0.4.4"


from mojo.events import (
    installTool,
    BaseEventTool,
)


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
        self.onCurves.append((pos[0]+self.offset[0], pos[1]+self.offset[1]))
        self.startPoints.append(self._pointIndex)
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


items = [
    dict(
            textValue="Weight",
            popUpValue=0,
        ),
    dict(
            textValue="Width",
            popUpValue=1,
        ),
    dict(
            textValue="Whatever",
            popUpValue=2,
        ),
    ]










class LongBoardUIController(Subscriber, ezui.WindowController):
    #    [X] Only show designspace current font is part of @onlyShowRelevantDesignspace
    #    [X] Discrete location follows current font @useDiscreteLocationOfCurrentFont

    previewsFolderName = "previews"
    
    def build(self):
        # LongBoardUIController
        content = """
        NOOP @currentOperator
                
        | ----------------- | @table
        | xx | tf | pu | av |
        | ----------------- |

        * HorizontalStack @stack
        
        > * VerticalStack @column1
        >> (Add New Instance) @addInstance
        >> (Make Preview UFO) @makePreviewUFO
        >> (Copy Glyph to Clipboard) @copyClipboard
        >> (Reset Current Location) @resetPreview
        
        > * VerticalStack @column2
        >> [X] Show Preview Outline @showPreview
        >> [X] Show Source Outlines @showSources
        >> [X] Show Construction @showPoints
        >> [X] Show Measurements @showMeasurements
        >> [X] Allow Extrapolation @allowExtrapolation

        >> Preview Transparency
        >> --X-- Haziness @hazeSlider
        """
        descriptionData = dict(
            table=dict(
                identifier="table",
                height=120,
                items = [],
                columnDescriptions = [
                    dict(
                        identifier="textValue",
                        title="Axis",
                        width=60,
                        editable=True
                    ),
                    dict(
                        identifier="popUpValue",
                        title="Direction",
                        editable=True,
                        width=100,
                        cellDescription=dict(
                            cellType="PopUpButton",
                            cellClassArguments=dict(
                                items=["Horizontal", "Vertical", "Ignore"]
                            )
                        )
                    ),
                    dict(
                        identifier="axisWarning",
                        title="",
                        width=20,
                        editable=False
                    ),
                    dict(
                        identifier="axisValue",
                        title="Value",
                        width=60,
                        editable=False
                    ),
                ],
            ),
            currentOperator=dict(
                text="No Designspace?"
                ),
            hazeSlider=dict(
                minValue=0.08,
                maxValue=0.8,
                value=0.5
                ),
        )
        self.w = ezui.EZPanel(
            title=f"Longboard {longBoardVersion}",
            content=content,
            descriptionData=descriptionData,
            controller=self,
            size=(400, "auto")
        )
        self.operator = None
        self.previewLocation_UI = None
    
    def locationToString(self, location):
        t = []
        for name in sorted(location.keys()):
            t.append(f"{name}_{location[name]:3.2f}")
        return "_".join(t)
    
    def makePreviewUFOCallback(self, sender):
        # Make a ufo for the current preview location and open it up.
        # Why in longboard and not in DSE? Because it is more about evaluating the
        # current location than it is about adding a new instance to the designspace.
        # Make the UFO filename as Skateboard did it. 
        if self.operator is None: return
        if self.operator.path is None: return
        ufoNameMathTag = "MM"
        currentPreviewLocation = self.operator.getPreviewLocation()
        currentPreviewContinuous, currentPreviewDiscrete = self.operator.splitLocation(currentPreviewLocation)
        defaultFont = self.operator.findDefaultFont(discreteLocation=currentPreviewDiscrete)
        instanceDescriptor = InstanceDescriptor()
        instanceDescriptor.familyName = defaultFont.info.familyName
        instanceDescriptor.styleName = self.locationToString(currentPreviewLocation)
        instanceDescriptor.location = currentPreviewLocation
        ufoName = f"Preview_{instanceDescriptor.familyName}-{instanceDescriptor.styleName}_{ufoNameMathTag}.ufo"
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
            print("Something went wrong making the preview, sorry.")
            print(traceback.format_exc())
            return
        self.operator.useVarlib = useVarlibState
        self.operator.extrapolate = extrapolateState
        font.save(ufoPath)
        OpenFont(font, showInterface=True)
        
    def copyClipboardCallback(self, sender):
        # copy the text of the current preview to the clipboard
        currentPreviewLocation = self.operator.getPreviewLocation()
        name = CurrentGlyph().name
        mathGlyph = self.operator.makeOneGlyph(name, location=currentPreviewLocation)
        if mathGlyph is not None:
            clipboardGlyph = RGlyph()
            mathGlyph.extractGlyph(clipboardGlyph.asDefcon())
            clipboardGlyph.copyToPasteboard()

    def resetPreviewCallback(self, sender):
        currentPreviewLocation = self.operator.getPreviewLocation()
        currentPreviewContinuous, currentPreviewDiscrete = self.operator.splitLocation(currentPreviewLocation)
        defaultLocation = self.operator.newDefaultLocation(discreteLocation=currentPreviewDiscrete)
        self.operator.setPreviewLocation(defaultLocation)
        self.operator.changed()
        
    def addInstanceCallback(self, sender):
        currentLocation = self.operator.getPreviewLocation()
        # first check if this location already has an instance
        for instance in self.operator.instances:
            if currentLocation == instance.location:
                print(f"instance at {currentLocation} exists, cancelling")
                return
        # then add the instance
        self.operator.addInstanceDescriptor(
            designLocation = currentLocation,
            styleName = self.locationToString(currentLocation),
            )
        self.operator.changed()
        
    def tableEditCallback(self, sender):
        # LongBoardUIController
        # callback for the interaction sources table
        # maybe it can have a less generic name than "tableEditCallback"
        # tableEditCallback [{'textValue': 'weight', 'popUpValue': 0}]
        # @@
        prefs = []
        for axis in self.w.getItem("table").get():
            axisName = axis['textValue']
            if axis['popUpValue'] == 0:     # horizontal
                prefs.append((axisName, "horizontal"))
            elif axis['popUpValue'] == 1:     # vertical
                prefs.append((axisName, "vertical"))
            elif axis['popUpValue'] == 2:     # vertical
                prefs.append((axisName, "ignore"))
        # where is the operatr coming from?
        if self.operator is not None:
            self.operator.lib[interactionSourcesLibKey] = prefs
            self.previewLocation_UI = self.operator.getPreviewLocation()
            self.operator.changed()
        else:
            print("tableEditCallback pref not set, no operator", pref)
        
    def started(self):
        # LongBoardUIController
        self.w.open()
        registerGlyphEditorSubscriber(LongboardEditorView)

    def destroy(self):
        # LongBoardUIController
        unregisterGlyphEditorSubscriber(LongboardEditorView)

    def checkAxisValueInExtremes(self, operator, axisName, axisValue):
        # check if the axis Value for axis name is in between minimum and maximum
        for axisRecord in operator.axes:
            if axisRecord.name == axisName:
                aD_minimum, aD_default, aD_maximum =  operator.getAxisExtremes(axisRecord)
                if aD_minimum <= axisValue <= aD_maximum:
                    return True
        return False
        
    def navigatorLocationChanged(self, info):
        # LongBoardUIController
        # @@ receive notifications about the navigator location changing.
        # scale mouse movement to "increment units"
        # operatpr has the axes data
        # glypheditor has the viewscale
        # UI has the axis masks
        # @@ sort extrapolation here?
        # @@ or post the filter table when it changes
        # @@ and handle everything in glypheditor?
        view = info["lowLevelEvents"][-1].get('view')
        offset = view.offset()
        viewScale = view.scale()
        popOptions = ['horizontal', 'vertical', None]
        data = info["lowLevelEvents"][-1].get('data')
        nav = data['horizontal'], data['vertical']

        # @@_mouse_drag_updating_data
        # the
        editorObject = data['editor']

        unit = {}
        unitScale = 100
        for axis in self.w.getItem("table").get():
            name = axis['textValue']
            if axis['popUpValue'] == 0:     # horizontal
                #unit[name] = unitScale/(data['horizontal'] / viewScale)
                unit[name] = data['horizontal']
            elif axis['popUpValue'] == 1:     # vertical
                #unit[name] = unitScale/(data['vertical'] / viewScale)
                unit[name] = data['vertical']
            # and for ignore we don't pass anything
        extreme = []      
        for axisName, offset in unit.items():
            value = editorObject.previewLocation_dragging[axisName]
            value += .05 * offset
            editorObject.previewLocation_dragging[axisName] = value
        # check for clipping here
        if self.w.getItem("allowExtrapolation").get() == 0:
            editorObject.previewLocation_dragging = self.operator.clipDesignLocation(editorObject.previewLocation_dragging)
        editorObject.updateInstanceOutline()
        
    def relevantOperatorChanged(self, info):
        # LongBoardUIController
        # @@ from https://robofont.com/documentation/reference/api/mojo/mojo-subscriber/#mojo.subscriber.registerSubscriberEvent
        operator = info["lowLevelEvents"][0].get('operator')
        if operator is None: return
        currentLocation = operator.getPreviewLocation()
        # @@ ask operator for the interaction sources stored in its lib
        if operator is not None:
            items = []
            prefs = []
            interactionSourcesPref = operator.lib.get(interactionSourcesLibKey)
            #interactionSourcesPref = None    # reset prefs
            if interactionSourcesPref is not None:
                for axisName, interaction in interactionSourcesPref:
                    v = 2
                    if interaction == "horizontal":
                        v = 0
                    elif interaction == "vertical":
                        v = 1
                    axisValue = currentLocation.get(axisName, '-')
                    axisWarning = ""
                    if axisValue is not None and axisValue != "-":
                        if self.checkAxisValueInExtremes(operator, axisName, axisValue):
                            axisWarning = ""
                        else:
                            axisWarning = "⚠️"
                    items.append(dict(textValue=axisName, popUpValue=v, axisWarning=axisWarning, axisValue=f"{axisValue:3.2f}"))
            else:
                v = 0
                for axisObject in operator.getOrderedContinuousAxes():
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
                operator.lib[interactionSourcesLibKey] = prefs
                operator.changed()
            self.w.getItem("table").set(items)
            self.operator = operator
            if operator.path is not None:
                fileName = os.path.basename(operator.path)
                self.w.setItemValue("currentOperator", f"Showing: {fileName}")
            else:
                self.w.setItemValue("currentOperator", f"Unsaved Designspace")

    def showPreviewCallback(self, sender):
        # LongBoardUIController
        value = sender.get()
        postEvent(settingsChangedEventKey, showPreview=value)

    def showSourcesCallback(self, sender):
        # LongBoardUIController
        value = sender.get()
        postEvent(settingsChangedEventKey, showSources=value)

    def showPointsCallback(self, sender):
        # LongBoardUIController
        value = sender.get()
        postEvent(settingsChangedEventKey, showPoints=value)
    
    def allowExtrapolationCallback(self, sender):
        # LongBoardUIController
        value = sender.get()
        postEvent(settingsChangedEventKey, extrapolate=value)
        
    def showMeasurementsCallback(self, sender):
        # LongBoardUIController
        value = sender.get()
        postEvent(settingsChangedEventKey, showMeasurements=value)
    
    #def useDiscreteLocationOfCurrentFontCallback(self, sender):
    #    # LongBoardUIController
    #    value = sender.get()
    #    postEvent(settingsChangedEventKey, useDiscreteLocationOfCurrentFont=value)

    def hazeSliderCallback(self, sender):
        # LongBoardUIController
        value = sender.get()
        postEvent(settingsChangedEventKey, longBoardHazeFactor=value)








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
            fillModel = (.5,.5,.5, previewHaze)
            strokeModel = (1,1,1, haze)
        else:
            fillModel = (.5,.5,.5, previewHaze)
            strokeModel = (0,0,0,haze)
        self.measurementStrokeColor = strokeModel
        self.measurementFillColor = strokeModel
        self.sourceStrokeColor = strokeModel
        self.instanceStrokeColor = strokeModel
        self.vectorStrokeColor = strokeModel
        #self.previewFillColor = fillModel
        self.previewStrokeColor = fillModel
        
    def setPreferences(self):
        # LongboardEditorView
        self.darkMode = inDarkMode()
        self.measurementMarkerSize = 5
        self.measurementStrokeWidth = 1
        self.measurementStrokeDash = (1, 3)
        self.previewStrokeDash = (1, 3)
        self.vectorStrokeDash = (1, 3)
        self.sourceStrokeDash = (30, 2)
        self.instanceStrokeWidth = 0.5
        self.markerSize = 3
        self.measureLineCurveOffset = 50
        self.marginLineHeight = 50    # the height of the margin line in the preview
        self.setColors()
    
    def build(self):
        # LongboardEditorView
        self.setPreferences()
        self.currentOperator = None
        self.allowExtrapolation = True    # should we show extrapolation
        self.extrapolating = False    # but are we extrapolating?
        self.showPreview = True
        self.showSources = False
        self.centerAllGlyphs = True
        self.showPoints = True
        self.showMeasurements = True
        self.useDiscreteLocationOfCurrentFont = True
        self.navigatorToolPosition = None
        self.navigatorToolProgress = None
        self.dragging = False
        self.preparePreview = False
        self._lastEventTime = None
        self.previewLocation_dragging = None    # local editing copy of the DSE2 preview location

        glyphEditor = self.getGlyphEditor()
        # container for all layers in the editor window
        self.editorContainer = glyphEditor.extensionContainer(containerKey, location="middleground")
        # container for all layers in the preview window
        # note: different use of the word Preview
        self.previewContainer = glyphEditor.extensionContainer(previewContainerKey, location="preview")

        self.previewPathLayer = self.previewContainer.appendPathSublayer(
            strokeColor = self.previewStrokeColor,
            #strokeDash = self.previewStrokeDash,
            strokeWidth = 1,
            fillColor = None,
        )

        self.instancePathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.instanceStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None
        )
        self.sourcesPathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.sourceStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None,
            strokeDash=self.vectorStrokeDash,
            strokeCap="round",
        )
        self.pointsPathLayer = self.editorContainer.appendLineSublayer(
            strokeColor=self.vectorStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None,
            strokeDash=self.vectorStrokeDash,
            strokeCap="round",
        )
        self.marginsPathLayer = self.editorContainer.appendLineSublayer(
            strokeColor=self.vectorStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None,
            strokeDash=self.vectorStrokeDash,
            strokeCap="round",
        )
        self.sourcesMarkerLayer = self.editorContainer.appendSymbolSublayer(
            fillColor = self.sourceStrokeColor,
        )
        self.sourcesMarkerLayer.setImageSettings(
            dict(
                name="rectangle",
                size=(self.markerSize, self.markerSize),
                fillColor=self.sourceStrokeColor
            )
        )
        self.instanceMarkerLayer = self.editorContainer.appendSymbolSublayer(
            fillColor = self.sourceStrokeColor,
        )
        self.instanceMarkerLayer.setImageSettings(
            dict(
                name="rectangle",
                size=(self.markerSize, self.markerSize),
                fillColor=self.sourceStrokeColor
            )
        )
        self.measurementsIntersectionsLayer = self.editorContainer.appendLineSublayer(
            strokeColor=self.measurementStrokeColor,
            strokeWidth=self.measurementStrokeWidth,
            strokeDash = self.measurementStrokeDash,
            fillColor = None,
        )
        self.measurementMarkerLayer = self.editorContainer.appendSymbolSublayer(
        )
        self.measurementMarkerLayer.setImageSettings(
            dict(
                name="oval",
                size=(self.measurementMarkerSize, self.measurementMarkerSize),
                fillColor=self.measurementStrokeColor
            )
        )
        self.measurementTextLayer = self.editorContainer.appendBaseSublayer()

    def glyphEditorWillShowPreview(self, info):
        self.preparePreview = True
        self.updateInstanceOutline()
    
    def glyphEditorWillHidePreview(self, info):
        self.preparePreview = False
        self.updateInstanceOutline()
        
    def glyphEditorDidMouseDown(self, info):
        # LongboardEditorView
        # starting drag
        self.dragging = True
        self.setColors(active=True)
        self.navigatorToolPosition = None
        # get the designspace current location and make a local copy
        # then update the local copy while we're dragging
        self.previewLocation_dragging = self.operator.getPreviewLocation()
        self._lastEventTime = None
        self.updateSourcesOutlines()
        self.updateInstanceOutline()
    
    def glyphEditorDidMouseUp(self, info):
        # LongboardEditorView
        # ending drag
        self.dragging = False
        self.setColors(active=False)
        self.navigatorToolPosition = None
        self._lastEventTime = None
        self.updateInstanceOutline()
        self.operator.setPreviewLocation(self.previewLocation_dragging)
        
    def glyphEditorDidMouseDrag(self, info):
        # LongboardEditorView
        # get the mouse drag from the navigator tool
        # We need the view.scale to "unscale" the mouse delta.
        # Otherwise this could have gone straight to the UI.
        if info["lowLevelEvents"][-1]["tool"].__class__.__name__ != "LongboardNavigatorTool": return
        if not self.operator: return
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
        # @@
        # this is the data we're going to send to the UI
        # the UI knows about the directions and the units
        # we're also going to pass the editor object
        # because the UI needs to call a redraw afterwards
        
        # @@_mouse_drag_updating_data
        data = {
                'editor': self, 
                'previewLocation': self.previewLocation_dragging,
                'horizontal': self.navigatorToolProgress[0]/timeSinceLastEvent,
                'vertical': self.navigatorToolProgress[1]/timeSinceLastEvent,
                }

        publishEvent(navigatorLocationChangedEventKey, data=data)

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
        glyphEditor = self.getGlyphEditor()
        for key in [containerKey, previewContainerKey]:
            container = glyphEditor.extensionContainer(key)
            container.clearSublayers()

        self.instancePathLayer.clearSublayers()
        self.previewPathLayer.clearSublayers()
        self.instanceMarkerLayer.clearSublayers()
        self.marginsPathLayer.clearSublayers()
        self.measurementMarkerLayer.clearSublayers()
        self.measurementsIntersectionsLayer.clearSublayers()
        self.measurementTextLayer.clearSublayers()

        self.updateSourcesOutlines()
        self.updateInstanceOutline()
        self.currentOperator = None
        
    def glyphEditorDidSetGlyph(self, info):
        # LongboardEditorView
        # when the glyph in the editor has changed
        # get the previewlocation from the designspace
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        ds = self.operator
        previewLocation_dragging = ds.getPreviewLocation()
        if previewLocation_dragging is None:
            previewLocation_dragging = ds.newDefaultLocation()
            ds.setPreviewLocation(previewLocation_dragging)
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
        self.updateSourcesOutlines()
        self.updateInstanceOutline()

    #    designspaceEditorSourcesDidAddSource
    #    designspaceEditorSourcesDidRemoveSource
    #    designspaceEditorSourcesDidChanged
    
    #    designspaceEditorAxesDidChange
    #    designspaceEditorAxesDidAddAxis
    #    designspaceEditorAxesDidRemoveAxis
    
    def designspaceEditorSourceGlyphDidChange(self, info):
        # LongboardEditorView
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        self.updateInstanceOutline()

    def checkExtrapolation(self, location):
        # check if the axis Value for axis name is in between minimum and maximum
        if self.operator is None: return False
        axes = {ar.name: ar for ar in self.operator.axes}
        for axisName in location:
            axisRecord = axes.get(axisName)
            if axisRecord is None: continue
            aD_minimum, aD_default, aD_maximum =  self.operator.getAxisExtremes(axisRecord)
            if not (aD_minimum <= location.get(axisRecord.name) <= aD_maximum): 
                return True
        return False
        
    def designspaceEditorPreviewLocationDidChange(self, info):
        # LongboardEditorView
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        loc = self.previewLocation_dragging = info['location']
        # check extrapolations
        currentPreviewContinuous, currentPreviewDiscrete = self.operator.splitLocation(loc)
        self.extrapolating = self.checkExtrapolation(currentPreviewContinuous)
        self.updateInstanceOutline()
    
    def glyphDidChangeMeasurements(self, info):
        # LongboardEditorView
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        self.updateInstanceOutline()
    
    def drawMeasurements(self, editorGlyph, previewShift, previewGlyph):
        # LongboardEditorView
        # draw intersections for the current measuring beam and the current preview
        for m in editorGlyph.measurements:
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
                jumperLayer = self.measurementsIntersectionsLayer.appendPathSublayer(
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
                symbolLayer = self.measurementMarkerLayer.appendSymbolSublayer(position=mp1)
                symbolLayer.setImageSettings(
                    dict(
                        name="oval",
                        size=(self.measurementMarkerSize, self.measurementMarkerSize),
                        fillColor=self.measurementFillColor
                        )
                    )
                symbolLayer = self.measurementMarkerLayer.appendSymbolSublayer(position=mp2)
                symbolLayer.setImageSettings(
                    dict(
                        name="oval",
                        size=(self.measurementMarkerSize, self.measurementMarkerSize),
                        fillColor=self.measurementFillColor
                        )
                    )
                # draw the measurement distance text
                textPos = .5*(mp1[0]+mp2[0])+needlex, .5*(mp1[1]+mp2[1])+needley
                dist = math.hypot(mp1[0]-mp2[0], mp1[1]-mp2[1])
                #$$
                textLayer= self.measurementTextLayer.appendTextLineSublayer(
                    position=textPos,
                    pointSize=11,
                    fillColor=self.measurementFillColor,
                    horizontalAlignment="center",
                    )
                textLayer.setText(f"{dist:3.2f}")
        
    def updateSourcesOutlines(self):
        # LongboardEditorView
        # everything necessary to update the sources, not time sensitive
        if self.darkMode != inDarkMode():
            self.darkMode = not self.darkMode
        self.sourcesPathLayer.clearSublayers()
        self.pointsPathLayer.clearSublayers()
        self.sourcesMarkerLayer.clearSublayers()
        if self.operator is None:
            return
        ds = self.operator
        editorGlyph = self.getGlyphEditor().getGlyph()
        cpCurrent = CollectorPen(glyphSet=editorGlyph.font)
        sourcePens = []
        editorGlyph.draw(cpCurrent)

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


        ds = self.operator
        items, unicodes = ds.collectSourcesForGlyph(glyphName=editorGlyph.name, decomposeComponents=True, discreteLocation=discreteLocationForCurrentSource)
        for item in items:
            loc, srcMath, thing = item
            sourcePen = CollectorPen(glyphSet={})
            # do not draw the master we're drawing in
            # 
            if loc==continuousLocationForCurrentSource: continue
            srcGlyph = RGlyph()
            srcMath.extractGlyph(srcGlyph.asDefcon())
            if self.centerAllGlyphs:
                xMin, yMin, xMax, yMax = srcGlyph.bounds
                # centering
                shift = .5*editorGlyph.width-.5*srcGlyph.width
                srcGlyph.moveBy((shift, 0))
            srcGlyph.draw(sourcePen)
            sourcePens.append(sourcePen)

        if self.showSources:
            path = srcGlyph.getRepresentation("merz.CGPath")
            layer = self.sourcesPathLayer.appendPathSublayer(
                fillColor=None,
                strokeColor=self.sourceStrokeColor,
                strokeWidth=self.instanceStrokeWidth,
                strokeDash=self.sourceStrokeDash,
                strokeCap="round",
                )
            layer.setPath(path)

        if self.showPoints:
            # draw the oncurve point vectors
            for s in sourcePens:
                for a, b in zip(cpCurrent.onCurves, s.onCurves):
                    lineLayer = self.pointsPathLayer.appendLineSublayer(
                        startPoint=a,
                        endPoint=b,
                        strokeWidth=self.instanceStrokeWidth,
                        strokeColor=self.vectorStrokeColor,
                        strokeDash=self.vectorStrokeDash,
                        strokeCap="round",
                    )
                    symbolLayer = self.sourcesMarkerLayer.appendSymbolSublayer(position=a)
                    symbolLayer.setImageSettings(
                        dict(
                            name="oval",
                            size=(self.markerSize, self.markerSize),
                            fillColor=self.vectorStrokeColor
                            )
                        )
                    symbolLayer = self.sourcesMarkerLayer.appendSymbolSublayer(position=b)
                    symbolLayer.setImageSettings(
                        dict(
                            name="oval",
                            size=(self.markerSize, self.markerSize),
                            fillColor=self.vectorStrokeColor
                            )
                        )

        if self.showPoints:
            # show the off curve point vectors
            for s in sourcePens:
                for a, b in zip(cpCurrent.offCurves, s.offCurves):
                    lineLayer = self.pointsPathLayer.appendLineSublayer(
                        startPoint=a,
                        endPoint=b,
                        strokeWidth=self.instanceStrokeWidth,
                        strokeColor=self.vectorStrokeColor,
                        strokeDash=self.vectorStrokeDash,
                        strokeCap="round",
                    )
                    symbolLayer = self.sourcesMarkerLayer.appendSymbolSublayer(position=a)
                    symbolLayer.setImageSettings(
                        dict(
                            name="oval",
                            size=(self.markerSize, self.markerSize),
                            fillColor=self.sourceStrokeColor
                            )
                        )
                    symbolLayer = self.sourcesMarkerLayer.appendSymbolSublayer(position=b)
                    symbolLayer.setImageSettings(
                        dict(
                            name="oval",
                            size=(self.markerSize, self.markerSize),
                            fillColor=self.sourceStrokeColor
                            )
                        )
        
    def updateInstanceOutline(self):
        # LongboardEditorView
        # everything necessary to update the preview, time sensitive
        if self.darkMode != inDarkMode():
            self.darkMode = not self.darkMode
        self.instancePathLayer.clearSublayers()
        self.previewPathLayer.clearSublayers()
        self.instanceMarkerLayer.clearSublayers()
        self.marginsPathLayer.clearSublayers()

        self.measurementMarkerLayer.clearSublayers()
        self.measurementsIntersectionsLayer.clearSublayers()
        self.measurementTextLayer.clearSublayers()
        
        if self.operator is None:
            return
        if self.previewLocation_dragging is None:
            return

        ds = self.operator
        editorGlyph = self.getGlyphEditor().getGlyph()
        #cpCurrent = CollectorPen(glyphSet=editorGlyph.font)
        sourcePens = []
        #editorGlyph.draw(cpCurrent)
            
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
            mathGlyph = ds.makeOneGlyph(editorGlyph.name, location=self.previewLocation_dragging)
            if editorGlyph is None or mathGlyph is None:
                path = None
                return
            
            previewGlyph = RGlyph()
            mathGlyph.extractGlyph(previewGlyph.asDefcon())
            shift = 0
            if self.centerAllGlyphs:
                xMin, yMin, xMax, yMax = previewGlyph.bounds
                shift = .5*editorGlyph.width-.5*previewGlyph.width
                previewGlyph.moveBy((shift, 0))
            cpPreview = CollectorPen(glyphSet={})
            previewGlyph.draw(cpPreview)
            if self.showMeasurements:
                self.drawMeasurements(editorGlyph,  shift, previewGlyph)
            if self.showPreview:
                path = previewGlyph.getRepresentation("merz.CGPath")
                # 01 stroke instance path in the editor layer
                layer = self.instancePathLayer.appendPathSublayer(
                    fillColor=None,
                    strokeColor=self.instanceStrokeColor,
                    strokeWidth=self.instanceStrokeWidth,
                    strokeDash=self.sourceStrokeDash,
                    strokeCap="round",
                    )
                layer.setPath(path)
                
                # set the path in the preview layer as well
                layer = self.previewPathLayer.appendPathSublayer(
                    strokeColor = self.previewStrokeColor,
                    #strokeDash = self.previewStrokeDash,
                    strokeWidth = 1,
                    fillColor = None,
                    )
                layer.setPath(path)

                if self.showPoints:
                    # 03 on curve markers on instance outline
                    for m in cpPreview.onCurves:
                        symbolLayer = self.instanceMarkerLayer.appendSymbolSublayer(position=m)
                        symbolLayer.setImageSettings(
                            dict(
                                name="oval",
                                size=(self.markerSize, self.markerSize),
                                fillColor=self.instanceStrokeColor
                                )
                            )
                    # 04 off curve markers on instance outline
                    for m in cpPreview.offCurves:
                        symbolLayer = self.instanceMarkerLayer.appendSymbolSublayer(position=m)
                        symbolLayer.setImageSettings(
                            dict(
                                name="oval",
                                size=(self.markerSize, self.markerSize),
                                fillColor=self.instanceStrokeColor
                                )
                            )
                    # 05 draw small lines for the left and right margins of the instance outline
                    #@@
                    # show the margin lines at the expected angle
                    italicSlantOffset = editorGlyph.font.lib.get(self.italicSlantOffsetKey, 0)
                    a = editorGlyph.font.info.italicAngle
                    if a is None:
                        a = 0
                    angle = math.radians(90+a)
                    dx = math.cos(angle) * self.marginLineHeight
                    a = (shift-dx+italicSlantOffset, -self.marginLineHeight)
                    b = (shift+italicSlantOffset, 0)
                    shiftRight = .5*editorGlyph.width +.5*previewGlyph.width
                    c = (shiftRight-dx+italicSlantOffset, -self.marginLineHeight)
                    d = (shiftRight+italicSlantOffset, 0)
                    leftMargin = self.marginsPathLayer.appendLineSublayer(
                        startPoint=a,
                        endPoint=b,
                        strokeColor=self.vectorStrokeColor,
                        strokeWidth=2, #self.instanceStrokeWidth,
                        fillColor = None,
                        strokeDash= self.vectorStrokeDash,
                        strokeCap="round",
                    )
                    rightMargin = self.marginsPathLayer.appendLineSublayer(
                        startPoint=c,
                        endPoint=d,
                        strokeColor=self.vectorStrokeColor,
                        strokeWidth= 2,    #self.instanceStrokeWidth,
                        fillColor = None,
                        strokeDash=self.vectorStrokeDash,
                        strokeCap="round",
                    )

                
    def showSettingsChanged(self, info):
        # LongboardEditorView
        if info["extrapolate"] is not None:
            self.allowExtrapolation = info["extrapolate"]
        if info["showPreview"] is not None:
            self.showPreview = info["showPreview"]
        if info["showSources"] is not None:
            self.showSources = info["showSources"]
        if info["showPoints"] is not None:
            self.showPoints = info["showPoints"]
        if info["showMeasurements"] is not None:
            self.showMeasurements = info["showMeasurements"]
        if info["longBoardHazeFactor"] is not None:
            self.longBoardHazeFactor = info["longBoardHazeFactor"]
        self.setPreferences()
        self.updateSourcesOutlines()
        self.updateInstanceOutline()

def uiSettingsExtractor(subscriber, info):
    # crikey there as to be a more efficient way to do this.
    info["extrapolate"] = None
    info["showPreview"] = None
    info["showSources"] = None
    info["showPoints"] = None
    info["showMeasurements"] = None
    #info["useDiscreteLocationOfCurrentFont"] = None
    info["longBoardHazeFactor"] = None
    for lowLevelEvent in info["lowLevelEvents"]:
        info["extrapolate"] = lowLevelEvent.get("extrapolate")
        info["showPreview"] = lowLevelEvent.get("showPreview")
        info["showSources"] = lowLevelEvent.get("showSources")
        info["showPoints"] = lowLevelEvent.get("showPoints")
        info["showMeasurements"] = lowLevelEvent.get("showMeasurements")
        #info["useDiscreteLocationOfCurrentFont"] = lowLevelEvent.get("useDiscreteLocationOfCurrentFont")
        info["longBoardHazeFactor"] = lowLevelEvent.get("longBoardHazeFactor")




registerSubscriberEvent(
    subscriberEventName=settingsChangedEventKey,
    methodName="showSettingsChanged",
    lowLevelEventNames=[settingsChangedEventKey],
    eventInfoExtractionFunction=uiSettingsExtractor,
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
    delay=.5,
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




OpenWindow(LongBoardUIController) 




