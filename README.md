# modpack-converter
Convert's one minecraft modpack format to another.

Maybe I need to think of a better name...

# If you use this application, please report any issue you encounter, since I don't use it, I don't know if there any problems.

# Features

- Auto detect input modpack format
- Support convertions to and from:
    - MultiMC (parsing only)
    - CurseForge
    - Modrinth
    - packwiz
- Detects downloadable resourcepacks and shaders (MultiMC only)
- User friendly toml config
- Multiple output formats at once

# How to Use

```
mc-converter [-h] [-c CONFIG] -i INPUT -f FORMAT [-o OUTPUT]
```

## Explanation:

```
-h --help: prints help
-i --input: specifies input file (mostly zip file)
-c --config: specifies config file, used for fill the gaps like description or files not in modrinth on curseforge example can be found in this repository.
-f --format: soecifies formats to convert, must be separated by space.
-o --output: specifies output directory, where converted zip files will be stored. By default current working directory will be used.
```

Avaliable formats:     - `curseforge, modrinth, packwiz, intermediate`

`intermediate` must be used only for debuging, can contain sensetive information

Example: 
```
mc-converter -i MyLovelyMultiMcModpack.zip -c config.toml -f curseforge modrinth -o converted_modpacks
```

# How to Install

## From PyPI
```
pip install mc-converter
```
## From `.whl` file
Go to Release page, download latest `.whl` file \
 And install it via the following comand:
 ```
 pip install mc_converter_{version}.whl
 ```
 
 # Credits

murmurhash2 - Murmur Hash 2 libray - https://pypi.org/project/murmurhash2 \
aiohttp - Async web interface - https://github.com/aio-libs/aiohttp \
tomli - Fast pure python toml parser - https://github.com/hukkin/tomli \
pytoml - The only one toml writer that can handle weird packwiz files - https://github.com/avakar/pytoml \
tenacity - Awesome, ease-in-use retrying library - https://github.com/jd/tenacity
