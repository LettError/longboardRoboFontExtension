![The LongBoard Icon](longboardMechanicIcon.png)

# Longboard

Longboard draws previews of the current DSE2 designspace in the glyph window.
It is the successor to the Skateboard and Superpolator tools.

This is for RoboFont 4.5+ and you need to have the [DesignspaceEditor2 extension](https://github.com/LettError/designSpaceRoboFontExtension) installed. Longboard will activate when you have a designspace open in DSE2, and a glyph edit window for one of the sources.

## Picking axis directions for mouse movement

![LongBoard UI](/source/html/screen_20240510.png)

The LongBoard Window shows a table with the continuous axes that are available for exploring for the current glyph. Use the pop up menu to choose a **direction** for the Navigator. For istance, in this image, horizontal movements of the navigator tool will make changes to the width axis. And vertical movements will correspond to changes in the weight axis.

The warning sign pops up when an axis value is outside the minimum / maximum values defined for the axis. Extrapolation!

## Buttons

* **Add New Instance** Create a new instance in the current designspace. Family name is copied from the default source. Stylename is created from axis names and values. 
* **Make Preview UFO** This creates a new UFO interpolated at the current preview location. The UFO is opened afterwards. This is **not** a new instance, but for inspection and measuring. The UFOs are saved in a **preview** folder next to the designspace file. 
* **Copy Glyph to Clipboard** Does as advertised. The preview glyph to the clipboard so you can paste it somewhere else.
* **Reset Current Location** will bring you home to the default location. In case you get lost in crazy extrapolations. 

## Checkboxes 

The checkboxes offer some control over what is drawn. **Allow Extrapolation** permits extrapolation when using the Navigator tool. Uncheck to disallow extrapolating.

## Navigator

LongBoard installs a tool in the glyph editor toolbar called **Navigator**. Select and drag around in the glyph editor to explore different axis values. 

## Notes

The mapping of mouse movements to axis values is a bit hard wired in this initial release. As long as your axes have values that are on a 0 - 1000 scale it will be fine, but there may be some speed issues if the axes are on a smaller scale, like 0 - 1. 

With this tool most of the functionality that I wrote for Skateboard should be available again. DesignspaceEditor2 does all the heavy lifting. Longboard really is just a small visualiser tool on top of that. I hope these are useful to you. 

Thanks to Frederik Berlaen, Tal Leming, Roberto Arista, GitHub Sponsors and all Skateboard and Superpolator users who make the development of tools like this possible.

