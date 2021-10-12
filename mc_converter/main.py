from argparse import ArgumentParser
from pathlib import Path
from os import walk

def get_pack_format(path: Path) -> str:

    # Key modpack identifiers:
    # Modrinth has index.json
    # MultiMC has mmc-pack.json and instance.cfg
    # CurseForge has manifest.json and modlist.html
    # packwiz is a folder, and has index.toml and pack.toml
    # So.. That was easier then I thought

    if path.is_dir():
        files = [file for _, _, filenames in walk(path) for file in filenames]
        if "index.toml" in files and "pack.toml" in files: return "packwiz"

    if str(path).endswith("zip"):
        from zipfile import ZipFile
        with ZipFile(path) as zip:

            filenames = [Path(file).name for file in zip.namelist()]

            if "index.json" in filenames: return "modrinth"
            elif "mmc-pack.json" in filenames and "instance.cfg" in filenames: return "multimc"
            elif "manifest.json" in filenames and "modlist.html" in filenames: return "curseforge"

    return "Unknown"

async def main():

    formats = ['packwiz', 'multimc', 'modrinth', 'curseforge', 'intermediary']
 
    parser = ArgumentParser(description="Converts modpack formats to each other", exit_on_error=True)
    parser.add_argument('-c', '--config', dest='config', type=Path, help='Path to config, used to fill the gaps in parsed data')
    parser.add_argument('-i', '--input', dest='input', type=Path, help='Path to pack', required=True)
    parser.add_argument('-f', '--format', dest='format', type=str, choices=formats, help='Format to convert to', required=True)
    parser.add_argument('-o', '--output', dest='output_dir', type=Path, help='Specify output directory (optional)')
    args = parser.parse_args()

    if not args.input.exists(): exit("Invalid input!")
    pack_format = get_pack_format(args.input)
    if pack_format == "Unknown": exit("Invalid pack input format!")
