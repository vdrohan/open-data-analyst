import pytest

from open_data_analyst.geo import haversine_km


def test_same_point_is_zero():
    assert haversine_km(49.2858, -123.1117, 49.2858, -123.1117) == 0


def test_one_degree_of_latitude_is_about_111_km():
    assert haversine_km(49.0, -123.0, 50.0, -123.0) == pytest.approx(111.2, abs=0.2)


def test_symmetric():
    a = haversine_km(49.2858, -123.1117, 49.1913, -122.849)
    b = haversine_km(49.1913, -122.849, 49.2858, -123.1117)
    assert a == pytest.approx(b)
