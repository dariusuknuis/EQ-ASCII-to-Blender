import io
import os
import shlex
import sys

def clear_console():
    if sys.platform.startswith('win'):
        os.system('cls')
    else:
        os.system('clear')

# Call the function to clear the console
clear_console()

# Manually set the directory containing your scripts
script_dir = r'C:\Users\dariu\Documents\Quail\Importer'  # Replace with the actual path
#print(f"Script directory: {script_dir}")  # Check the path
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Function to open and initiate the parsing
def parse(filepath: str):
    #print(f"Opening file: {filepath}")
    with open(filepath, 'r') as file:
        data = file.read()
    r = io.StringIO(data)
    file_dir = os.path.dirname(filepath)  # Get the directory
    try:
        return parse_definitions(r, file_dir, os.path.basename(filepath))
    except Exception as e:
        raise Exception(f"Error while parsing: {e}") from e

# Main function to handle definition switching and return results
def parse_definitions(r: io.TextIOWrapper = None, file_dir: str = None, filename: str = None):
    if r is None:
        raise Exception("reader is none")

#    print(f"Parsing file: {filename}")
    base_name = os.path.splitext(filename)[0].upper()  # Define base_name from the file name
    if base_name.endswith("_ANI"):  # Check if the base_name ends with '_ANI'
        base_name = base_name[:-4]  # Remove the last 4 characters ('_ANI')


    material_palettes = {}
    meshes = []
    armature_data = None
    polyhedrons = []
    textures = {}
    materials = []
    track_definitions = {'animations': {}, 'armature_tracks': {}}  # Use dictionaries for track_definitions
    includes = []

    for line in r:
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        # Check for INCLUDE files
        if line.startswith("INCLUDE"):
            include = shlex.split(line)[1].strip('"')
            includes.append(include)
            include_filepath = os.path.join(file_dir, include)
#            print(f"Processing INCLUDE file: {include_filepath}")
            
            # Parse the INCLUDE file recursively
            include_results = parse(include_filepath)

            # Debugging: print what was returned from the INCLUDE file
#            print(f"INCLUDE file {include_filepath} parsed results:")
#            print(f"Meshes: {include_results[0]}")
            # print(f"Armature Data: {include_results[1]}")
#            print(f"Track Definitions: {include_results[2]}")
#            print(f"Material Palettes: {include_results[3]}")
#            print(f"Polyhedrons: {include_results[5]}")
#            print(f"Textures: {include_results[6]}")
#            print(f"Materials: {include_results[7]}")

            # Unpack the INCLUDE file results and merge with the main results
            meshes.extend(include_results[0])
            if include_results[1]:
                armature_data = include_results[1]
            # Merge the track definitions for both animations and armature_tracks
            track_definitions['animations'].update(include_results[2]['animations'])
            track_definitions['armature_tracks'].update(include_results[2]['armature_tracks'])
            material_palettes.update(include_results[3])
            polyhedrons.extend(include_results[5])
            textures.update(include_results[6])
            materials.extend(include_results[7])

        elif line.startswith("MATERIALPALETTE"):
            from material_palette_parse import material_palette_parse
            material_palette = material_palette_parse(r, parse_property, line)
            if material_palette['name']:
                material_palettes[material_palette['name']] = material_palette['materials']
#            print(f"Parsed MATERIALPALETTE: {material_palette}")

        elif line.startswith("DMSPRITEDEF2"):
            from dmspritedef2_parse import dmspritedef2_parse
            dmsprite = dmspritedef2_parse(r, parse_property, line)
            meshes.append(dmsprite)
#            print(f"Parsed DMSPRITEDEF2: {dmsprite}")

        elif line.startswith("TRACKDEFINITION"):
            from track_parse import track_parse
            #print(f"Parsing TRACKDEFINITION in {filename}")
            track_data = track_parse(r, parse_property, base_name, line)  # Pass the current line to track_parse
            # Merge the track data for both animations and armature_tracks
            track_definitions['animations'].update(track_data['animations'])
            track_definitions['armature_tracks'].update(track_data['armature_tracks'])
