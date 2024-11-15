# EQ-ASCII-to-Blender (WCE Importer)
Blender add-on to parse EverQuest ASCII game data and create Blender assets

To use:

Import

1) Download the WCE Importer/Exporter ZIP file from releases. Install as a Blender add-on through Edit>Preferences>Add-ons. Make sure to enable the add-on.
2) Download the matching quail.exe version from https://github.com/xackery/quail/releases.
3) Place quail.exe and the EverQuest .s3d file you want to edit in the same folder.
4) Run quail.exe from command line. The command to convert a file from .s3d to Quail WCE format is:

            quail.exe convert filename.s3d filename.quail
   
5) In Blender press N to bring up the Sidebar and find the WCE Importer tab. Press "Import WCE File".
6) Find and select the _root.wce file in the main filename.quail folder that you created with quail.exe.
7) A dialog box will appear that had the names of the files or folders that can be loaded. Each one is basically a model. Some, like WORLD.WCE, just have some data. Check the models you want to load and hit OK.

Export

1) Export is now built into the add-on. Just hit the "Export Selected Models" button and it will open a file explorer window to select a location to export.
2) It will then open a dialog with possible models to export. It will show every empty object blender file as a model to export. Select models and hit OK.
