ReadMe version 2.3, for DTW version 5+.


   - Contents:
	- Opening Files
	- Opening a Root Folder / Creating a new ISO
	- Exporting
	- Importing Files into a Disc
	- Other Disc Operations
	- Browsing Textures
	- Importing Textures into a DAT/USD
	- Settings
	- Erasing Textures
	- Other Notes on Saving


		=================
		| Opening Files |
		=================

The program supports Melee disc images (ISOs or GCMs), image/texture files as PNG or TPL, and Melee data files (DATs, USDs, or similarly structured files that have textures, all of which are simply referred to as DATs for the rest of this doc).

For convenience, you can open files in multiple different ways:

 - Drag-’n-drop onto the program’s .exe file (i.e. the icon; before opening the program)
 - Drag-’n-drop directly onto the program’s GUI (anywhere) once the program is already open.
 - The ‘Open Disc’ & ‘Open DAT’ options in the File Menu.
 - The text field for a file path on the Disc Details, DAT Texture Tree and Manual Placement tabs.
 - The ‘Open Recent’ option in the File Menu, which will remember up to 12 (this number can be changed, see settings) of the last ISOs/DATs and/or other files you’ve opened, so you don’t have to search for them.

When opening a disc image, you'll be presented with a list of all of the files in the game in the Disc File Tree tab. From here, you can export a file to create it as its own standalone file, or import a standalone file to replace one that’s in your game, or click “Browse Textures” to see or change the textures in that file. Alternatively, you can open a standalone DAT file (one you've downloaded or already exported), which will open directly to the DAT Texture Tree tab.

The “DAT / USD” text field on the ‘DAT Texture Tree’ and ‘Manual Placement’ tabs is quite versatile. You can paste-in the file path of not just DATs, but disc images too. And if you’ve loaded a disc in the program, you can even type in the filepath or filename for a file within the disc! For example, with a disc loaded, you can type in “GALE01/MnSlMap.usd” or even just “MnSlMap.usd” (with or without quotes), and press Enter. So if you know the filename of the file you want to load, you can quickly jump to it without having to leave the tab or program. You can also use this text field to reload any file you have open at any time, just click into the field and press Enter and the file will be reloaded.

Also mind the ‘Prev./Next File’ buttons to the left and right of the file details on the DAT Texture Tree tab. These allow you to browse through files in the currently loaded disc image, or, if the DAT you’ve loaded is from a folder on your computer, the buttons will browse the other DAT files in that folder instead. (Even if you’ve loaded some custom file type, then the feature will also consider that a valid filetype to look for.)



		Opening a Root Folder / Creating a new ISO:

