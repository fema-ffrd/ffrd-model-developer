"""
This script can be used to download SSURGO soil survey data from 
a NRCS USDA WFS within the extent of an input aoi vector file.

Refer to the README.md file for more information
"""

import geopandas as gpd
import pandas as pd
import math
import multiprocessing as mp
import os
import requests
import ssl
import warnings

from shapely.geometry import box

# Disable pandas warnings
warnings.filterwarnings("ignore")

# Set pyogrio as the default engine for geopandas ( better performance )
gpd.options.io_engine = "pyogrio"

# Disable SSL certificate verification
## NOTE: This is needed for running in some environments - primarily Windows Terminal
ssl._create_default_https_context = ssl._create_unverified_context


def get_data(wfs_url: str):
    """
    Download SSURGO soil survey data from the USDA NRCS Soil Data WFS

    Args:
        wfs_url (str): USDA NRCS Soil Data WFS url

    Returns:
        list: List of geodataframes with the retrieved data & failed urls
    """
    failed_url = None
    for attempt in range(3):
        try:
            gdf_ssurgo = gpd.read_file(
                wfs_url, driver="GML", timeout=120, engine="pyogrio"
            )
        except:
            continue
    if "gdf_ssurgo" in locals() and not gdf_ssurgo.empty:
        return [gdf_ssurgo, failed_url]
    else:
        failed_url = wfs_url
        return [None, failed_url]


def get_failed_data(failed_url_list: list, gdf_ssurgo: list):
    """
    Retry failed urls ( without multiprocessing ) & add the retrieved data to the list of geodataframes

    Args:
        failed_url_list (list): List of failed wfs urls
        gdf_ssurgo (list): List of geodataframes from previously retrieved data

    Returns:
        list: List of geodataframes with all retrieved data
    """
    try:
        rerun_gdf = map(get_data, failed_url_list)
        rerun_results = [result[0] for result in rerun_gdf if result[0] is not None]
        gdf_ssurgo.extend(rerun_results)
        return gdf_ssurgo
    except Exception as e:
        print("An error occurred getting failed items.")


def create_url(min_x: float, min_y: float, max_x: float, max_y: float) -> str:
    """
    This function creates a URL for the SSURGO WFS
    based on the bounding box of the study area.

    Args:
        min_x (float):  Minimum x-coordinate (longitude) of the bounding box
        min_y (float):  Minimum y-coordinate (latitude) of the bounding box
        max_x (float):  Maximum x-coordinate (longitude) of the bounding box
        max_y (float):  Maximum y-coordinate (latitude) of the bounding box

    Returns:
        str: URL for the NRCS USDA Soil Data Mart WFS
    """
    return f"https://sdmdataaccess.nrcs.usda.gov/Spatial/SDMWGS84Geographic.wfs?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=MapunitPoly&BBOX={min_x},{min_y},{max_x},{max_y}&SRSNAME=EPSG:4326&OUTPUTFORMAT=GML3"


def split_extent(extent: tuple, gdf: gpd.GeoDataFrame):
    """
    Split the extent into subextents of approximately 1 square degree each. This function is called when the extent of the
    shapefile is greater than 9 square degrees.

    Args:
        extent (tuple): The extent of the shapefile in the format (min_x, max_x, min_y, max_y)
        gdf (geopandas.geodataframe.GeoDataFrame): The geodataframe of the area of interest (used for
            confirming subextent intersects the area of interest)
    """
    # Size of each subextent (approximately 1 square degree or 100000 meters by 100000 meters)
    min_x, max_x, min_y, max_y = extent
    subextent_size = 0.25  # in degrees

    # add some tile overlap to prevent possible gaps
    tile_margin = 0.0015  # in degrees

    subextents = []

    # Calculate the number of rows and columns
    num_rows = math.ceil((max_y - min_y) / subextent_size)
    num_cols = math.ceil((max_x - min_x) / subextent_size)

    step_x = (max_x - min_x) / num_cols
    step_y = round((max_y - min_y) / num_rows, 8)

    for row in range(num_rows):
        for col in range(num_cols):
            # Calculate the bounds of the subextent
            subextent_min_x = round((min_x + col * step_x) - tile_margin, 8)
            subextent_max_x = round((min_x + (col + 1) * step_x) + tile_margin, 8)
            subextent_min_y = round((min_y + row * step_y) - tile_margin, 8)
            subextent_max_y = round((min_y + (row + 1) * step_y) + tile_margin, 8)

            # Create a box for the subextent
            subextent_box = box(
                subextent_min_x, subextent_min_y, subextent_max_x, subextent_max_y
            )

            # Check if the subextent intersects with the GeoDataFrame
            if gdf.intersects(subextent_box).any():
                # Add the subextent to the list
                subextents.append(
                    (subextent_min_x, subextent_max_x, subextent_min_y, subextent_max_y)
                )

    return subextents


