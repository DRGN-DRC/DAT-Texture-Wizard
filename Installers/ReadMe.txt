These will install these applications to your context menu's "Send to" submenu (as shown in the screenshot).

If you move where you keep these applications, then the links in the context menu will break. To fix them, just re-run the installer. You can also remove the converter from the context menu by running the uninstaller.




	More on the PNG to-from TPL script:

This is a script I wrote around something I found within a set of utilities called Wimm's SZS Tools (link: http://www.mariokartwii.com/threads/75689-Wiimms-SZS-Tools#post3621221). Originally, Wimm's tool is used via manual entry into the command line for a single image (including requiring input for the file, file format and image type options). My script uses this tool, but gives you the ability to simply select the files you want to convert, and drag-and-drop them all onto the script at once (or even better, just right click on the files, and send them to the converter, as seen in the screenshot in this folder). For each file, it will look at the file format and image type from the file to determine what to do with it. If it’s a TPL, the script converts it to a PNG, and if it’s a PNG, it will convert it to a TPL, while choosing the correct encoding based on the image type*. For the whole process, an interface doesn’t even open; instead, a few moments later you’ll simply have your converted files in the same folder as the originals.

*It determines the image type (and therefore what encoding to use) by looking at the file name. So it will work fine as long as you kept the standard naming convention. e.g. “txt_0038_14.tga” or “GALE01_d7f59321_0.png”. Although you don’t need the entire default filename; all you really need to keep is the last underscore and number at the end, before the file extension.

Your images and the script don’t need to be in the same folder like with TexConv; they can be anywhere, even on different drives. In fact, you can even use it from Window's right-click context menu (as seen in the screenshot in the spoiler below), making it easier than ever to convert your images!

One final note: if you open the script in a text editor, towards the beginning of the script you'll find that there are a couple of options that you can modify.


 - Durgan (DRGN)