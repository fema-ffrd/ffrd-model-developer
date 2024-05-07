"""
The functions developed in this script can be used to download NLCD_2021_Land_Cover_L48 (US) landcover data from 
www.mrlc.gov WCS within the extent of an input SHP file. Downloaded NLCD data is also converted to Mannings n values 
using input CSV file.

Refer to the README.md file for more information
This code was largely built off of the LandCoverDownloader provided in the github repo below:
NLCD Downloader Reference: https://github.com/reirby/LandCoverDownloader
This was utilized through an MIT License provided within the repo.
"""

import csv
import io
import math
import os
import tempfile

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from osgeo import gdal
from shapely.geometry import box

gdal.DontUseExceptions()


def get_nlcd_and_convert(
    aoi_path: str, output_directory: str, nlcd_classifications_path: str = None
):
    """
    Download the NLCD (2021) landcover data, convert it to Mannings n values using nlcd classifications csv, and
    export nlcd and mannings rasters to output directory.

    Args:
        aoi_path (str): The path to the file containing area of interest. The full extent will be used to subset the NLCD data.
        output_directory (str): The path to the directory where the output tif files will be saved.
        nlcd_classifications_path (str): The path to the CSV file that contains the Mannings n values for each NLCD classification.
            CSV column headers should be: 'value', 'nlcd_name', 'mannings_n'
            If no csv file is provided, a default one will be generated using the function mock_csv_file()
    """

    # validate the CSV file if one if provided
    if nlcd_classifications_path is not None:
        check_fields_in_csv(nlcd_classifications_path)
    else:
        print(
            "No Manning's N CSV file provided. A default lookup table of nlcd codes to mannings values will be used. \
              Please review the output Mannings N values and provide a custom csv lookup if needed. \
              Lookup csv file should contain columns: 'value', 'nlcd_name', 'mannings_n'"
        )

    # get the extent of the shapefile, calculate its are in square degrees
    gdf = read_and_dissolve(aoi_path)
    gdf = gdf.to_crs(4326)
    min_x, min_y, max_x, max_y = gdf.total_bounds
    ext_wgs84 = (min_x, max_x, min_y, max_y)
    span_x = abs(max_x - min_x)
    span_y = abs(max_y - min_y)
    area = span_x * span_y

    # query by 5070 extents (to match 5070 mrlc dataset)
    gdf = gdf.to_crs(5070)
    min_x, min_y, max_x, max_y = gdf.total_bounds
    ext_albers = (min_x, max_x, min_y, max_y)

    # if the area is less than 9 square degrees, just get the whole image, otherwise split it into tiles
    if area <= 9:
        print("Getting the NLCD image...")
        # set the output folder and output image names
        out_img = os.path.join(output_directory, "nlcd_clip.tif")
        out_img_mannings = os.path.join(output_directory, "mannings_n_clip.tif")

        # call functions that download and convert the NLCD data
        wcs_url = get_url(ext_albers)
        get_img(wcs_url, out_img)

        # convert to manning's n raster
        convert_to_mannings(out_img, out_img_mannings, nlcd_classifications_path)
        
        # clip the images to the extent of the shapefile
        clip_image(out_img, out_img, gdf)
        clip_image(out_img_mannings, out_img_mannings, gdf)
    else:
        print("Acquiring NLCD data by chunks...")
        tile_extents = split_extent(ext_albers, gdf)
        failed_img = []
        tile_paths = []
        tile_paths_mannings = []

        for i, ext in enumerate(tile_extents):
            print(f"Getting NLCD image {i+1} out of {len(tile_extents)}")

            wcs_url = get_url(ext)
            out_img = os.path.join(output_directory, f"nlcd_{i}.tif")
            out_img_mannings = os.path.join(output_directory, f"mannings_n_{i}.tif")

            # call functions that download and convert the NLCD data
            result = get_img(wcs_url, out_img)

            # convert to manning's n raster
            convert_to_mannings(out_img, out_img_mannings, nlcd_classifications_path)

            if result == "fail":
                failed_img.append(i)
            else:
                tile_paths.append(out_img)
                tile_paths_mannings.append(out_img_mannings)

        # if image failed, try downloading missed images one more time
        if len(failed_img) > 0:
            for i in failed_img:
                ext = tile_extents[i]
                min_x, max_x, min_y, max_y = ext
                out_img = os.path.join(output_directory, f"nlcd_{i}_{i}.tif")
                out_img_mannings = os.path.join(
                    output_directory, f"mannings_n_{i}_{i}.tif"
                )
                wcs_url = get_url(ext)
                result = get_img(wcs_url, out_img)
                convert_to_mannings(
                    out_img, out_img_mannings, nlcd_classifications_path
                )
                if result == "success":
                    tile_paths.append(out_img)
                    tile_paths_mannings.append(out_img_mannings)
                else:
                    print(f"Failed to acquire tile from url: {wcs_url}.")

        # mosaic tiles back together
        output_mosaic = os.path.join(output_directory, "nlcd_clip.tif")
        output_mosaic_mannings = os.path.join(output_directory, "mannings_n_clip.tif")
        build_mosaic(tile_paths, output_mosaic)
        build_mosaic(tile_paths_mannings, output_mosaic_mannings)

        # remove the individual tiles
        for tile in tile_paths:
            os.remove(tile)

        for tile in tile_paths_mannings:
            os.remove(tile)

        # clip the images
        clip_image(output_mosaic, output_mosaic, gdf)
        clip_image(output_mosaic_mannings, output_mosaic_mannings, gdf)

        # Print the output file paths
        print(f"NLCD image saved to {output_mosaic}")
        print(f"Manning's n raster saved to {output_mosaic_mannings}")

