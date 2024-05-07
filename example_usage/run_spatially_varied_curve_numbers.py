import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.spatially_varied_curve_numbers import generate_soils_classes

aoi = "path to area of interest polygon file"
output_directory = "path to output directory" 
aoi = "/workspaces/fema-open-source-temp/data/ssurgo/tx_huc4.gpkg"
output_directory = "/workspaces/fema-open-source-temp/data/ssurgo/txhuc4_test" 

## run the full workflow (get ssurgo soils data, get hydro group, and generate soil classes)
generate_soils_classes(aoi, output_directory)

