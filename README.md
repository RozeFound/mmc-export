# MultiMC advanced exporter

Since MultiMC export features are very limited, I created a script that solves this problem, with this script you can export MultiMC pack to any popular format (e.g. curseforge, modrinth, packwiz)

# If you use this application, please report any issue you encounter, since I don't use it, I don't know if there any problems.

# Features

- Support convertions to:
    - CurseForge
    - Modrinth
    - packwiz
- Detects downloadable resourcepacks and shaders
- Supports github parsing[¹](#github-rate-limits)
- Loose modrinth search
- User friendly toml config
- Multiple output formats at once

---
### Github rate limits

Github have limited requests per hour to 60, that means that if you have more than 60 mods, the rest will be excluded from github search.

To solve this, you can authorize in application. \
You need to create personal key [here](https://github.com/settings/tokens) (with no permissions), and pass it as argument to script along with your username, example:
```
mmc-export -i modpack -f format --github_auth username:token
```
I recommend you to store tokens in enviroment variables for security reasons.

# How to Use

```
mmc-export [-h] [-c CONFIG] -i INPUT -f FORMAT [-o OUTPUT]
```

Example: 
```
mmc-export -i modpack.zip -c config.toml -f curseforge modrinth -o converted_modpacks
```

## Explanation:

```
-h --help: prints help
-i --input: specifies input file (mostly zip file)
-c --config: specifies config file, used for fill the gaps like description or files not in modrinth on curseforge example can be found in this repository.
-f --format: soecifies formats to convert, must be separated by spaces.
-o --output: specifies output directory, where converted zip files will be stored. By default current working directory will be used.
```

Avaliable formats:     - `CurseForge, Modrinth, packwiz, Intermediate` (case sensetive)

`intermediate` must be used only for debuging, can contain sensetive information like user name.

# How to Install

## From PyPI
```
pip install mmc-export
```
 
 # Credits

murmurhash2 - Murmur Hash 2 libray - https://pypi.org/project/murmurhash2 \
aiohttp - Async web interface - https://github.com/aio-libs/aiohttp \
tomli - Fast pure python toml parser - https://github.com/hukkin/tomli \
pytoml - The only one toml writer that can handle weird packwiz files - https://github.com/avakar/pytoml \
tenacity - Awesome, ease-in-use retrying library - https://github.com/jd/tenacity