Open a root folder using the option found in Menu -> Open Root, and choose a folder containing the files for your disc (it doesn't need to be named root). Upon saving (CTRL-S or Menu -> Save), you'll be prompted for an ISO/GCM filename to create a new disc image. (GCM = GameCube Media; the extension you specify will not change how the disc is built.)


		=============
		| Exporting |
		=============

Exporting files from your disc is not limited to DATs and USDs; any file shown in the ISO File Tree can be exported (one or multiple simultaneously). With textures, the ‘Export All Textures’ feature will export all textures you can see listed, meaning that those filtered out (feature described below in the ‘Texture Filtering’ section) won’t be exported.

If you’re only exporting one texture or file from a disc, you can specify its file name (a standard naming convention will be offered by default as a suggestion). However, when exporting multiple, only the standard naming convention will be used, to speed up the process. By default, DAT/USD or other files from disc images will be named just as they are within the disc, which is typically just as seen in the Disc File Tree. For textures, the standard naming convention comes in this format: [sourceFile]_[textureOffset]_[textureType].[fileExtension], e.g. “MnMaAll.usd_0x70580_0.png". If you want to use this (benefits described below), but also want to add your own notes with it, add the notes to the beginning, while separating with another underscore and keeping the rest of the name intact. For example: “Controller image_MnMaAll.usd_0x71f80_0.png". Some of the uses of this standard naming convention include:

- Provides anyone looking at the file all the information they need for putting it into the game, even if they’re using older texture hacking methods.
- Others that you may share the file(s) with will likely be saved some work, especially when they want to work with more than a few textures.
- More logical than Dolphin's dump feature file naming convention.
- Extra functionality when using the file with this program, described below. (And even more powerful functionality using it is planned.)


		===============================
		| Importing Files into a Disc |
		===============================

Anything that can be exported from the Disc File Tree tab can also be imported back into it. For a single file, simply select the file you’d like to replace and click Import (found in the pane on the right, the toolbar drop-down at the top, or the right-click menu). The file is then queued for saving, and will be updated in the disc the next time you save. (This prevents rebuilding a disc prematurely or repeatedly, if there will be multiple new files added).

Selecting files in the file tree is a method for importing and replacing only a specific file at a time. Files don't need to be named a specific way for that method. For multiple files, use the 'Import Multiple Files' function in the Disc Operations menu or right-click dropdowns. This method will use the filenames of the files you're importing to determine what files in the disc to replace, meaning that they must match the names of the files in the disc (though this is not case-sensitive). Files that reside in a folder are specified by including the folder path in the filename as well, using a dash separator. For example, a file named "audio-menu01.hps" would replace the 'menu01.hps' file in the 'audio' folder.


		=========================
		| Other Disc Operations |
		=========================

- Add File(s) to Disc - Adds a new file to the disc, rather than replace an existing one.

- Add Directory of File(s) to Disc - Adds all of the files within a folder, and the folder itself, to the disc, rather than replace existing ones.

- Create Directory - Adds a new directory (folder) to the disc.

- Rename Selected Item - Renames a file or folder. Names must be less than 30 characters in length; this applies to the above operations as well. Changes to conveneince folders (i.e. those that don't actually exist in the disc) will of course not be saved.

- Remove Selected Item(s) - Removes the selected file(s) and/or folder(s) from the disc.

- Move Selected to Directory - Moves the selected file(s) and/or folder(s) to a new directory. This could be any folder or the root of the disc.

After any of the operations above (except renaming), expect that the disc will need to be rebuilt when saved, in order to move data in the file and rebuild the disc's filesystem.


- Generate CSP Trim Colors - Only used for one game, 'SSBM: 20XX' (game versions 4+). This is used to set the colors that appear behind Character Select Portraits (CSPs), for distinguishing between alternate character costume selections. The feature will analyze the colors in the costume file -excluding eye textures and those used for shading (typically monochrome variations of other present textures)- and generate two colors for the background of the CSP/port area. These colors are: the base color, which is the majority of the area behind the CSP, and the accent color, which is the small line that runs along the top and right side. The base color will be set as the most prominent color from the costume. By default, the accent color should be a color of high luminance and saturation (in order to form a good contrast from the base color) if the base color is dark, or a low luminance and saturation if the base color is a light color.

This feature can be used in two ways: 1) Right-click on a character's alternate costume file (i.e. one of those ending in .lat/.rat) and select the option. If you use this method, you'll be presented with a small window where you can pick a different accent color from among the colors generated for that costume. Or you can use the window to enter specific values directly for both the base and accent colors. 2) Auto-Generate CSP Trim Colors; a setting under the Settings menu. If this is enabled, then whenever you import a costume file to replace one of the .lat or .rat files, the generator will run in autonomous mode to generate colors, take the base color and default accent color, and update those in your game.

Details on how the color data is stored in 20XX can be found here:
https://smashboards.com/threads/the-20xx-melee-training-hack-pack-v4-05-update-3-17-16.351221/page-134#post-20881731


		=====================
		| Browsing Textures |
		=====================

Textures that are part of a mipmap group will have their line highlighted in a light blue.

For now, you can manually edit the other mipmaps in the group the same as you would manually edit other textures. You can find more information on mipmaps here:

http://smashboards.com/threads/how-to-hack-any-texture.388956/page-3#post-20372869
http://wiki.tockdom.com/wiki/Image_Formats#Mipmaps
https://en.wikipedia.org/wiki/Mipmap


