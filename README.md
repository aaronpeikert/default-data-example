# Default Data Example

## Getting Started

`data/` includes the mini example used in the policy.

addionally there is the `defaultdata.py` script which will check that everything in `data/` adhered to the default data standard.

```
chmod +x defaultdata.py
./defaultdata.py check
./defaultdata.py package
```

* `check` will check the basic filestructure and allert you if anything is missing
* `package` will turn the sidecar `yaml`(s) into a Frictionless `datapackage.json`


# Optional

There is a copy of this repo on `GitHub` on which you can test the Frictionless GitHub integration:

Install the package:

```bash
pip install frictionless[github] --pre
pip install 'frictionless[github]' --pre # for zsh shell
```

Read the basic example:

```python
from frictionless import Package

package = Package("https://github.com/aaronpeikert/default-data-example")
print(package.get_resource('happiness').read_rows())
```

In R, you have to download the git repo, but then `frictionless` works as well:

```r
frictionless::read_resource(frictionless::read_package(), "happiness")
```

## Creating a binary (for no python install)

```
pyinstaller --onefile defaultdata.py
```