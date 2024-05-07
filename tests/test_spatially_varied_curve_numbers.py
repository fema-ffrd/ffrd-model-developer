import sys, os
import pytest
import requests


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.spatially_varied_curve_numbers import create_url


@pytest.fixture(scope="module")
def small_extents():
    """Create reusable parameters for testing. These parameters
    are available in the namespace of the test functions.
    """

    # create low and high parameters (floats)
    xmin, xmax, ymin, ymax = -80.0, -79.9, 35.0, 35.1
    extents = (xmin, xmax, ymin, ymax)

    yield (extents)


def test_get_url_small_extents(small_extents: tuple):
    """Test the get_url function"""

    # call the get_url function
    wfs_url = create_url(
        min_x=small_extents[0],
        min_y=small_extents[2],
        max_x=small_extents[1],
        max_y=small_extents[3],
    )

    # check if the URL is available
    response = requests.get(wfs_url)
    assert response.status_code == 200, f"URL {wfs_url} is not available"

