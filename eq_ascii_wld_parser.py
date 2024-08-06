import os
import sys

# Manually set the directory containing your scripts
script_dir = r'C:\Users\dariu\Documents\Quail\Importer'  # Replace with the actual path
print(f"Script directory: {script_dir}")  # Check the path
if script_dir not in sys.path:
    sys.path.append(script_dir)

from main_parse import main_parse
from material_palette_parse import material_palette_parse
from dmspritedef2_parse import dmspritedef2_parse
from hierarchicalspritedef_parse import hierarchicalspritedef_parse
from track_parse import track_parse
from polyhedrondefinition_parse import polyhedrondefinition_parse
from simplespritedef_parse import simplespritedef_parse
from materialdefinition_parse import materialdefinition_parse

def eq_ascii_parse(filepath):
    def recursive_parse(filepath, parsed_sections=None, include_paths=None):
        if parsed_sections is None:
            parsed_sections = {}
        if include_paths is None:
            include_paths = []

        sections, includes = main_parse(filepath)

        # Merge sections into parsed_sections
        for section, instances in sections.items():
            if section not in parsed_sections:
                parsed_sections[section] = []
            parsed_sections[section].extend(instances)

        # Process INCLUDE statements
        for include in includes:
            include_path = os.path.join(os.path.dirname(filepath), include)
            if include_path not in include_paths:
                include_paths.append(include_path)
                recursive_parse(include_path, parsed_sections, include_paths)

        return parsed_sections, include_paths

    # Start the recursive parsing from the main file
    parsed_sections, include_paths = recursive_parse(filepath)

    # Print out the sections for debugging
    print("\nParsed Sections:")
    for section, instances in parsed_sections.items():
        print(f"Section: {section}")
        for instance in instances:
            print(f"Instance: {instance[:50]}...")  # Print first 50 chars of each instance for brevity

    # Parse material palettes
    material_palettes = {}
    for instance in parsed_sections.get('MATERIALPALETTE', []):
        material_palette = material_palette_parse(instance)
        if material_palette['name']:
            material_palettes[material_palette['name']] = material_palette['materials']

    # Parse DMSPRITEDEF2 sections
    meshes = []
    for instance in parsed_sections.get('DMSPRITEDEF2', []):
        dmspritedef2, inner_sections = dmspritedef2_parse(instance)
        meshes.append(dmspritedef2)

    # Parse HIERARCHICALSPRITEDEF sections
    armature_data = None
    for instance in parsed_sections.get('HIERARCHICALSPRITEDEF', []):
        armature_data = hierarchicalspritedef_parse(instance)

    # Parse POLYHEDRONDEFINITION sections
    polyhedrons = []
    for instance in parsed_sections.get('POLYHEDRONDEFINITION', []):
        print(f"Polyhedron Instance: {instance}")  # Debug print to check instance content
        polyhedron = polyhedrondefinition_parse(instance)
        polyhedrons.append(polyhedron)

    # Parse SIMPLESPRITEDEF sections
    textures = {}
    for instance in parsed_sections.get('SIMPLESPRITEDEF', []):
        print(f"SIMPLESPRITEDEF Instance: {instance}")  # Debug print to check instance content
        sprite_textures = simplespritedef_parse(instance)
        textures.update(sprite_textures)

    # Parse MATERIALDEFINITION sections
    materials = []
    for instance in parsed_sections.get('MATERIALDEFINITION', []):
        print(f"MATERIALDEFINITION Instance: {instance}")  # Debug print to check instance content
        material_defs = materialdefinition_parse(instance)
        materials.extend(material_defs)

    # Parse track definitions and instances
    track_definitions = track_parse(parsed_sections)

    return meshes, armature_data, track_definitions, material_palettes, include_paths, polyhedrons, textures, materials

if __name__ == '__main__':
    # Example usage:
    filepath = 'C:\\Users\\dariu\\Documents\\Quail\\pre.spk'
    meshes, armature_data, track_definitions, material_palettes, include_files, polyhedrons, textures, materials = eq_ascii_parse(filepath)

    # Print out the includes
    print("Includes:")
    for include in include_files:
        print(f"  {include}")

    print("\nMaterial Palettes:")
    for name, materials_list in material_palettes.items():
        print(f"Palette: {name}")
        for material in materials_list:
            print(f"  Material: {material}")

    print("\nDMSPRITEDEF2 Sections:")
    for dmspritedef2 in meshes:
        print(dmspritedef2)
    
    print("\nHIERARCHICALSPRITEDEF Sections:")
    print(armature_data)

    print("\nTRACKDEFINITION and TRACKINSTANCE Sections:")
    print(track_definitions)

    print("\nPOLYHEDRONDEFINITION Sections:")
    for polyhedron in polyhedrons:
        print(polyhedron)
    
    print("\nSIMPLESPRITEDEF Textures:")
    for name, path in textures.items():
        print(f"Texture Name: {name}, File Path: {path}")

    print("\nMATERIALDEFINITION Sections:")
    for material in materials:
        print(material)