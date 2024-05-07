# Use the nlcd_download_converter with or without a nlcd_classifications.csv file. See the 
# mock_csv_file function for an example of how to create a nlcd_classifications.csv file to apply 
# project specific manning's N values for each NLCD land cover class.

import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.spatially_varied_mannings_n import get_nlcd_and_convert
from src.spatially_varied_mannings_n import export_default_csv

input_aoi_path = "path to aoi file"
output_directory = "path to output directory"
nlcd_classifications_path = "path to nlcd_classifications.csv file" # or None

## Run the function with an nlcd_classifications.csv file
# get_nlcd_and_convert(input_aoi_path, output_directory, nlcd_classifications_path)

## Run the function without an nlcd_classifications.csv file (use default nlcd code<->mannings_n conversion)
# get_nlcd_and_convert(input_aoi_path, output_directory)

## If you don't have an nlcd_classifications.csv file and want to define the conversion values, export 
## the default lookup table to use as a template
# output_csv = "path to an output csv file"
# export_default_csv(output_csv)

