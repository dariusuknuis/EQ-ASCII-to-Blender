# EQ-ASCII-to-Blender (WCE Importer)
Blender add-on to parse EverQuest ASCII game data and create Blender assets

To use:

Import

1) Download the WCE Importer ZIP file from releases. Install as a Blender add-on through Edit>Preferences>Add-ons. Make sure to enable the add-on.
2) Download the matching quail.exe version from https://github.com/xackery/quail/releases.
3) Place quail.exe and the EverQuest .s3d file you want to edit in the same folder.
4) Run quail.exe from command line. The command to convert a file from .s3d to Quail WCE format is:
            quail.exe convert filename.s3d filename.quail
5) Within the .quail folder there is a file called _root.wce with contents like this:
   
            // wcemu v0.0.1
            // This file was created by quail v1.4
            // Original file: chequip.wld

            INCLUDE "WORLD.WCE"
            INCLUDE "CLN/_ROOT.WCE"
            INCLUDE "ALL/_ROOT.WCE"
            INCLUDE "ARM/_ROOT.WCE"
            INCLUDE "AVI/_ROOT.WCE"

   The lines after INCLUDE "WORLD.WCE" are the models that will load. Comment out any models you don't want to load like this:
   
            // wcemu v0.0.1
            // This file was created by quail v1.4
            // Original file: chequip.wld

            //INCLUDE "WORLD.WCE"
            INCLUDE "CLN/_ROOT.WCE"
            //INCLUDE "ALL/_ROOT.WCE"
            //INCLUDE "ARM/_ROOT.WCE"
            //INCLUDE "AVI/_ROOT.WCE"
   
6) In Blender press N to bring up the Sidebar and find the WCE Importer tab. Press "Import WCE File".
7) Find and select the _root.wce file in the main filename.quail folder that you created with quail.exe.
8) It will load each model that was uncommented as a separate empty object. Under each empty object are the meshes and armatures for that model.

Export

1) Download the Exporter folder and files from Github and unzip wherever you want.
2) Change the below line in master_export.py to the location you placed your exporter scripts folder at:
            # Add the path where export scripts are located
            **sys.path.append(r'C:\Users\dariu\Documents\Quail\Exporter')**
3) Open the Blender Scripting workspace and click the folder icon and open the master_export.py.
4) Set the location for the output on this line near the bottom of the script:
            **output_path = r"C:\Users\dariu\Documents\Quail\Exporter"  # Update the path to your preferred location**
   and the name of the empty object for the model you want to export at the bottom of the script:
            **export_model('ELF') #empty object containing models and armature here**

