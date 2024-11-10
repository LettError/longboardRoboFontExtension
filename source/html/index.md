

![The LongBoard Icon](icon.png)

# Longboard


![LongBoard in the Glypheditor](screen_20241102_A.png)

Longboard draws previews of the current designspace in the glyph window.
It is the successor to the Skateboard and Superpolator tools.

This is for RoboFont 4.5+, you need to have the [DesignspaceEditor2 extension](https://github.com/LettError/designSpaceRoboFontExtension) installed. Longboard will activate when you have a designspace open in DSE2, and a glyph edit window for one of the sources.

![The LongBoard UI](screen_20241105.png)

Use Longboard to smoothly explore your designspaces in the glyph editor. A single mouse drag can manipulate as many axis values as you want. To set it up, use the table at the top of the LongBoard Window. It lists the **continuous axes** available for exploring. Use the pop up menu to choose a **direction** for the Navigator. For istance, in this image, horizontal movements of the navigator tool will change width axis values. And vertical movements will correspond to change in weight axis values.

Longboard determines the values for the **discrete axes** from the source you're currently looking at. So if your designspace has a continuous weight and a discrete italic axis, Longboard will show upright weight variations in the upright sources, and italic weight variations in italic sources.

Double click on the axis values to edit the numbers.

The **Tools**, **Appearance** and **About** tabs can close to save some space.

## Buttons

* **Add New Instance** Creates a new instance in the current designspace. Family name is copied from the default source. Style name is created from axis names and values. Use DSE2 to set all the other parameters. LongBoard warns you if the location is already in use.
* **Make Preview UFO** This creates a new UFO for the current preview location. RoboFont operns the UFO when it is ready. This UFO can be used for inspection, proofing, detailed measuring and so on. The UFOs are saved in the **preview** folder next to the designspace file. This will **not** make a new instance in the designspace. If you want to add the preview UFO as a source, you have to move it out of the Previews folder and rename it. Mote: Preview UFOs have floating point coordinates because precision.
* **Copy Glyph to Clipboard** Does as advertised. The preview glyph to the clipboard so you can paste it somewhere else. This glyph has decomposed components for obvious reasons.
* **Default Location** will take the Preview home to the default location. In case you get lost in crazy extrapolations. 
* **Random Location** will take the Preview to a random location in the designspace. In case you want to see the sights. If you have **Allow Extrapolation** checked, the random location will extrapolate a bit over the axis extremes.

## Appearance

* **Show Sources** draws all the sources for this glyph as well as the preview. This can be useful, but it can also be quite busy, visually. You be the judge and choose what you need. The sources are drawn centered under the current glyph.
* **Show Vectors** draws a vector between the sources and the preview. So you can see how the points get pulled around. This can be useful to spot compatibility issues.
* **Show Measurements** This applies the RoboFont Measure tool to the preview and shows the dimensions in blue. This way you can search for very specific stems, for instance.
* **Allow Extrapolation** Restrict the dragging with the Navigator tool to the axis extremes, or go wild. Variable font technology can not extrapolate. But in type design it can be a useful thing. Again, do what you need.

## Navigator

* LongBoard installs a tool in the glyph editor toolbar called **Longboard Navigator**.
* Look for this icon: ![LongBoard navigator icon in the RoboFont glyph editor toolbar](icon_toolbar.png)
* Select the tool and drag the cursor around in the glyph editor to explore different axis values.
* The preview will remain at the selected value when you switch to a different tool.


## Notes

* The mapping of mouse movements to axis values is done with a Subjective Algorithm™. That means "it works here with the designspaces I tested it with", As long as your axes have values that are roughly on a 0 - 1000 scale it will be fine, but there may be some speed issues if the axes are on a smaller scale, like 0 - 1. I may follow up on that.Otherwise, use your common sense.
* With this tool most of the functionality that I wrote for **Skateboard** and indeed **Superolator** should be available again. **DesignspaceEditor2** does all the heavy lifting. Longboard is a clever visualiser tool on top of DSE. I hope you enjoy. Feel free to check the GitHub sponsor pages.

## Thanks!

* LongBoard is **fast** and exists because of the work, support and help from [Frederik Berlaen](https://github.com/sponsors/typemytype) and [Tal Leming](https://github.com/sponsors/typesupply)
* Roberto Arista also worked on an earlier edition of this project.
* GitHub Sponsors who make the development of open, specialised, shared tools like this possible. In the small industry of type design, that makes a huge difference. You, or the company you work for, can sponsor open source type design tools like this. [My sponsor page is here.](https://github.com/sponsors/letterror)
* And all Skateboard 🛹 and Superpolator ![Superolator icon, sorta.](longboardIcon_icon.png) for your support, feedback and patience!

Visit [LettError.com](https://letterror.com) to see my fonts and other work. Take a look at [Superpolator.com](https://superpolator.com) for the theory of building designspaces for variable fonts, animated examples of interpolation problems and some tips on drawing for interpolation.