#            print(f"Parsed TRACKDEFINITION: {track_data}")

        elif line.startswith("HIERARCHICALSPRITEDEF"):
            from hierarchicalspritedef_parse import hierarchicalspritedef_parse
            armature_data = hierarchicalspritedef_parse(r, parse_property, line)
            # print(f"Parsed HIERARCHICALSPRITEDEF: {armature_data}")

        elif line.startswith("POLYHEDRONDEFINITION"):
            from polyhedrondefinition_parse import polyhedrondefinition_parse
            polyhedron = polyhedrondefinition_parse(r, parse_property, line)
            polyhedrons.append(polyhedron)
#            print(f"Parsed POLYHEDRONDEFINITION: {polyhedron}")

        elif line.startswith("SIMPLESPRITEDEF"):
            from simplespritedef_parse import simplespritedef_parse
            sprite_textures = simplespritedef_parse(r, parse_property, line)
            if sprite_textures:
                textures[sprite_textures['name']] = sprite_textures
#            print(f"Parsed SIMPLESPRITEDEF: {sprite_textures}")

        elif line.startswith("MATERIALDEFINITION"):
            from materialdefinition_parse import materialdefinition_parse
            material_defs = materialdefinition_parse(r, parse_property, line)
            materials.append(material_defs)
#            print(f"Parsed MATERIALDEFINITION: {material_defs}")

    # Debug print to track final merged data from this file
#    print(f"Final parsed results for {filename}:")
#    print(f"Meshes: {meshes}")
    #  print(f"Armature Data: {armature_data}")
#    print(f"Track Definitions: {track_definitions}")
#    print(f"Material Palettes: {material_palettes}")
#    print(f"Polyhedrons: {polyhedrons}")
#    print(f"Textures: {textures}")
#    print(f"Materials: {materials}")

    return meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials

# Shared utility function to parse a single property and validate it
def parse_property(r, property: str, num_args: int = -1):
    if r is None:
        raise Exception("reader is none")
    if property == "":
        raise Exception("empty property")

    for line in r:
        # Debugging: Print out the line being parsed
#        print(f"Parsing line for property '{property}': {line.strip()}")
        
        if "//" in line:
            line = line.split("//")[0]
        line = line.strip()
        if not line:
            continue
        records = shlex.split(line)
#        print(f"Parsed records for '{property}': {records}")
        
        if len(records) == 0:
            raise Exception(f"{property}: empty records ({line})")
        if records[0] != property:
            raise Exception(f"{property}: expected {property} got {records[0]}")
        if num_args != -1 and len(records) - 1 != num_args:
            raise Exception(f"{property}: expected {num_args} arguments, got {len(records) - 1}")
        
        return records

# Main function to start parsing from the main file
def eq_ascii_parse(filepath):
    # Start parsing the main file
    meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials = parse(filepath)

    return meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials

if __name__ == '__main__':
    filepath = r"C:\Users\dariu\Documents\Quail\global_chr.quail\_root.wce"
    meshes, armature_data, track_definitions, material_palettes, include_files, polyhedrons, textures, materials = eq_ascii_parse(filepath)

    # If armature data exists, print it out (for extra clarity outside of the function)
    # if armature_data:
    #     print("\nFinal Collected Armature Data:")
    #     for key, value in armature_data.items():
    #         print(f"{key}: {value}")

    # if meshes:
    #     print("\nFinal Collected Meshes:")
    #     for mesh in meshes:  # Iterate directly over the list
    #         print(f"{mesh}")

#    if track_definitions:
#        print("\nFinal Collected Track Definitions:")
#        print("Animations:")
#        for track_name, animation in track_definitions['animations'].items():
#            print(f"{track_name}: {animation}")
#        print("Armature Tracks:")
#        for track_name, armature_track in track_definitions['armature_tracks'].items():
#            print(f"{track_name}: {armature_track}")

    # if material_palettes:
    #     print("\nFinal Collected Material Palettes:")
    #     for key, value in material_palettes.items():
    #         print(f"{key}: {value}")

#    if include_files:
#        print("\nFinal Collected Include Files:")
#        for include_file in include_files:  # Iterate directly over the list
#            print(f"{include_file}")

#    if polyhedrons:
#        print("\nFinal Collected Polyhedrons:")
#        for polyhedron in polyhedrons:  # Iterate directly over the list
#            print(f"{polyhedron}")

#    if textures:
#        print("\nFinal Collected Textures:")
#        for texture_name, texture_data in textures.items():  # This prints the full texture information
#            print(f"{texture_data}")

#    if materials:
#        print("\nFinal Collected Materials:")
#        for material in materials:  # Iterate directly over the list
#            print(f"{material}")
