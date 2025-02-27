#!/usr/bin/env python3
import os
import sys
import re
import json
import argparse
import datetime
import hashlib

try:
    import yaml
except ImportError:
    yaml = None

def check_project_structure(project_path, target_inv=None):
    """
    Check the project folder structure and file naming conventions.
    If target_inv is provided, only check that investigation.
    Returns a list of error messages.
    """
    errors = []
    # Check for README.md at project root.
    readme_path = os.path.join(project_path, "README.md")
    if not os.path.isfile(readme_path):
        errors.append("Project root must contain a README.md file.")

    # Check for data/ folder.
    data_path = os.path.join(project_path, "data")
    if not os.path.isdir(data_path):
        errors.append("Project must contain a data/ folder.")
        return errors

    # Ensure data/ contains only files.
    for item in os.listdir(data_path):
        item_full = os.path.join(data_path, item)
        if os.path.isdir(item_full):
            errors.append(f"data/ folder must only contain set-related files, but found subfolder: {item}")

    # Define regex patterns for file types.
    source_pattern    = re.compile(r'^(?P<inv>[A-Za-z0-9_]+)-source\..+$')
    raw_pattern     = re.compile(r'^(?P<inv>[A-Za-z0-9_]+)-raw\..+$')
    tidy_pattern    = re.compile(r'^(?P<inv>[A-Za-z0-9_]+)\.tsv$')
    sidecar_pattern = re.compile(r'^(?P<inv>[A-Za-z0-9_]+)\.yml$')

    # Group files by investigation name.
    investigations = {}  # { inv_name: { 'source': [], 'raw': [], 'tidy': [], 'sidecar': [] } }
    for file in os.listdir(data_path):
        # Allow .gitignore and .DS_File to be present
        if file in {".gitignore", ".DS_Store"}:
            continue

        file_path = os.path.join(data_path, file)
        if not os.path.isfile(file_path):
            continue

        matched = False
        for ftype, pattern in [('source', source_pattern),
                               ('raw', raw_pattern),
                               ('tidy', tidy_pattern),
                               ('sidecar', sidecar_pattern)]:
            m = pattern.match(file)
            if m:
                matched = True
                inv_name = m.group('inv')
                investigations.setdefault(inv_name, {'source': [], 'raw': [], 'tidy': [], 'sidecar': []})
                investigations[inv_name][ftype].append(file)
                break
        if not matched:
            errors.append(f"File '{file}' does not match any known naming pattern.")

    # If target investigation specified, filter the investigations.
    if target_inv:
        if target_inv not in investigations:
            errors.append(f"Investigation '{target_inv}' not found in data folder.")
            investigations = {}
        else:
            investigations = {target_inv: investigations[target_inv]}

    # Check each investigation.
    for inv, files_dict in investigations.items():
        # Investigation name must be alphanumeric (and underscores).
        if not re.fullmatch(r"[A-Za-z0-9_]+", inv):
            errors.append(f"Investigation name '{inv}' contains invalid characters. Only alphanumeric and '_' are allowed.")

        # Exactly one raw, tidy, and sidecar file must be present.
        if len(files_dict['raw']) != 1:
            errors.append(f"Investigation '{inv}' must have exactly one raw file; found {len(files_dict['raw'])}.")
        if len(files_dict['tidy']) != 1:
            errors.append(f"Investigation '{inv}' must have exactly one tidy data file; found {len(files_dict['tidy'])}.")
        if len(files_dict['sidecar']) != 1:
            errors.append(f"Investigation '{inv}' must have exactly one sidecar file; found {len(files_dict['sidecar'])}.")

        # source file is optional (at most one allowed).
        if len(files_dict['source']) > 1:
            errors.append(f"Investigation '{inv}' must have at most one source file; found {len(files_dict['source'])}.")

    # Optionally, check content of tidy and sidecar files.
    for inv, files_dict in investigations.items():
        if files_dict['tidy']:
            tidy_file = files_dict['tidy'][0]
            tidy_path = os.path.join(data_path, tidy_file)
            try:
                with open(tidy_path, encoding='utf-8') as f:
                    header_line = f.readline()
                    if "\t" not in header_line:
                        errors.append(f"Tidy data file '{tidy_file}' does not appear to be tab-separated.")
            except UnicodeDecodeError:
                errors.append(f"Tidy data file '{tidy_file}' is not encoded in UTF-8.")
            except Exception as e:
                errors.append(f"Error reading tidy data file '{tidy_file}': {str(e)}")

        if files_dict['sidecar']:
            sidecar_file = files_dict['sidecar'][0]
            sidecar_path = os.path.join(data_path, sidecar_file)
            if yaml is not None:
                try:
                    with open(sidecar_path, 'r', encoding='utf-8') as f:
                        yaml.safe_load(f)
                except Exception as e:
                    errors.append(f"Sidecar file '{sidecar_file}' is not valid YAML: {str(e)}")
            else:
                errors.append("PyYAML is not installed. Cannot check sidecar YAML files.")

    return errors

