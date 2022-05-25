# MultiMC advanced exporter
![PyPI pyversions](https://img.shields.io/pypi/pyversions/mmc-export)
[![PyPI version](https://img.shields.io/pypi/v/mmc-export?label=mmc-export&color=%2347a637)](https://pypi.org/project/mmc-export)
[![PyPI downloads](https://img.shields.io/pypi/dm/mmc-export?color=%23894bbf)](https://pypistats.org/packages/mmc-export)
[![GitHub license](https://img.shields.io/github/license/RozeFound/mmc-export)](/LICENSE)

Since MultiMC export features are very limited, I created a script that solves this problem, with this script you can export MultiMC pack to any popular format (e.g. curseforge, modrinth, packwiz). MultiMC forks which didn't changed export format much also supported, PolyMC support approved.

# Features

- Support conversion to:
    - CurseForge
    - Modrinth
    - packwiz
- Detects downloadable resourcepacks and shaders
- Supports github parsing[¹](#github-rate-limits)
- Loose modrinth search
- User friendly toml config
- Multiple output formats at once

---
### GitHub rate limits

GitHub has limited requests per hour (up to 60), this means that if you have more than 60 mods, the rest will be excluded from github search.

To solve this, you can authorize in application. \
You need to create personal key [here](https://github.com/settings/tokens) (with no permissions), and pass it as argument to script along with your username, like:
```
mmc-export -i modpack -f format --github-auth username:token
```
I recommend you to store tokens in enviroment variables for security reasons.

# How to Use
```
mmc-export -i modpack.zip -c config.toml -f Modrinth packwiz -o converted_modpacks
```
It's recommended to fill config at least with basic info like name and version, some launchers can fail import if these values are empty.
## Syntax:
```
mmc-export [-h] [-c CONFIG] -i INPUT -f FORMAT [-o OUTPUT] [--github-auth GITHUB_AUTH] [--modrinth-search SEARCH_TYPE] [--exclude-providers PROVIDERS] [--exclude-forbidden]
```

### Explanation:

```
-h --help: prints help
-i --input: path to modpack, must be zip file exported from MultiMC.
-c --config: path to config, used to fill the gaps like description or losted mods.
-f --format: output formats, must be separated by spaces.
-o --output: directory where converted zip files will be stored.
--github-auth: GitHub Auth in format username:token
--modrinth-search: modrinth search accuracy
--exclude-providers: providers you wish to exclude from search
--exclude-forbidden: set to not ignore CF distribution flag. Must be enabled for public modpacks.
```

`--format` options (case-sensitive): 
- `CurseForge`
- `Modrinth`
- `packwiz`
- `Intermediate` (only for debugging, may contain sensitive data like username)

`--exclude-providers` options (case-sensitive): 
- `CurseForge`
- `Modrinth`
- `GitHub`

`--modrinth-search` options:
- `exact` - by hash (default)
- `accurate`- by hash or slug
- `loose` - by hash or long name

The example for the optional `--config` file [can be found here](example_config.toml). 

For example, it can help in cases where the script says
> No config entry found for resource: ModName
Then you should add an entry to the end of the config like so:

```
[[Resource]]
name = "ModName"
filename = "the_name_of_the.jar" 
url = "https://cdn.modrinth.com/data/abcdefg/versions/1.0.0/the_name_of_the.jar"
```

# How to Install / Update
```
pip install -U mmc-export
```
