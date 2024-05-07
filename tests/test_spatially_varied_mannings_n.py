import os
import pytest
import requests

from src.spatially_varied_mannings_n import get_url

@pytest.fixture(scope="module")
def small_extents():
    """Create reusable parameters for testing. These parameters
    are available in the namespace of the test functions.
    """

    # create low and high parameters (integers)
    xmin, xmax, ymin, ymax = 80000, 80100, 1155000, 1155100 # EPSG 5070 to match wcs request args
    extents = (xmin, xmax, ymin, ymax)
    
    yield (extents)


def test_get_url_small_extents(small_extents: tuple):
    """Test the get_url function"""

    # call the get_url function
    wcs_url = get_url(small_extents)
    print(wcs_url)

    # check if the URL is available
    response = requests.get(wcs_url)
    assert response.status_code == 200, f"URL {wcs_url} is not available"

