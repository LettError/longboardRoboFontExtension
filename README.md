![The LongBoard Icon](longboardMechanicIcon.png)

# Longboard

Longboard draws previews of the current DSE2 designspace in the glyph window.
It is the successor to the Skateboard and Superpolator tools.

This is for RoboFont 4.5+ and you need to have the [DesignspaceEditor2 extension](https://github.com/LettError/designSpaceRoboFontExtension) installed. Longboard will activate when you have a designspace open in DSE2, and a glyph edit window for one of the sources.

## Picking axis directions for mouse movement

![LongBoard UI](/source/html/screen_20240510.png)

The LongBoard Window shows a table with the continuous axes that are available for exploring for the current glyph. Use the pop up menu to choose a **direction** for the Navigator. For istance, in this image, horizontal movements of the navigator tool will make changes to the width axis. And vertical movements will correspond to changes in the weight axis.

The warning sign pops up when an axis value is outside the minimum / maximum values defined for the axis. Extrapolation!

LongBoard also installs a tool in the glyph editor toolbar called **Navigator**.

## Buttons

* **Add New Instance** Create a new instance in the current designspace. Family name is copied from the default source. Stylename is created from axis names and values. 
* **Make Preview UFO** This creates a new UFO interpolated at the current preview location. The UFO is opened afterwards. This is **not** a new instance, but for inspection and measuring. The UFOs are saved in a **preview** folder next to the designspace file. 
* **Copy Glyph to Clipboard** Does as advertised. The preview glyph to the clipboard so you can paste it somewhere else.
* **Reset Current Location** will bring you home to the default location. In case you get lost in crazy extrapolations. 

