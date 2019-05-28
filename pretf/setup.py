import os
import re

from setuptools import find_namespace_packages, setup


def get_version():
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, "pretf", "cli.py")) as open_file:
        contents = open_file.read()
    match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", contents, re.MULTILINE)
    return match.group(1)


setup(
    name="pretf",
    version=get_version(),
    author="Raymond Butcher",
    author_email="ray.butcher@claranet.uk",
    license="MIT License",
    packages=find_namespace_packages("pretf.*"),
    #modules=["pretf.cli", "pretf.core", "pretf.log"],
    #packages=["pretf.core"],
    entry_points={"console_scripts": ("pretf=pretf.cli:main",)},
    install_requires=["colorama"],
)