def get_soils_hydro_group(soils_path: str, output_directory: str):
    """
    This function downloads the component soil data of interest (mukey, comppct_r, hydgrp) from the USDA NRCS
    https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest for the mukey values in the input ssurgo soils vector data.

    Based on the max comppct_r grouped by hydgrp for each mukey, a hydrologic group (hydgrp) is determined for each mukey.
    The component soil data and hydrologic group classification data are saved to CSV files
    (component_source_data.csv and hydrogroup_data.csv, respectively). The hydrogroup data is merged with the the soils data
    downloaded from the WFS and saved to an output vector file.

    Args:
        soils_path (str):   Path to the input ssurgo soils vector file; typically previously downloaded with acquire_ssurgo_data();
                            file format must be supported by Fiona (see geopandas.read_file() for more information)

        output_directory (str):  Path to the desired output where the vector file will be saved;
                            component soil data and hydrologic group classification data are saved to CSV files in the same folder as the output vector file
    """
    # Import the soils vector data
    soils_gdf = gpd.read_file(soils_path)

    # Get the mukey values as list, set as string

    mukey_list = soils_gdf["mukey"].tolist()
    mukey_list = list(set(mukey_list))  # get unique values
    aoi_mukey = [str(item) for item in mukey_list]

    # Prepare the SQL query for the REST API
    # Get the component data (mukey, comppct_r, hydgrp) for the mukey values
    url = "https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest"
    query = f"SELECT mukey, comppct_r, hydgrp FROM component WHERE mukey IN ({','.join(aoi_mukey)})"

    data = {"format": "json", "query": query}

    print(
        f"Getting the component soil data for {len(aoi_mukey)} mukey values in input SSURGO file..."
    )

    # Send the request
    response = requests.post(url, json=data)

    if response.status_code == 200:
        result = response.json()
        print("Creating hydrogroup vector file...")

        # Convert the result to a pandas DataFrame
        df = pd.DataFrame(result["Table"])
        df.columns = ["mukey", "comppct_r", "hydgrp"]
        df["comppct_r"] = df["comppct_r"].astype(float)

        # Save the DataFrame to a CSV file
        df.to_csv(os.path.join(output_directory, "component_source_data.csv"))

        # Group by 'hydgrp' and 'mukey', calculate sum, and rename columns
        grouped_data = df.groupby(["hydgrp", "mukey"])["comppct_r"].sum().reset_index()
        grouped_data.columns = ["hydgrp", "mukey", "pct"]

        # Find rows with maximum 'pct' value for each 'mukey'
        hydrogroup_data = grouped_data.loc[
            grouped_data.groupby("mukey")["pct"].idxmax()
        ]

        hydrogroup_data = hydrogroup_data.reset_index(drop=True)
        hydrogroup_data.to_csv(os.path.join(output_directory, "hydrogroup_data.csv"))

        # Convert 'mukey' to int in both dataframes
        soils_gdf["mukey"] = soils_gdf["mukey"].astype(int)
        hydrogroup_data["mukey"] = hydrogroup_data["mukey"].astype(int)

        # join the hydro_data table to the soils_gdf based on mukey in hydrogroup_data and MUKEY in soils_gdf
        soils_gdf = soils_gdf.merge(
            hydrogroup_data, left_on="mukey", right_on="mukey", how="outer"
        )
        soils_gdf = soils_gdf.dissolve(by="hydgrp").reset_index()

        # rename hydgrp to Soil_Class
        soils_gdf.rename(columns={"hydgrp": "Soil_Class"}, inplace=True)

        # for every value in Soil_Class, delete the record if value is None
        soils_gdf = soils_gdf[soils_gdf["Soil_Class"].notnull()]

        # for every value in Soil_Class, replace "/" with "-"
        soils_gdf["Soil_Class"] = soils_gdf["Soil_Class"].str.replace("/", "-")

        # Only keep the soil_class and geometry columns
        soils_gdf = soils_gdf[["Soil_Class", "geometry"]]

        # write the output to a vector file
        output_soils_classes = os.path.join(
            output_directory, "ssurgo_soil_classes.gpkg"
        )
        soils_gdf.to_file(output_soils_classes)

    else:
        print("Error:", response.status_code)
        print(response.text)  # This will print the error message if any


