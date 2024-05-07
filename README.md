ffrd-model-developer
==============================

FFRD

Utilities to help develop ffrd specification hec-ras models

==============================

spatially_varied_curve_numbers.py
==============================
This script has two primary functions:
(1) to download SSURGO soil survey data from a NRCS USDA WFS within the extent of an input aoi vector file
(2) create a hydrologic group vector file from an input NRCS USDA soil data vector file

For more information on USDA Soil Data Web Services, please visit the USDA NRCS Web Services help page

==============================  
Two primary functions exists in spatially_varied_curve_numbers.py: 

**spatially_varied_curve_numbers(aoi_path, output_path)**  

Description: This function downloads SSURGO soil survey data from the USDA NRCS Soil Data WFS and saves the data to a vector file.  

- aoi_path (str):     Path to the input vector file defining the study area; file format must be supported by Fiona (see geopandas.read_file() for more information)  
- output_path (str):  Path to the desired output where the vector file will be saved; the file format is determined by the file extension (e.g., .shp, .gpkg, etc); file format must be any OGR data source supported by Fiona  (see geopandas.GeoDataFrame.to_file() for more information)
        


**get_soils_hydro_group(soils_path, output_path)** 

Description:        This function downloads the component soil data of interest (mukey, comppct_r, hydgrp) from the USDA NRCS 
                            https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest for the mukey values in the input ssurgo soils vector data. 
                            Based on the max comppct_r grouped by hydgrp for each mukey, a hydrologic group (hydgrp) is determined for each mukey.
                            The component soil data and hydrologic group classification data are saved to CSV files
                            (component_source_data.csv and hydrogroup_data.csv, respectively). The hydrogroup data is merged with the the soils data
                            downloaded from the WFS and saved to an output vector file. 
                            
- soils_path (str):   Path to the input ssurgo soils vector file;   typically previously downloaded with spatially_varied_curve_numbers();  
file format must be supported by Fiona (see geopandas.read_file() for more information)
- output_path (str):  Path to the desired output where the vector file will be saved; the file format is determined by the file extension (e.g., .shp, .gpkg, etc); file format must be any OGR data source supported by Fiona  (see geopandas.GeoDataFrame.to_file() for more information); component soil data and hydrologic group classification data are saved to CSV files in the same folder as the output vector file
 

Example Usage: See /workspaces/fema-open-source-temp/example_usage/run_get_ssurgo_soils.py

Outstanding Tasks:
    + pin python in environment


==============================
nlcd_downloader_converter.py
==============================
Example Usage: See /workspaces/fema-open-source-temp/example_usage/run_nlcd_downloader_converter.py

This script can be used to  download NLCD_2021_Land_Cover_L48 (US) landcover from www.mrlc.gov WCS within the extent of an 
input polygon vector file. Downloaded NLCD data is also converted to Mannings n values using the provided input CSV file.
Images for large extents are downloaded in tiles and then merged together. The output tif image is in WGS 84; EPSG:4326 
coordinate system.

Files are saved in the same directory as the input shapefile

This code was largely built off of the LandCoverDownloader provided in the github repo below:
NLCD Downloader Reference: https://github.com/reirby/LandCoverDownloader
This was utilized through an MIT License provided within the repo.

One primary function exists in nlcd_downloader_converter.py: 

def get_nlcd_and_convert(aoi_path, output_directory, nlcd_classifications_path = None)
        aoi_path (str): The path to the file containing area of interest. The full extent will be used to subset the NLCD data.
        file format must be supported by Fiona (see geopandas.read_file() for more information)

        output_directory (str): The path to the directory where the output tif files will be saved.
        
        nlcd_classifications_path (str): The path to the CSV file that contains the Mannings n values for each NLCD classification.
            CSV column headers should be: 'value', 'nlcd_name', 'mannings_n'
            If no csv file is provided, a default one will be generated using the function mock_csv_file()


NLCD Legend Reference: https://www.mrlc.gov/data/legends/national-land-cover-database-class-legend-and-description


