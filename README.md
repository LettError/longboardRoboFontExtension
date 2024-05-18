![The LongBoard Icon](longboardMechanicIcon.png)

# Longboard 🛹

Longboard draws previews of the current DSE2 designspace in the glyph window.
It is the successor to the Skateboard and Superpolator tools.

This is for RoboFont 4.5+ and you need to have the [DesignspaceEditor2 extension](https://github.com/LettError/designSpaceRoboFontExtension) installed. Longboard will activate when you have a designspace open in DSE2, and a glyph edit window for one of the sources.

## Pick an axis directions for mouse movement

![LongBoard UI](/source/html/screen_20240510.png)

The best thing about Longboard is the smooth navigation of the axes! A single mouse drag can manipulate as many axis values as you want. To set it up, use the LongBoard Window. It has a table with the continuous axes that are available for exploring for the current glyph. Use the pop up menu to choose a **direction** for the Navigator. For istance, in this image, horizontal movements of the navigator tool will make changes to the width axis values. And vertical movements will correspond to changes in the weight axis values.

The warning sign pops up when an axis value is outside the minimum / maximum values defined for the axis. Extrapolation is a really useful tool in type design. But it is good to know where the extremes are.

Longboard determines the values for the discrete axes from the source you're currently looking at. So if your designspace has a continuous weight and a discrete italic axis, Longboard will show upright weight variations in the upright sources, and italic weight variations in italic sources.



## Buttons

* **Add New Instance** Creates a new instance in the current designspace. Family name is copied from the default source. Style name is created from axis names and values. Use DSE2 to set all the other parameters.
* **Make Preview UFO** This creates a new UFO interpolated at the current preview location and the UFO is opened afterwards. This will **not** make a new instance in the designspace! The UFO is for inspection, proofing, measuring and so on. The UFOs are saved in the **preview** folder next to the designspace file. 
* **Copy Glyph to Clipboard** Does as advertised. The preview glyph to the clipboard so you can paste it somewhere else.
* **Reset Current Location** will bring you home to the default location. In case you get lost in crazy extrapolations. 

## Navigator

* LongBoard installs a tool in the glyph editor toolbar called **Longboard Navigator**.
* This is the icon: ![LongBoard navigator icon in the RoboFont glyph editor toolbar](/source/html/icon_toolbar.png)
* Select the tool and drag the cursor around in the glyph editor to explore different axis values. 

## Checkboxes 

* The checkboxes offer some control over what is drawn.
* **Show measurements** Longboard will draw its own measurements next to the RoboFont Measure lines. Useful for finding stems with a specific value, for instance.
* **Allow Extrapolation** permits extrapolation when using the Navigator tool. Unchecked the preview location will be clipped to axis extremes.


## Notes

* The mapping of mouse movements to axis values is hard wired in this initial release. As long as your axes have values that are roughly on a 0 - 1000 scale it will be fine, but there may be some speed issues if the axes are on a smaller scale, like 0 - 1. 
* With this tool most of the functionality that I wrote for **Skateboard** should be available again. **DesignspaceEditor2** does all the heavy lifting. Longboard really is just a small visualiser tool on top of that.

## Thanks!

* Frederik Berlaen, Tal Leming, Roberto Arista
* GitHub Sponsors who make the development of open, shared tools like this possible.
* And all Skateboard 🛹 and Superpolator ![Superolator icon, sorta.](/source/html/longboardIcon_icon.png) for your support, feedback and patience!