def acquire_ssurgo_data(aoi_path: str, output_directory: str):
    """
    This function downloads SSURGO soil survey data from the USDA NRCS Soil Data WFS
    and saves the data to a vector file.

    Args:
        aoi_path (str):     Path to the input vector file defining the study area;
                            file format must be supported by Fiona (see geopandas.read_file() for more information)

        output_directory (str):  Path to the desired output directory where the vector file will be saved;

    Returns:
        output_ssurgo (str): Path to the output vector file
    """

    # Read the extent/study area into geodataframe, project to WGS84 (EPSG:4326), get the bounding box, buffer it by 0.05 degrees
    gdf = gpd.read_file(aoi_path)
    original_crs = gdf.crs
    gdf = gdf.to_crs(4326)
    min_x, min_y, max_x, max_y = gdf.total_bounds

    min_x -= abs(max_x - min_x) * 0.05
    min_y -= abs(max_y - min_y) * 0.05
    max_x += abs(max_x - min_x) * 0.05
    max_y += abs(max_y - min_y) * 0.05

    extent = (min_x, max_x, min_y, max_y)

    # get the span of the bounding box
    span_x = abs(max_x - min_x)
    span_y = abs(max_y - min_y)
    area = span_x * span_y
    print(f"Study area with buffer: {area} sq. deg.")

    tile_extents = split_extent(extent, gdf)
    url_list = []

    # Create urls
    for i, ext in enumerate(tile_extents):
        min_x, max_x, min_y, max_y = ext
        # Create the WFS URL, read the WFS into a GeoDataFrame
        wfs_url = create_url(min_x, min_y, max_x, max_y)
        url_list.append(wfs_url)

    # Get the data
    print("Acquiring SSURGO data...")
    num_cores = mp.cpu_count()
    with mp.Pool(int(num_cores / 4)) as pool:
        results = pool.map(get_data, url_list)

        # Get the geodataframes and failed urls
    gdf_ssurgo = [result[0] for result in results if result[0] is not None]

    failed_url_list = [
        failed_url[1] for failed_url in results if failed_url[1] is not None
    ]

    print(f"Results for {len(results)} of {len(url_list)} tiles collected")

    # Retry failed URLs
    if failed_url_list:
        print("Retrying failed URLs...")
        gdf_ssurgo = get_failed_data(failed_url_list, gdf_ssurgo)

    # Check if any data was retrieved
    if not any(not gdf.empty for gdf in gdf_ssurgo):
        raise Exception(
            "The API is not responding or no data was retrieved. Wait and try again."
        )

    # Concat the geodataframes
    merged_gdf = pd.concat(gdf_ssurgo, ignore_index=True)
    merged_gdf = merged_gdf.set_crs(gdf.crs)

    # Remove duplicate data
    print("Removing duplicate data...")
    merged_gdf = merged_gdf.drop_duplicates(subset=["geometry", "mukey"])

    # Reproject to original CRS
    merged_gdf.to_crs(original_crs, inplace=True)
    gdf.to_crs(original_crs, inplace=True)

    # Clip results to AOI
    print("Clipping results to AOI...")
    soils_gdf = gpd.clip(merged_gdf, gdf)
    soils_gdf.to_crs(4326, inplace=True)

    # Export the data
    print("Exporting SSURGO data results...")
    output_ssurgo = os.path.join(output_directory, "ssurgo_data.gpkg")
    soils_gdf.to_file(output_ssurgo, driver="GPKG")

    return output_ssurgo


def generate_soils_classes(input_aoi_file: str, output_directory: str):
    """Download SSURGO soil survey data from the USDA NRCS Soil Data WFS, then convert to
    hydrologic group classification data and save to output directory

    Args:
        input_aoi_file (str): Path to the input vector file defining the study area
        output_directory (str): Path to the desired output directory where various datasets will be saved
    """

    downloaded_ssurgo = acquire_ssurgo_data(input_aoi_file, output_directory)
    get_soils_hydro_group(downloaded_ssurgo, output_directory)