def read_and_dissolve(filepath):
    """
    Read a spatial file, dissolve all the polygons, and return a GeoDataFrame with a valid geometry.

    Args:
        filepath (str): The path to the spatial file.

    Returns:
        GeoDataFrame: A GeoDataFrame with a single, valid geometry.
    """
    # Read the file
    gdf = gpd.read_file(filepath)

    # Dissolve all polygons
    gdf_dissolved = gdf.dissolve()

    # Fix any self-intersections
    gdf_dissolved["geometry"] = gdf_dissolved.geometry.buffer(0)

    return gdf_dissolved


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
    subextent_size = 100000  # in meters

    # add some tile overlap to prevent possible gaps
    tile_margin = 120  # in meters

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


def get_img(wcs_url, fname):
    """
    Download the NLCD data from the WCS URL and save it to the specified file path.

    Args:
        wcs_url (str): The WCS URL from which the NLCD data will be downloaded.
        fname (str): The file path where the downloaded NLCD data will be saved.
    """
    # open the WCS URL
    ds = gdal.Open(wcs_url)

    # Check if the dataset is successfully opened
    if ds is None:
        print("Failed to open WCS dataset")
        return "fail"
    else:
        output_format = "GTiff"
        image_driver = gdal.GetDriverByName(output_format)
        output_ds = image_driver.CreateCopy(fname, ds)

        # Close datasets
        ds = None
        output_ds = None

        return "success"


def build_mosaic(input_imgs, output_mosaic):
    """
    Mosaic the input images into a single file and clip it to the extent of a GeoDataFrame.

    Args:
        input_imgs (list): A list of file paths to the NLCD/Mannings n tiles that will be mosaiced.
        output_mosaic (str): The file path where the mosaiced data will be saved.
    """
    # Set the warp options
    warp_options = gdal.WarpOptions(
        format="GTiff", resampleAlg="near", creationOptions=["COMPRESS=LZW"]
    )

    # Mosaic the input files
    gdal.Warp(output_mosaic, input_imgs, options=warp_options)

def get_url(extent):
    """
    Generate the WCS URL for the NLCD data within the specified extent.

    Resource identified through the following link:
    https://www.mrlc.gov/geoserver/ows?service=WCS&version=2.0.1&request=GetCapabilities

    Args:
        extent (tuple): The extent of the shapefile in the format (min_x, max_x, min_y, max_y)
    """

    min_x, max_x, min_y, max_y = extent
    url = f"https://www.mrlc.gov/geoserver/mrlc_download/NLCD_2021_Land_Cover_L48/wcs?service=WCS&version=2.0.1&request=getcoverage&coverageid=NLCD_2021_Land_Cover_L48&subset=Y({min_y},{max_y})&subset=X({min_x},{max_x})&SubsettingCRS=http://www.opengis.net/def/crs/EPSG/0/5070"

    return url


