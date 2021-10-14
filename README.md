# modpack-converter
Convert's one modpack format to another.

Maybe I need to think of a better name...

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

# How to Build

I use poetry to dependency resolving, so first you need to install it \
Poetry have a [variuos ways to install itself](https://python-poetry.org/docs/#installation), the easiest one is to install it from `pip`
But I recommend to it install with [pipx](https://github.com/pypa/pipx) to avoid possible conflicts

First install the pipx:
```
pip install -U pipx
```
Second the poetry:
```
pipx install poetry
```

After it clone this repository, and run 
```
cd modpack-converter
poetry install
```