Texture Filters: If you’re trying to find something specific, you can filter what textures appear in the DAT Texture Tree list by going to the Settings menu -> Adjust Texture Filters. The Aspect Ratio may be given as a ratio, fraction, whole number, or decimal, e.g. “4:3”, ¼, 1 (for a square), .5, etc.. The Offset may be given in hex or decimal (remember to include the “0x” to differentiate between these). Filtering greatly cuts down on loading times since the excluded textures won’t need to be drawn or decoded.


		=====================================
		| Importing Textures into a DAT/USD |
		=====================================

There are three different methods this program can use to do this, based on which tab you’re using when you import the texture, which each have different advantages:

 1) When on the “DAT Texture Tree” tab: Start by selecting one or more textures that you’d like to replace. Click ‘Import’ to browse for a texture file, or you may drag-and-drop your texture anywhere onto the window. If you selected multiple textures in the program, all of them will be replaced with the texture you’re importing. (Assuming that the texture will fit in the available space, which you will be notified of if it doesn’t.) In most cases, you’ll want to be replacing with the same dimensions and texture type as what’s originally in the game. Once you’re done replacing textures, go to the File Menu and click ‘Save Changes’ to finish. This requirement of saving means that at any time before saving, you can simply reload the file (click into the “DAT / USD” text field and hit ‘Enter’) if you’ve made a mistake. This method also doesn’t require the texture to have any special filename; you don’t even need it to include a texture type. However, if you do include a texture type in the filename, then you can change it and optionally “force” the type to be different than what is already in the game (unless you really know what you’re doing, only changing to a type that uses the same or less space will work). 

 2) The "Disc Import Method" for textures: When you’re on the “Disc File Tree” tab and you import a texture, it will be imported to the file and offset (location in that file) described in the filename. This of course only works with the standard naming convention described in the “Exporting” section above. You don’t need to select any files in the file tree to use this method. The only prerequisite is that you have a disc image opened. You may also import multiple files at once using this method. This makes it very quick and easy to import textures into your game.

 3) On the “Manual Placements” tab: This allows you to directly write textures into any specific location (offset). This is essentially the functionality of DTW2, available to provide support in cases where neither of the above methods will work, for example if the texture you're working with does not show up in the program. This method also allows you to import multiple textures at once, but only into a single standalone DAT (one not in a disc); it can't do multiple textures across multiple files like the Disc Import Method.

To set the offsets -which determine the individual points in the DAT file that the texture(s) are overwritten to- you have two options:

Option 1: Manual assignment. As mentioned above, once you've selected textures, you’ll see their filepaths listed in the text field. To give them an offset, type an arrow like this “-->”, followed by the offset. For example, a line with a filepath and an offset of 0xbad60 would look like this: 

C:\textures\exampleFolder\EfCoData.dat_0xbad60_3.tpl --> 0xbad60

(You’ll see the arrow change to green, helping it stand out and indicating that it’s recognized. The spaces are optional to just make things more readable. The “0x” in the offset is also actually optional.)

Option 2: Automatic assignment. If your texture uses the standard naming convention (described in the “Exporting” section above), then the texture should have the proper offset as soon as it’s loaded into the program. Be careful though; if the new texture is originally from a different place in the file, or from a different file, then this value might be wrong and you’ll need to set it manually.

Multiple Overwrites feature: You can overwrite the same image into multiple different locations if you'd like. To do this, write all of the offsets after the arrow ("-->"), separated by commas. For example:

C:\exampleFolder\file_0x123456_1.png --> BAD60, ABCF, 00123

Separate Palette Offsets: There are a few rare paletted textures that do not follow the standard method for where their palettes are placed in the DAT/USD file. If you happen to be working with an image like this, you'll need to know the offset for where the image data goes, as well as the offset for the palette data. Once you have this information, setting these offsets is simple; simply write the image data offset, followed by a colon (":"), followed by the palette data offset. For example:
	
C:\exampleFolder\file_0x12345_8.tpl --> 0123F:3210F
	
In this case, the image data will be written to 0123F, and the palette will go to 3210F. Again, this is only for rare cases; most textures, even with palettes, just need one offset.


		============
		| Settings |
		============

