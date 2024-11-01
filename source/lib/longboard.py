"""
    Successor to Skateboard and Superpolator
    Fast, interactive previews of glyphs in a designspace.
    
    erik@letterror.com
    October 2024
"""

import importlib
import ufoProcessor.ufoOperator
importlib.reload(ufoProcessor.ufoOperator)
import ezui
import math, time, os, traceback
import AppKit

import merz

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

longBoardVersion = "1.1"


from mojo.events import (
    installTool,
    BaseEventTool,
)


def glyphEditorIsInZoom():
    # detect if we're zooming at the moment
    tool = getActiveEventTool()
    return bool(tool._zooming)

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




class LongBoardUIController(Subscriber, ezui.WindowController):
    #    [X] Only show designspace current font is part of @onlyShowRelevantDesignspace
    #    [X] Discrete location follows current font @useDiscreteLocationOfCurrentFont

    previewsFolderName = "previews"
    
    def build(self):
        # LongBoardUIController
        content = """
        NOOP @currentOperator
                
        | ----------------- | @axesTable
        | xx | tf | pu | av |
        | ----------------- |

        | ----------------- | @locationTable
        | xx | tf | pu | av |
        | ----------------- |

        * HorizontalStack @stack
        
        > * VerticalStack @column1
        >> (Add New Instance) @addInstance
        >> (Make Preview UFO) @makePreviewUFO
        >> (Copy Glyph to Clipboard) @copyClipboard
        >> (Reset Current Location) @resetPreview
        
        > * VerticalStack @column2
        #>> [X] Show Preview @showPreview
        >> [ ] Show Sources @showSources
        >> [ ] Show Vectors @showPoints
        >> [X] Show Measurements @showMeasurements
        >> [ ] Allow Extrapolation @allowExtrapolation

        >> Preview Transparency
        >> --X-- Haziness @hazeSlider
        """
        descriptionData = dict(
            axesTable=dict(
                height=100,
                width=500,
                items = [],
                columnDescriptions = [
                    dict(
                        identifier="textValue",
                        title="Axis",
                        #width=60,
                        editable=True
                    ),
                    dict(
                        identifier="popUpValue",
                        title="🔀",
                        editable=True,
                        #width=100,
                        cellDescription=dict(
                            cellType="PopUpButton",
                            cellClassArguments=dict(
                                items=["Horizontal", "Vertical", "Ignore"]
                            )
                        )
                    ),
                    # dict(
                    #     identifier="axisWarning",
                    #     title="",
                    #     width=20,
                    #     editable=False
                    # ),
                    dict(
                        identifier="axisValue",
                        title="Value",
                        #width=100,
                        editable=True,
                        cellDescription=dict(
                            attributes = dict(fillColor = (1,0,0, 1)),
                        ),
                    ),
                ],
            ),

            locationTable=dict(
                height=150,
                width=500,
                items = [],
                columnDescriptions = [
                    # dict(
                    #     identifier="locationType",
                    #     title="Type",
                    #     #width=60,
                    #     editable=False
                    # ),
                    dict(
                        identifier="locationName",
                        title="🏷️",
                        width=190,
                        editable=False
                    ),
                    dict(
                        identifier="locationText",
                        title="📍",
                        width=190,
                        editable=False
                    ),
                ],
            ),

            currentOperator=dict(
                text="Looking for Designspace and Current Glyph"
                ),
            hazeSlider=dict(
                minValue=0.08,
                maxValue=0.8,
                value=0.5
                ),
        )
        self.w = ezui.EZWindow(
            title=f"Longboard",
            content=content,
            descriptionData=descriptionData,
            controller=self,
            size=(500, "auto")
        )
        self.operator = None
        self.axisValueDigits = 3
    
    def locationToString(self, location):
        t = []
        for name in sorted(location.keys()):
            t.append(f"{name}_{location[name]:3.2f}")
        return "_".join(t)
    
    def designspaceEditorDidCloseDesignspace(self, info):
        #print('designspaceEditorDidCloseDesignspace', info)
        self.w.getItem("axesTable").set([])
        self.w.getItem("locationTable").set([])
        #@@
        self.w.setItemValue("currentOperator", "Looking for Designspace and Current Glyph")
        self.close()
        #if self.operator is None: return
        #if self.operator.path is None: return
        
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
        #print('done generating')
        self.operator.useVarlib = useVarlibState
        self.operator.extrapolate = extrapolateState
        font.save(ufoPath)
        font.close()
        OpenFont(ufoPath, showInterface=True)
        
    def copyClipboardCallback(self, sender):
        # copy the text of the current preview to the clipboard
        currentPreviewLocation = self.operator.getPreviewLocation()
        glyph = CurrentGlyph()
        if glyph is None: return
        name = glyph.name
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
    
    #def locationTableEditCallback(self, sender):
    #    print('locationTableCallback', sender)

    def locationTableSelectionCallback(self, sender):
        #print('locationTableSelectionCallback', sender.getSelectedItems())
        selectedLocations = sender.getSelectedItems()
        first = selectedLocations[0]
        firstLocation = first.get('locationDict')
        if firstLocation is not None:
            self.operator.setPreviewLocation(firstLocation)
            self.operator.changed()
                        
    def axesTableEditCallback(self, sender):
        #print('axesTableEditCallback', sender)
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
        #print("locationFromTable", locationFromTable)
        # can we broadcast this new location to the world?
        if self.operator is not None:
            self.operator.lib[interactionSourcesLibKey] = prefs
            currentPreviewLocation = self.operator.getPreviewLocation()
            currentPreviewLocation.update(locationFromTable)
            self.operator.setPreviewLocation(currentPreviewLocation)
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
        # receive notifications about the navigator location changing.
        # scale mouse movement to "increment units"
        # operatpr has the axes data
        # glypheditor has the viewscale
        # UI has the axis masks
        # sort extrapolation here?
        # or post the filter table when it changes
        # and handle everything in glypheditor?
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
        for axis in self.w.getItem("axesTable").get():
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
            if axisName in editorObject.previewLocation_dragging:
                value = editorObject.previewLocation_dragging[axisName]
                value += .05 * offset
                editorObject.previewLocation_dragging[axisName] = value
        # check for clipping here
        if self.w.getItem("allowExtrapolation").get() == 0:
            editorObject.previewLocation_dragging = self.operator.clipDesignLocation(editorObject.previewLocation_dragging)
        # update the instance outline, but not a rebuild, just move the points
        editorObject.updateInstanceOutline(rebuild=False)
    
    def relevantOperatorChanged(self, info):
        # LongBoardUIController
        # @@ from https://robofont.com/documentation/reference/api/mojo/mojo-subscriber/#mojo.subscriber.registerSubscriberEvent
        #print("relevantOperatorChanged", info)
        operator = info["lowLevelEvents"][0].get('operator')
        glyph = info["lowLevelEvents"][0].get('glyph')
        if operator is None:
            print('No Operator found.')
            return
        glyphName = None
        if glyph is not None:
            glyphName = glyph.name
        currentLocation = operator.getPreviewLocation()
        # ask operator for the interaction sources stored in its lib
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
                            axisWarning = "😨"
                    items.append(dict(textValue=axisName, popUpValue=v, axisWarning=axisWarning, axisValue=round(axisValue, self.axisValueDigits)))
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
            self.w.getItem("axesTable").set(items)
            # collect interesting locations here
            interesting = []
            for src in operator.sources:
                loc = dict(
                    #locationType="Source", 
                    locationName = os.path.basename(src.path),
                    locationText = operator.nameLocation(src.location),
                    locationDict = src.location,
                    )
                interesting.append(loc)
            for instance in operator.instances:
                loc = dict(
                    #locationType="Source", 
                    locationName=f'{instance.familyName} {instance.styleName}',
                    locationText = operator.nameLocation(instance.location),
                    locationDict = instance.location,
                    )
                interesting.append(loc)
            self.w.setItemValue("locationTable", interesting)
            #
            self.operator = operator
            if operator.path is not None:
                fileName = os.path.basename(operator.path)
                if glyphName is not None:
                    self.w.setItemValue("currentOperator", f"Showing: {glyphName} from {fileName}")
                else:
                    self.w.setItemValue("currentOperator", f"Showing: {fileName}. No Glyph.")
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
        #print('setColors', active)
        if self.darkMode:
            fillModel = (.5,.5,.5, .8*haze)
            strokeModel = (1,1,1, haze)
            vectorModel = (.8,.8,.8, .8*haze)
            self.measurementStrokeColor = (0, 1, 1, haze)
            self.measurementFillColor = (0, 1, 1, haze)
        else:
            fillModel = (.5,.5,.5, previewHaze)
            strokeModel = (0,0,0,haze)
            vectorModel = (.8,.8,.8, previewHaze)
            self.measurementStrokeColor = (0, .25, .5, haze)
            self.measurementFillColor = (0, .25, .5, haze)
        self.sourceStrokeColor = vectorModel
        self.instanceStrokeColor = strokeModel
        self.vectorStrokeColor = vectorModel
        self.previewFillColor = fillModel
        self.previewStrokeColor = strokeModel
        
    def setPreferences(self):
        # LongboardEditorView
        self.darkMode = inDarkMode()
        self.measurementMarkerSize = 2
        self.measurementStrokeWidth = 1
        self.measurementStrokeDash = (1, 3)
        self.previewStrokeDash = (4, 4)
        self.vectorStrokeDash = (2, 2)
        self.sourceStrokeDash = (1, 2)
        self.instanceStrokeDash = (5, 2)
        self.instanceStrokeWidth = 1
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
        self.showSources = False
        self.sourcePens = []
        self.sourceGlyphs = []
        self.centerAllGlyphs = True
        self.showPoints = False
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
        self.pointsPathLayer = self.editorContainer.appendPathSublayer(
            strokeColor=self.vectorStrokeColor,
            strokeWidth=self.instanceStrokeWidth,
            fillColor = None,
            strokeDash=self.vectorStrokeDash,
            strokeCap="round",
        )
        self.marginsPathLayer = self.editorContainer.appendBaseSublayer()
        self.instanceMarkerLayer = self.editorContainer.appendBaseSublayer()
        self.measurementsIntersectionsLayer = self.editorContainer.appendBaseSublayer()
        self.measurementMarkerLayer = self.editorContainer.appendBaseSublayer()
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
        #print('glyphEditorDidMouseDown')
        ## @@ 
        if info["lowLevelEvents"][-1]["tool"].__class__.__name__ != "LongboardNavigatorTool": return
        self.dragging = True
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
        self.updateInstanceOutline()
        self.operator.setPreviewLocation(self.previewLocation_dragging)
        
    def glyphEditorDidMouseDrag(self, info):
        # LongboardEditorView
        # get the mouse drag from the navigator tool
        # We need the view.scale to "unscale" the mouse delta.
        # Otherwise this could have gone straight to the UI.
        if info["lowLevelEvents"][-1]["tool"].__class__.__name__ != "LongboardNavigatorTool": return
        if not self.operator: return
        
        #zooming = glyphEditorIsInZoom()
        #if zooming:
        #    print('glyphEditorDidMouseDrag zooming')

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
        self.editorContainer.clearSublayers()
        self.previewContainer.clearSublayers()
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
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)

    #    designspaceEditorSourcesDidAddSource
    #    designspaceEditorSourcesDidRemoveSource
    #    designspaceEditorSourcesDidChanged
    
    #    designspaceEditorAxesDidChange
    #    designspaceEditorAxesDidAddAxis
    #    designspaceEditorAxesDidRemoveAxis
    
    def designspaceEditorSourceGlyphDidChange(self, info):
        # LongboardEditorView
        # rebuild all the layers
        relevant, font, ds = self.relevantForThisEditor(info)
        if not relevant:
            return
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)

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
                textPos = .5*(mp1[0]+mp2[0])+needlex, .5*(mp1[1]+mp2[1])+needley
                dist = math.hypot(mp1[0]-mp2[0], mp1[1]-mp2[1])
                #$$
                # layer append or update? 4
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
                measurementTextLayer.setText(f"{dist:3.2f}")
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
            #if loc==continuousLocationForCurrentSource: continue
            sourceGlyph = RGlyph()
            srcMath.extractGlyph(sourceGlyph.asDefcon()) # mathglyph to sourceGlyph
            if self.centerAllGlyphs:
                xMin, yMin, xMax, yMax = sourceGlyph.bounds
                # centering
                shift = .5*editorGlyph.width-.5*sourceGlyph.width
                sourceGlyph.moveBy((shift, 0))
            sourceGlyph.draw(sourcePen)
            self.sourcePens.append(sourcePen)
            self.sourceGlyphs.append(sourceGlyph)

    def updateSourcesOutlines(self, rebuild=True):
        if self.operator is None:
            return

        #zooming = glyphEditorIsInZoom()
        #print("updateSourcesOutlines rebuild", rebuild, zooming)
        # LongboardEditorView
        # everything necessary to update the sources, not time sensitive

        self.prepareSourcesOutlines(rebuild=rebuild)

        if self.darkMode != inDarkMode():
            self.darkMode = not self.darkMode
        if rebuild:
            self.sourcesPathLayer.clearSublayers()
            self.sourcesMarkerLayer.clearSublayers()

        if self.showSources:
            for sourceGlyphIndex, sourceGlyph in enumerate(self.sourceGlyphs):
                sourceGlyphsLayerName = f"sourceGlyphPath_{sourceGlyphIndex}"
                sourceGlyphsLayer = self.sourcesPathLayer.getSublayer(sourceGlyphsLayerName)
                if sourceGlyphsLayer is None:
                    # layer append or update? 5
                    sourceGlyphsLayer = self.sourcesPathLayer.appendPathSublayer(
                        name=sourceGlyphsLayerName,
                        fillColor=None,
                        strokeColor=self.sourceStrokeColor,
                        strokeWidth=self.instanceStrokeWidth,
                        strokeDash=self.sourceStrokeDash,
                        strokeCap="round",
                        )
                sourceGlyphsLayer.setPath(sourceGlyph.getRepresentation("merz.CGPath"))

        # if self.showPoints:
        #     # show the on curve point vectors
        #     for sourcePenIndex, sourcePen in enumerate(self.sourcePens):
        #         for sourceOnCurveIndex, p in enumerate(sourcePen.onCurves):
        #             isStart = p in sourcePen.startPoints
        #             # layer append or update? 10
        #             sourceOnCurveSymbolLayerName = f"source_marker_{sourcePenIndex}_{sourceOnCurveIndex}"
        #             sourceOnCurveSymbolLayer = self.sourcesMarkerLayer.getSublayer(sourceOnCurveSymbolLayerName)
        #             if sourceOnCurveSymbolLayer is None:
        #                 sourceOnCurveSymbolLayer = self.sourcesMarkerLayer.appendSymbolSublayer(
        #                     name = sourceOnCurveSymbolLayerName,
        #                     position = p,
        #                     imageSettings = dict(
        #                         name="rectangle",
        #                         size=(self.sourceMarkerSize, self.sourceMarkerSize),
        #                         fillColor=self.sourceStrokeColor
        #                     ),
        #                 )
        #             sourceOnCurveSymbolLayer.setPosition(p)
                        
        
    def updateInstanceOutline(self, rebuild=True):
        # LongboardEditorView
        # everything necessary to update the preview, time sensitive
        
        #zooming = glyphEditorIsInZoom()
        #print("updateInstanceOutline rebuild", rebuild, zooming)

        if self.darkMode != inDarkMode():
            self.darkMode = not self.darkMode
        if rebuild:
            # this is set when we're constructing the instance preview
            # for the first time. Clear out everything, rebuild everything
            self.instancePathLayer.clearSublayers()
            self.previewPathLayer.clearSublayers()
            self.instanceMarkerLayer.clearSublayers()
            self.marginsPathLayer.clearSublayers()
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

            # @@
            self.updateSourceVectors(previewGlyph)

            cpPreview = CollectorPen(glyphSet={})
            previewGlyph.draw(cpPreview)
            if self.showMeasurements:
                self.drawMeasurements(editorGlyph,  shift, previewGlyph)

            if self.showPreview:
                # 01 stroke instance path in the editor layer
                # layer append or update? 12
                path = previewGlyph.getRepresentation("merz.CGPath")
                instanceLayerName = f'instance_outline_{editorGlyph.name}'
                instanceLayer = self.instancePathLayer.getSublayer(instanceLayerName)
                if instanceLayer is None:
                    instanceLayer = self.instancePathLayer.appendPathSublayer(
                        name = instanceLayerName,
                        fillColor=None,
                        strokeColor=self.instanceStrokeColor,
                        strokeWidth=self.instanceStrokeWidth,
                        strokeDash = self.instanceStrokeDash,
                        strokeCap="round",
                        )
                instanceLayer.setPath(path)
                
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
                
                if self.showPoints:
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
                    #@@
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
                    # layer append or update? 16
                    
                    marginLayerName = f'instance_{editorGlyph.name}_margins'
                    marginLayer = self.marginsPathLayer.getSublayer(marginLayerName)
                    if marginLayer is None:
                        marginLayer = self.marginsPathLayer.appendPathSublayer(
                            name = marginLayerName,
                            strokeColor = self.vectorStrokeColor,
                            strokeDash = self.previewStrokeDash,
                            strokeWidth = 1,
                            fillColor = None,
                        )
                    marginLinePath = merz.MerzPen()
                    marginLinePath.moveTo(a)
                    marginLinePath.lineTo(b)
                    marginLinePath.endPath()
                    marginLinePath.moveTo(c)
                    marginLinePath.lineTo(d)
                    marginLinePath.endPath()
                    marginLayer.setPath(marginLinePath.path)

                    leftMarginLayerName = f'instance_{editorGlyph.name}_leftMargin'
                    leftMarginLayer = self.marginsPathLayer.getSublayer(leftMarginLayerName)
                    if leftMarginLayer is None:
                        leftMarginLayer = self.marginsPathLayer.appendLineSublayer(
                            name=leftMarginLayerName,
                            #startPoint=a,
                            #endPoint=b,
                            strokeColor=self.vectorStrokeColor,
                            strokeWidth= self.instanceStrokeWidth,
                            fillColor = None,
                            strokeDash= self.vectorStrokeDash,
                            strokeCap="round",
                        )
                    leftMarginLayer.setStartPoint(a)
                    leftMarginLayer.setEndPoint(b)

                    # layer append or update? 17
                    rightMarginLayerName = f'instance_{editorGlyph.name}_rightMargin'
                    rightMarginLayer = self.marginsPathLayer.getSublayer(rightMarginLayerName)
                    if rightMarginLayer is None:
                        rightMarginLayer = self.marginsPathLayer.appendLineSublayer(
                            name=rightMarginLayerName,
                            startPoint=c,
                            endPoint=d,
                            strokeColor=self.vectorStrokeColor,
                            strokeWidth=  self.instanceStrokeWidth,
                            fillColor = None,
                            strokeDash=self.vectorStrokeDash,
                            strokeCap="round",
                        )
                    rightMarginLayer.setStartPoint(c)
                    rightMarginLayer.setEndPoint(d)

    def updateSourceVectors(self, previewGlyph):
        if self.showPoints:
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
        self.updateSourcesOutlines(rebuild=True)
        self.updateInstanceOutline(rebuild=True)
        #print("showSettingsChanged", self.showPoints)

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




OpenWindow(LongBoardUIController) 