def convert_to_mannings(image_path, out_img_mannings, nlcd_classifications_path=None):
    """
    Convert the NLCD raster to Mannings n raster using either the provided CSV file or a placeholder,
    and save the results to a new GeoTIFF file.

    Args:
        image_path (str): The path to the NLCD rater that will be converted to Mannings n values.
        out_img_mannings (str): The file path where the Mannings n data will be saved.
        nlcd_classifications_path (str): The path to the CSV file that contains the Mannings n values
            for each NLCD classification. CSV column headers should be: 'value', 'nlcd_name', 'mannings_n'
    """

    # Load CSV file; if not provided, use the default CSV file
    if nlcd_classifications_path is None:
        df = pd.read_csv(mock_csv_file())
    else:
        # Load the CSV file into a DataFrame
        df = pd.read_csv(nlcd_classifications_path)

    # Open the raster file
    with rasterio.open(image_path) as src:
        raster_data = src.read(1)

    # Create a dictionary mapping 'value' to 'mannings_n'
    value_to_manningsn = pd.Series(df.mannings_n.values, index=df.value).to_dict()

    # Vectorize the function so it can operate on the whole array at once
    vectorized_func = np.vectorize(value_to_manningsn.get)

    # Apply the function to the raster data, then ensure in a rasterio-friendly data type
    manningsn_data = vectorized_func(raster_data)
    manningsn_data = manningsn_data.astype("float32")

    # Save the ManningsN data to a new GeoTIFF file
    with rasterio.open(
        out_img_mannings,
        "w",
        driver="GTiff",
        height=manningsn_data.shape[0],
        width=manningsn_data.shape[1],
        count=1,
        dtype=str(manningsn_data.dtype),
        crs=src.crs,
        transform=src.transform,
    ) as dst:
        dst.write(manningsn_data, 1)
        # print(f"Manning's n raster saved to {out_img_mannings}")


def mock_csv_file():
    """
    Create a default NLCD to Manning's N lookup CSV file

    Returns:
        f (io.StringIO): A file-like object containing the default NLCD to Manning's N lookup table.
    """
    # Create csv file
    csv_data = """value,nlcd_name,mannings_n
    11,Open Water,0.03
    12,Perennial Ice/Snow,0.09999
    21,Developed Open Space,0.045
    22,Developed Low Intensity,0.075
    23,Developed Medium Intensity,0.081
    24,Developed High Intensity,0.137
    31,Barren Land,0.03
    41,Deciduous Forest,0.114
    42,Evergreen Forest,0.13
    43,Mixed Forest,0.121
    51,Dwarf Scrub,0.09999
    52,Shrub Scrub,0.04
    71,Herbaceous Grassland,0.035
    72,Herbaceous Sedge,0.09999
    73,Lichens,0.09999
    74,Moss,0.09999
    81,Hay Pasture,0.04
    82,Cultivated Crops,0.04
    90,Woody Wetlands,0.08
    95,Emergent Herbaceous Wetlands,0.079"""

    # Create a file-like object from the csv data
    f = io.StringIO(csv_data)

    return f

def export_default_csv(output_csv):
    """Export the default NLCD to Manning's N lookup table to a CSV file.

    Args:
        output_csv (str): The path to the output CSV file.
    """
    # Create the default CSV file
    f = mock_csv_file()

    # Save the CSV file to the output path
    assert output_csv.endswith(".csv"), "Output path must end with .csv"
    with open(output_csv, "w") as out_file:
        out_file.write(f.getvalue())

    print(f"Default NLCD to Manning's N lookup table saved to {output_csv}")



def check_fields_in_csv(file_path):
    """
    Validate the CSV; check if the required fields are present in the CSV file.

    Args:
        file_path (str): The path to the CSV file that will be validated.

    Raises:
        ValueError: If the required fields are not present in the CSV file.
        FileNotFoundError: If the CSV file is not found.
        csv.Error: If there is an error reading the CSV file.
        Exception: If there is an unexpected error.
    """
    # Check if the required fields are present in the CSV file
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        required_fields = ["value", "nlcd_name", "mannings_n"]
        for field in required_fields:
            if field not in fieldnames:
                raise ValueError(f"Required field '{field}' not found in CSV file")


def clip_image(image_path, out_img, gdf):
    """
    Clip the image to the extent of the GeoDataFrame and save the clipped image to a new file.

    Args:
        image_path (str): The path to the image that will be clipped.
        out_img (str): The file path where the clipped image will be saved.
        gdf (GeoDataFrame): The GeoDataFrame to which the image will be clipped.
    """
    # Open the image
    with rasterio.open(image_path) as src:
        # Clip the image to the GeoDataFrame
        out_image, out_transform = mask(src, gdf.geometry, crop=True)

    # Update the metadata
    out_meta = src.meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform
    })

    # Write the clipped raster to a new file
    with rasterio.open(out_img, "w", **out_meta) as dest:
        dest.write(out_image)