- Use Disc Convenience Folders: The Disc Convenience Folders are folders added to the Disc File Tree that aren't actually in the disc, for example for organizing all character files or stage files together in SSBM. If you disable this option and load a disc, you'll see only the folders that actually exist in the disc's filesystem.

Note that if this feature is enabled, root folders that are opened may have a few specific files with incorrect predicted disc offsets.

- Avoid Rebuilding Disc: Rebuilding a disc is a process of assigning new file offsets, moving (copying) the game's file data, and recreating the disc's filesystem (namely, the FST). This is done in order to insert or remove information, such as adding new files to the disc, removing files, or importing a file that is sufficiently larger than the original file it replaces. This option controls whether the rebuild process takes place in cases where a rebuild is not absolutely required, described below.

When importing a file, it may or may not be required to rebuild the disc. If the new file is smaller than the original, rebuilding is not required. If the new file is larger than the original, then rebuilding might not be needed, depending on the amount of padding present between the files in the disc; if the amount of padding after the original file, before the next file in the disc, is less than the difference between the original file and the new file, then rebuilding is required (otherwise, importing the new file would partially overwrite the next file in the disc). However, if the size difference between the original file and the new file can fit in (is less than or equal to) the amount of padding that follows the original file in the disc, then rebuilding the disc is not needed.

Not having to rebuild the disc makes saving practically instantaneous. However, even when it is not required, rebuilding can be useful to make the disc smaller by removing files, importing files that are smaller than their originals, or by specifying less padding to be present between files (explained at the end of this section). Or you can specify more padding between files, so that rebuilding is required less often.

- Back-up When Rebuilding ("Rebuild" process explained above.): When you save changes to a disc and the disc will be rebuilt, having this option enabled will create a copy of your game with your new changes, while leaving your original disc image untouched. So this is just a matter of precaution; if you already have a back-up of your game (always a good idea to keep at least one that's reasonably up to date) or you fully trust the changes that you've made, then you don't need to keep this enabled. When disabled, you'll still see a temporary file created while the rebuild process is under way, but once it's done, your original ISO will be up to date with your changes. Note that a majority of the time spent rebuilding a disc is copying data, which needs to happen whether this option is enabled or not.

- Auto-Generate CSP Trim Colors: This is explained in the "Other Disc Operations" section above.

- Auto-Update Headers: This option is only of concern when you want to import a texture that has a different height, width, or texture type than the texture that is already in the target file. If this option is enabled, then all image data headers will be updated to match the properties of the newly imported texture. If disabled, the program will leave them alone (and give you a warning that they are not being updated). You can still modify the headers manually in the DAT Texture Tree tab, under the Properties sub-tab. It’s recommended to leave this on if you’re not sure. Note that this will only be useful if your new texture takes up less space than the existing one; if it requires more space, DTW will not import it, to prevent overwriting other data following the original texture space. You can calculate how much space the image data for a texture will use with the Image Data Length Calculator, found in the Tools menu.

- Regenerate Invalid Palettes: If you import a texture with a palette that has too many colors (i.e. there are more colors than what there is space for in the palette residing in the game), then having this option enabled will prompt DTW to generate a new palette and use that instead.

- Cascade Mipmap Changes: When this feature is enabled and a texture is imported over a mipmap texture of any level, all mipmap levels below it will also be updated to match it with an automatically scaled copy of the imported texture. The algorithm used for downscaling is set by the "downscalingFilter" (described below), available in the settings.ini file.

- Export Textures using Dolphin's Naming Convention: This sets the naming convention used for texture file names. The standard naming convention used by DTW is "[sourceFile]_[textureOffset]_[textureType].[fileExtension]", e.g. “MnMaAll.usd_0x70580_0.png". This is useful for the Disc Import Method feature (Dolphin's file naming convention cannot be used with that feature, because there is no way to know where to place the texture). Read the section "Importing Textures into a DAT/USD" to learn more about DTW's Disc Import Method for textures.

- Adjust Texture Filters: See the "Browsing Textures" section for what this is for.


	The following settings only appear in the settings.ini file:

