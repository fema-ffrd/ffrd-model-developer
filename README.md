ffrd-model-developer
==============================

FFRD

Utilities to help develop ffrd specification hec-ras models

While developing your project/tool, keep the following tips in mind:  
- Use the env.yaml file to keep pinned dependencies up-to-date and version controlled  
- Develop tests and run tests during development (see test_python_template.py for instructions)  
- Check your code's quality score using pylint: pylint --fail-under=9 src/ffrd-model-developer/*.py  

Project Organization
------------

    ├── LICENSE
    ├── README.md                <- The top-level README for developers using this project.  
    ├── .devcontainer
    │   ├── devcontainer.json    <- Dev Container specifications  
    │   ├── Dockerfile           <- Container definition for dev environment  
    │   ├── env.yaml             <- The requirements file for reproducing the analysis 
    │   └── README.md            <- Documentation for devcontainerenvironment
    │
    ├── .github  
    │   └── workflows           <- Configurable automated process(es) to run one or more triggered jobs
    │
    ├── data               <- Data used for this project ( ie. input data for processing )
    │
    ├── notebooks          <- Jupyter notebooks. Naming convention is a number (for ordering),
    │                         the creator's initials, and a short `-` delimited description, e.g.
    │                         `1.0-jqp-initial-data-exploration`.
    │
    ├── src                 <- Python source code for use in this project.
    │   ├── __init__.py         <- Package indicator, various uses 
    │
    ├── tests
    │   ├── __init__.py                 <- Package indicator, various uses
    │   └── test_python_template.py     <- Example of how to test functions in src folder
    │
    ├── .gitattributes      <- Handles formatting
    │
    ├── .gitignore          <- Handles which directories to keep out of version control
    │
    ├── .pylintrc           <- Customizations to pylint default settings
    │
    ├── Dockerfile          <- The production Dockerfile used for FFRD tools
    │
    ├── LICENSE             <- MIT license
    │
    ├── README.md           <- Template information
    │


--------

