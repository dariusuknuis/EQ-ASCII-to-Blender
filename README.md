# EQ-ASCII-to-Blender (WCE Importer)

Blender version: 3.6.2

Blender add-on to parse EverQuest ASCII game data and create Blender assets

To use:

Import

1) Download the WCE Importer/Exporter ZIP file from releases. Install as a Blender add-on through Edit>Preferences>Add-ons. Make sure to enable the add-on.
2) Compatible quail.exe, from my dev fork of the Quail repo, is located on the EQ-ASCII-to-Blender repo.
3) Place quail.exe and the EverQuest .s3d file you want to edit in the same folder.
4) Run quail.exe from command line. The command to convert a file from .s3d to Quail WCE format is:

            quail.exe convert filename.s3d filename.quail
   
5) In Blender press N to bring up the Sidebar and find the WCE Importer/Exporter tab. Press "Import WCE File".
6) Find and select the _root.wce file in the main filename.quail folder that you created with quail.exe.
7) A dialog box will appear that had the names of the files or folders that can be loaded. Each one is basically a model. Some, like WORLD.WCE, just have some data. Check the models you want to load and hit OK.

World Tools

If your input mesh has per-corner vertex colors, you should convert them to per-vertex colors. 
Should load a dummy DMSPRITEDEF with Import, or copy the custom properties of another DMSPRITEDEF mesh so it copies the properties to the output region meshes. 
Recommend FPSCALE of 5.

Special "zone" volumes, like PVP, water, etc... need to follow these naming conventions:

            Starts with:"DR" = Regular (Dry?)
                        "WT" = Water
                        "LA" = Lava
                        "SL" = "Slime" (Greener water with closer fog plane)
                        "VW" = "Velious" Water (Causes damage like Lava)
                        "W2" = Water "Version 2" (Grey fog and farther plane than regular water)
                        "W3" = Water "Version 3" (No fog and much farther clip plane than regular water)

            3rd character: "N" = Non-PvP zone (Not required)
                           "P" = PvP zone

            4th & 5th characters = "TP" =  zoneline or in-zone teleport
                        
            "S" between "_" = Slippery (Example: DRN__00134000000000000000000000_S_000000000000)

These types can mostly be combined. You can name the special zone volume with the above rules or put it in the "USERDATA" custom string property. The name of the special zone volumes always have to end with "_ZONE". Try to make them primitive shapes as much as possible. The logic for the teleport/zoneline volumes can be seen here: https://github.com/brainiac/MQ2Nav/blob/new-renderer/dependencies/zone-utilities/eqglib/eqg_terrain.cpp#L133

Existing EverQuest zones that are loaded through Import can be merged into a single mesh for easier editing by selecting the object with the zone's name and ending in "_WORLDDEF" (for instance, "ARENA_WORLDDEF"), and then pressing the "Format World" button in the N-menu under the Tools tab. 

Once you have your input mesh and special volumes prepared:
1) Select the input mesh
2) Open the N-menu and go to the Tools tab.
3) Click "Generate Outdoor World". Wait a few minutes possibly.
4) Click "Generate Radial Visibility".
5) Follow rules for export from the Export section.

Note: Try not to have too many small special "zone" volumes that are close together, as this can cause the addon to do too many splits of the same geometry. Zones like Kedge Keep will not split properly and the special volumes should be simplified.

Export

1) Open the N-menu and press the "Export Selected Models" button on the WCE Importer/Exporter tab and it will open a file explorer window to select a location to export.
2) It will then open a dialog with possible models to export. It will show every empty object blender file as a model to export. Select models and hit OK.
