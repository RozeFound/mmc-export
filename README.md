# MultiMC advanced exporter
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/mmc-export)](https://www.python.org)
[![PyPI version](https://img.shields.io/pypi/v/mmc-export?label=mmc-export&color=%2347a637)](https://pypi.org/project/mmc-export)
[![PyPI downloads](https://img.shields.io/pypi/dm/mmc-export?color=%23894bbf)](https://pypistats.org/packages/mmc-export)
[![GitHub license](https://img.shields.io/github/license/RozeFound/mmc-export)](/LICENSE)

Since MultiMC export features are very limited, I created a script that solves this problem, with this script you can export MultiMC pack to any popular format (e.g. curseforge, modrinth, packwiz). MultiMC forks which didn't changed export format much also supported.
**[PrismLauncher](https://github.com/PrismLauncher/PrismLauncher) apparently already have builtin Modrinth export feature starting with version 7.0**

<table class="alert-warn" align=center>
<tr>
    <td> ⚠️ </td>
    <td>
        mmc-export development is currently in <b>the maintenance-only mode</b>.
        This is to show that any abnormal lack of activity isn't going to mean it is
        no longer maintained. mmc-export considered feature-complete, and only will be updated when bugs arrive.
    </td>
</tr>
</table>

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
If you authenticate with GitHub using `mmc-export gh-login`, the limit will be removed and requests will be faster. You can always log out with `mmc-export gh-logout`.

If you don't want to use github search by some reason, you can specify `--exclude-providers GitHub` as argument.

# How to Use
```
mmc-export -i modpack.zip -c config.toml -f Modrinth packwiz -o converted_modpacks
```
It's recommended to fill config at least with basic info like name and version, some launchers can fail import if these values are empty.

## Sub-commands

`gh-login` - to authrize GitHub \
`gh-logout` - to get info how to deauthorize GitHub 

`purge-cache` - to purge cache. Available arguments:
```
--web: to delete requests cache and downloaded mods
--files: to delete hashes cache
--all: equivalent to --web --files, deletes all cache (default)
```

## Syntax
```
mmc-export [sub-command] [-h] [-c CONFIG] -i INPUT -f FORMAT [-o OUTPUT] [-v VERSION] [--modrinth-search SEARCH_TYPE] [--exclude-providers PROVIDERS]
```

### Explanation
```
-h --help: prints help
-i --input: path to modpack, must be zip file exported from MultiMC.
-c --config: path to config, used to fill the gaps like description or lost mods.
-f --format: output formats, must be separated by spaces.
-o --output: directory where converted zip files will be stored.
-v --version: specify modpack version, will be overriden by config's value if exists
--modrinth-search: modrinth search accuracy
--exclude-providers: providers you wish to exclude from search
--provider-priority: providers priority used for packwiz
--skip-cache: don't use web cache in this run
--scheme: output filename formatting scheme, more info in #scheme-formatting
```
> All paths can be relative to current working directory or absolute.

`--format` options (case-sensitive): 
- `CurseForge`
- `Modrinth`
- `packwiz`
- `Intermediate` (only for debugging, may contain sensitive data like username)

`--exclude-providers` options (case-sensitive): 
- `CurseForge`
- `Modrinth`
- `GitHub`

`--provider-priority` options (case-sensitive): 
- `CurseForge`
- `Modrinth`
- `Other` or `GitHub`

`--modrinth-search` options:
- `exact` - by hash (default)
- `accurate` - by hash or slug
- `loose` - by hash, slug or long name

The example for the optional `--config` file [can be found here](example_config.toml). 

For example, if the script says

> No config entry found for resource: ModName

Then you should add **one** of the following entries to the end of the config:

#### Specify source URL
```
[[Resource]]
name = "ModName"
filename = "the_name_of_the.jar" 
url = "https://cdn.modrinth.com/data/abcdefg/versions/1.0.0/the_name_of_the.jar"
```
#### Hide the warning
```
[[Resource]]
name = "ModName"
filename = "the_name_of_the.jar" 
action = "ignore"
```
#### Explicitly move to overrides
```
[[Resource]]
name = "ModName"
filename = "the_name_of_the.jar" 
action = "override"
```
#### Delete the file altogether
```
[[Resource]]
name = "ModName"
filename = "the_name_of_the.jar" 
action = "remove"
```
#### Make the mod optional
Append `optional = true` to any of above

#### Delete any file
This can be defined to delete any file that isn't downloadable from CurseForge/Modrinth, e.g. mod config or metadata file.
```
[[File]]
name = "Useless file.txt"
action = "remove"
```

## Scheme Formatting

Must be used as `--scheme "{keyword}_Literally any text"` without file extension, follows python's [format string syntax](https://docs.python.org/3/library/string.html#format-string-syntax)

#### Available keywords: 
- `abbr` - provider abbreviation, usually 2 capitals, e.g. `MR`, `CF`
- `format` - full format name, e.g. `CurseForge`, `Packwiz`
- `name` same as `pack.name` - modpack name
- `version` same as `pack.version` - modpack version
- `pack` - pointer to [Intermediate](mmc_export/Helpers/structures.py#L50-L66) structure

Default scheme is as simple as `{abbr}_{name}`

***Caution: if you don't use any format specifc keywords, output files will overwrite the same file several times***, can be ignored if you output to only one format.
Also, be aware of your filesystem limitations, unsupported characters may lead to an error, or inaccesible file.

# How to Install / Update
```
pip install -U mmc-export
```
