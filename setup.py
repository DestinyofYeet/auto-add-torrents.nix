from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().splitlines()

setup(
    name="auto-add-torrents",
    install_requires=install_requires,
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    py_modules=["main", "log"],
    entry_points={
        "console_scripts": ["auto-add-torrents=main:main"]
    }
)