- dumpPNGs: In order to view some CMPR textures, TPL files are first created and dumped in the “Texture Dumps” folder (this is necessary to use wimgt for the texture conversion process). If you turn this feature on, then PNG versions of all viewed textures (not just CMPR) will also be dumped. Note that these textures don’t act as a cache to speed up scanning files; they still need to be regenerated each time you view them in case they’re different. All boolean (True/False) options can be set as either "0" or "False" for off, or "1" or "True" for on (no quotes).

- deleteImageDumpsOnExit: With this option enabled, all texture dumps will be deleted once you close the program. Important note: these will be permanently deleted; they will not go to the recycle bin!

- paddingBetweenFiles: This may be set to a hex value, or the string "auto" (with no quotes), and controls how much padding is created when building or rebuilding discs. Large values will result in a larger disc, but will mean that importing files (that are larger than the original file) will require a rebuild less often. The default value is 0x40. If this is set to "auto", and the total file size of all files permits, DTW will create a disc that is the standard GameCube disc size of 1,459,978,240 bytes, and evenly distribute the amount of padding that would be left over after totaling the size of all non-system files in the disc.

If set to "auto", and the total file size of all files to be included in the disc is greater than the standard GameCube size, the padding between files will be 0. However, up to 3 bytes of padding may still be added between some files, in order to preserve 4 byte alignment (on the file-start offset) for all files. Similarly, if a non-4-byte multiple of a hex value is given, it will be adjusted downward to the nearest multiple of 4 bytes.

- downscalingFilter: This determines the downscaling filter used for processing mipmap levels that will be automatically generated by the Cascade Mipmap Changes option described above. Valid options (without quotes) are: 'nearest', 'lanczos' (the default), 'bilinear', or 'bicubic'. These are common methods, so you can google them to understand the pros/cons of each.

- altFontColor: You can use this to set a default font color for the program (some text elements will not be affected). The default color is particularly useful for systems running high-contrast themes. The format is #RRGGBB. Common color strings may also be used, which you can find here: "http://www.science.smith.edu/dftwiki/index.php/Color_Charts_for_TKinter" Note that this feature is enabled by the useAltFontColor option described below.

- useAltFontColor: This option enables/disables the color set for "altFontColor" above. As with the other boolean (True/False) options, this can be set as either "0" or "False" for off, or "1" or "True" for on (no quotes).

- textureExportFormat: Determines the file format when exporting textures in bulk; such as when using 'Export All' on the DAT Texture Tree tab, or 'Export Textures From Selected' on the Disc File Tree tab. Valid values are "png" or "tpl" (no quotes).



		=====================
		| Erasing Textures: |
		=====================

The ‘Erase (zero-out)’ feature replaces the image data portion of the file with zeros. It doesn’t touch the headers. (Zeroing the header will cause the game to freeze.) This can have varied in-game results, based on the texture type and the kind of object the texture is applied to in-game. Some objects have a solid fill color, in which case you will then just see that color fill the area, while others actually have transparency and you’ll simply see through the area where the texture was. You’ll need some trail-and-error to figure out which is which.



		=========================
		| Other Notes on Saving |
		=========================

The program status in the top right of the program (to the right of the main program tabs) can help you keep track of changes made to your game. It changes color based on one simple rule: green means that there are no changes waiting to be saved to whatever file you have opened, and red means that there are unsaved changes waiting to be saved. And at any time, you can check what changes are pending by the menu option, File -> View Unsaved Changes.

You don’t have to close out of the program, even if you’ve made changes to a disc, before you open it in another program like Dolphin. Since the same is also true for the Melee Code Manager, you can use both of these in tandem, without closing either between modifications. You’ll still have to stop emulation in Dolphin in order to save changes to a disc though, of course.





If you have any other questions, don’t forget about all of the other resources available through the Help menu within the program! And if there’s anything that’s missing, or that is here yet confusing, please let me know. And if you'd like to support development of this program and/or the Melee Code manager, you can
donate: https://tinyurl.com/donateToDRGNviaPayPal
or follow me on Patreon: https://www.patreon.com/drgn

Thanks!

 - Durgan (DRGN)


