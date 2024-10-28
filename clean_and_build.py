#!/usr/bin/env python3
import os
import shutil
import subprocess
import argparse
from pathlib import Path

# Try to use the standard library tomllib (Python 3.11+)
# Otherwise fall back to tomli/toml
try:
    import tomllib as tomli  # for reading
    from tomllib import dump as toml_dump  # will raise error since tomllib is read-only
except ImportError:
    try:
        import tomli  # for reading
        import toml  # for writing
        toml_dump = toml.dump
    except ImportError:
        raise ImportError("Please install toml with: pip install toml")

def increment_version(current_version: str, increment_type: str) -> str:
    """Increment version number based on semver."""
    major, minor, patch = map(int, current_version.split('.'))
    assert increment_type in ['major', 'minor', 'patch'], "Invalid increment type, must be 'major', 'minor', or 'patch'"
    if increment_type == 'major':
        return f"{major + 1}.0.0"
    elif increment_type == 'minor':
        return f"{major}.{minor + 1}.0"
    elif increment_type == 'patch':  # patch
        return f"{major}.{minor}.{patch + 1}"

def update_version(new_version: str = None, increment: str = None):
    """Update version in pyproject.toml."""
    try:
        # Read current pyproject.toml
        with open('pyproject.toml', 'rb') as f:  # Open in binary mode for tomli
            try:
                config = tomli.load(f)
            except tomli.TOMLDecodeError as e:
                print(f"❌ Error in pyproject.toml: {str(e)}")
                print("\nPlease check your pyproject.toml file for duplicate entries.")
                print("Specifically look for duplicate declarations of 'tool.setuptools.packages.find'")
                raise SystemExit(1)
        
        # Get current version
        current_version = None
        if 'project' in config:
            current_version = config['project']['version']
        elif 'tool' in config and 'poetry' in config['tool']:
            current_version = config['tool']['poetry']['version']
        else:
            raise ValueError("Couldn't find version field in pyproject.toml")
        
        # Determine new version
        if increment:
            final_version = increment_version(current_version, increment)
        elif new_version:
            final_version = new_version
        else:
            raise ValueError("Either --version or --increment must be specified")
            
        # Update version in config
        if 'project' in config:
            config['project']['version'] = final_version
        elif 'tool' in config and 'poetry' in config['tool']:
            config['tool']['poetry']['version'] = final_version
        
        # Write back to file
        with open('pyproject.toml', 'w', encoding='utf-8') as f:
            toml_dump(config, f)
        
        print(f"✔ Updated version from {current_version} to {final_version}")
        return final_version
    except Exception as e:
        print(f"❌ Failed to update version: {e}")
        raise

def clean_build_artifacts():
    """Remove build artifacts and cache directories."""
    dirs_to_remove = [
        'build',
        'dist',
        '*.egg-info',
        '__pycache__',
        '.pytest_cache',
        '.coverage',
        '.tox',
        '.mypy_cache'
    ]
    
    for pattern in dirs_to_remove:
        for path in Path('.').rglob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    print("✔ Cleaned build artifacts and caches")

def build_package():
    """Build the Python package."""
    try:
        subprocess.run(['python', '-m', 'build'], check=True)
        print("✔ Built package successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        raise

def publish_to_pypi():
    """Publish the package to PyPI."""
    try:
        subprocess.run(['python', '-m', 'twine', 'upload', 'dist/*'], check=True)
        print("✔ Published to PyPI successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Upload failed: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Build and publish Python package')
    version_group = parser.add_mutually_exclusive_group(required=True)
    version_group.add_argument('--version', '-v', help='New version number (e.g., 1.0.1)')
    version_group.add_argument('--increment', '-i', choices=['major', 'minor', 'patch'], 
                             help='Increment major, minor, or patch version')
    parser.add_argument('--no-publish', action='store_true', help='Skip publishing to PyPI')
    args = parser.parse_args()

    new_version = update_version(args.version, args.increment)
    print(f"Building version {new_version}")
    
    clean_build_artifacts()
    build_package()
    
    if not args.no_publish:
        publish_to_pypi()

if __name__ == '__main__':
    main()
