import io
import os
import shlex
import sys

# Function to open and initiate the parsing
def parse(filepath: str):
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

    base_name = os.path.splitext(filename)[0].upper()  # Define base_name from the file name

    material_palettes = {}
    meshes = []
    armature_data = None
    polyhedrons = []
    textures = {}
    materials = []
    track_definitions = []
    includes = []

    for line in r:
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        # Pass the current line to track_parse instead of just the stream
        if line.startswith("INCLUDE"):
            include = shlex.split(line)[1].strip('"')
            includes.append(include)
            include_filepath = os.path.join(file_dir, include)
            print(f"Processing INCLUDE file: {include_filepath}")
            # Parse the include file recursively
            include_results = parse(include_filepath)
            # Unpack the include file results and merge with the main results
            meshes.extend(include_results[0])
            if include_results[1]:
                armature_data = include_results[1]
                track_definitions.extend(include_results[2])
                material_palettes.update(include_results[3])
                polyhedrons.extend(include_results[5])
                textures.update(include_results[6])
                materials.extend(include_results[7])
        elif line.startswith("MATERIALPALETTE"):
            from material_palette_parse import material_palette_parse
            material_palette = material_palette_parse(r, parse_property, line)
            if material_palette['name']:
                material_palettes[material_palette['name']] = material_palette['materials']
        elif line.startswith("DMSPRITEDEF2"):
            from dmspritedef2_parse import dmspritedef2_parse
            dmsprite = dmspritedef2_parse(r, parse_property, line)
            meshes.append(dmsprite)
        elif line.startswith("TRACKDEFINITION"):
            from track_parse import track_parse
            track_data = track_parse(r, parse_property, base_name, line)  # Pass the current line to track_parse
            track_definitions.append(track_data)
        elif line.startswith("HIERARCHICALSPRITEDEF"):
            from hierarchicalspritedef_parse import hierarchicalspritedef_parse
            armature_data = hierarchicalspritedef_parse(r, parse_property, line)
        elif line.startswith("POLYHEDRONDEFINITION"):
            from polyhedrondefinition_parse import polyhedrondefinition_parse
            polyhedron = polyhedrondefinition_parse(r, parse_property, line)
            polyhedrons.append(polyhedron)
        elif line.startswith("SIMPLESPRITEDEF"):
            from simplespritedef_parse import simplespritedef_parse
            sprite_textures = simplespritedef_parse(r, parse_property, line)
            if sprite_textures:
                textures.update(sprite_textures)
        elif line.startswith("MATERIALDEFINITION"):
            from materialdefinition_parse import materialdefinition_parse
            material_defs = materialdefinition_parse(r, parse_property, line)
            materials.append(material_defs)

    return meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials

# Shared utility function to parse a single property and validate it
def parse_property(r: io.TextIOWrapper = None, property: str = "", num_args: int = -1) -> list[str]:
    if r is None:
        raise Exception("reader is none")
    if property == "":
        raise Exception("empty property")

    for line in r:
        if "//" in line:
            line = line.split("//")[0]
        line = line.strip()
        if not line:
            continue
        records = shlex.split(line)
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

    # Debug print to display the collected armature data
    if armature_data:
        print("\nCollected Armature Data:")
        for key, value in armature_data.items():
            print(f"{key}: {value}")

    return meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials

if __name__ == '__main__':
    filepath = r"C:\Users\dariu\Documents\Quail\crushbone.quail\r.mod"
    meshes, armature_data, track_definitions, material_palettes, include_files, polyhedrons, textures, materials = eq_ascii_parse(filepath)

    # If armature data exists, print it out (for extra clarity outside of the function)
    if armature_data:
        print("\nFinal Collected Armature Data:")
        for key, value in armature_data.items():
            print(f"{key}: {value}")