def load_yaml_fields(yml_file):
    """
    Load the YAML file and convert its mapping into a list of field definitions.
    Each YAML key becomes the 'name' attribute of the field.
    """
    try:
        with open(yml_file, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
    except Exception as e:
        sys.exit(f"Error loading YAML file {yml_file}: {e}")

    if not isinstance(yaml_data, dict):
        sys.exit(f"Error: Expected a YAML mapping at the root of {yml_file}")

    fields = []
    for field_name, field_def in yaml_data.items():
        if not isinstance(field_def, dict):
            print(f"Warning: Field '{field_name}' is not a mapping; skipping.", file=sys.stderr)
            continue
        new_field = {"name": field_name}
        new_field.update(field_def)
        fields.append(new_field)
    return fields

def compute_file_info(tsv_path):
    """Compute file size in bytes and md5 hash for a given file."""
    try:
        bytes_size = os.path.getsize(tsv_path)
    except Exception as e:
        sys.exit(f"Error obtaining file size for {tsv_path}: {e}")

    md5_hash = hashlib.md5()
    try:
        with open(tsv_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5_hash.update(chunk)
    except Exception as e:
        sys.exit(f"Error computing md5 for {tsv_path}: {e}")
    return bytes_size, md5_hash.hexdigest()

def package_investigations(target_inv=None):
    """
    Create a datapackage.json file at the top level.
    If target_inv is provided, package only that investigation;
    otherwise, package all investigations found in the data/ folder.
    
    For each investigation:
      - The resource name is inferred from the sidecar YAML filename.
      - The corresponding TSV file is expected at data/<name>.tsv.
      - The file size and md5 hash are computed if the TSV file exists.
      - The sidecar YAML file (input schema) is loaded and converted to a list of fields.
      - Additional metadata (profile, format, mediatype, encoding, dialect, licenses, and created date)
        is added as per the original bash script.
    """
    import os, sys, json, datetime

    project_path = os.getcwd()
    data_path = os.path.join(project_path, "data")
    if not os.path.isdir(data_path):
        sys.exit("Error: data/ folder not found in the current project directory.")

    # Collect all sidecar YAML files in data/ folder.
    investigations = {}
    for file in os.listdir(data_path):
        if file.endswith(".yml"):
            inv_name = os.path.splitext(file)[0]
            investigations[inv_name] = os.path.join(data_path, file)

    # If a target investigation is specified, filter the list.
    if target_inv:
        if target_inv not in investigations:
            sys.exit(f"Error: Investigation '{target_inv}' not found (no corresponding .yml file in data/).")
        investigations = {target_inv: investigations[target_inv]}

    resources = []
    # Use a single timestamp for all resources.
    created = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for inv, yml_file in investigations.items():
        # Construct TSV file path as data/<inv>.tsv.
        tsv_path = os.path.join(data_path, f"{inv}.tsv")
        if os.path.isfile(tsv_path):
            bytes_size, hash_hex = compute_file_info(tsv_path)
        else:
            print(f"Warning: TSV file '{tsv_path}' not found. Using placeholder values.", file=sys.stderr)
            bytes_size = 0
            hash_hex = ""

        # Load field definitions from the sidecar YAML.
        fields = load_yaml_fields(yml_file)

        resource = {
            "profile": "tabular-data-resource",
            "name": inv,
            "path": f"data/{inv}.tsv",
            "format": "tsv",
            "mediatype": "text/tab-separated-values",
            "encoding": "utf-8",
            "bytes": bytes_size,
            "hash": hash_hex,
            "schema": {
                "fields": fields
            },
            "dialect": {
                "header": True,
                "headerRows": [1],
                "headerJoin": " ",
                "commentChar": "#",
                "delimiter": "\t",
                "lineTerminator": "\r\n",
                "quoteChar": "\"",
                "doubleQuote": True,
                "skipInitialSpace": False
            },
            "licenses": [
                {
                    "name": "CC0",
                    "title": "Creative Commons CC0",
                    "path": "https://creativecommons.org/publicdomain/zero/1.0/"
                }
            ],
            "created": created
        }
        resources.append(resource)

    # Use the current directory name as the package name.
    package_name = os.path.basename(os.path.abspath(project_path)) or "defaultdata-package"
    datapackage = {
        "name": package_name,
        "resources": resources
    }

    out_file = os.path.join(project_path, "datapackage.json")
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(datapackage, f, indent=2)
        print(f"Created datapackage.json with {len(resources)} resource(s).")
    except Exception as e:
        sys.exit(f"Error writing datapackage.json: {e}")

def cmd_check(args):
    # The investigation (if given) is the first argument.
    target_inv = args.investigation
    project_folder = os.getcwd()
    errors = check_project_structure(project_folder, target_inv)
    if errors:
        print("Validation errors found:")
        for err in errors:
            print(" - " + err)
        sys.exit(1)
    else:
        print("All checks passed.")
        sys.exit(0)

def cmd_package(args):
    target_inv = args.investigation
    package_investigations(target_inv)
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(
        description="defaultdata: Tool for validating project structure and packaging investigation schemas into datapackage.json."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'check' subcommand: optional investigation name.
    check_parser = subparsers.add_parser("check", help="Check project folder structure.")
    check_parser.add_argument("investigation", nargs="?", default=None,
                                 help="Investigation name (if omitted, all investigations are checked)")
    check_parser.set_defaults(func=cmd_check)

    # 'package' subcommand: optional investigation name.
    package_parser = subparsers.add_parser("package", help="Create datapackage.json from investigation sidecar YAML(s).")
    package_parser.add_argument("investigation", nargs="?", default=None,
                                help="Investigation name (if omitted, all investigations are packaged)")
    package_parser.set_defaults(func=cmd_package)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()