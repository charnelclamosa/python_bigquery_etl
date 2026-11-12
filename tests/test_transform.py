import numpy as np
import pandas as pd
import pytest

from src.transform import (
  clean_strings,
  convert_data_types,
  validate_coordinates,
  remove_duplicates,
  strip_internal_spaces,
  str_to_title,
  transform,
)


@pytest.fixture
def nyc_311_df() -> pd.DataFrame:
  return pd.DataFrame(
    {
      "unique_key": [70838962, 70838963, 70838964],
      "agency": ["NYPD", "NYPD ", "DOHMH"],
      "agency_name": [
        "New York City Police Department",
        "  New York City Police Department",
        "Department of Health and Mental Hygiene  ",
      ],
      "complaint_type": ["Noise - Residential", "Noise - Residential", 
        "Rodent"],
      "descriptor": ["Loud Music/Party", "", "   "],
      "incident_zip": [10036.0, 10001.0, np.nan],
      "incident_address": ["605 West  42 Street", " 12 Main St ", None],
      "street_name": ["WEST  42 STREET", "  MAIN   STREET ", None],
      "address_type": ["ADDRESS", "ADDRESS", None],
      "landmark": [None, "CENTRAL PARK", None],
      "city": ["NEW YORK", "NEW YORK", "BROOKLYN"],
      "borough": ["MANHATTAN", "Manhattan ", "BROOKLYN"],
      "park_borough": ["MANHATTAN", "MANHATTAN", "BROOKLYN"],
      "latitude": [40.76096011122231, 40.75, np.nan],
      "longitude": [-73.99861746470174, -73.99, np.nan],
      "park_facility_name": ["Unspecified", "Unspecified", " "],
      "status": ["Closed", "Open", "Closed"],
      "created_date": ["2026-10-22 00:25:53", " 2026-10-22 01:00:00", ""],
      "resolution_action_updated_date": [
        "2026-10-22 02:00:00",
        "2026-10-22 03:00:00",
        "",
      ],
      "facility_type": [np.nan, np.nan, np.nan],
    },
    index=[100, 200, 300],
  )

def test_remove_leading_spaces(nyc_311_df):
  """
  [Happy path] Test if leading spaces will be removed.
  """
  expected_agency_name = "New York City Police Department"
  expected_incident_address = "12 Main St"

  actual = clean_strings(nyc_311_df)

  assert expected_agency_name == actual.loc[200, 'agency_name']
  assert expected_incident_address == actual.loc[200, 'incident_address']

def test_remove_trailing_spaces(nyc_311_df):
  """
  [Happy path] Test if trailing spaces will be removed.
  """
  expected_agency_name = "Department of Health and Mental Hygiene"
  expected_incident_address = "12 Main St"

  actual = clean_strings(nyc_311_df)

  assert expected_agency_name == actual.loc[300, 'agency_name']
  assert expected_incident_address == actual.loc[200, 'incident_address']

def test_empty_str_to_nan(nyc_311_df):
  """
  [Happy path] Test if empty strings will be parsed as missing values.
  """
  actual = clean_strings(nyc_311_df)

  assert pd.isna(actual.loc[300, 'park_facility_name'])
  assert pd.isna(actual.loc[200, 'descriptor'])
  assert pd.isna(actual.loc[300, 'descriptor'])

def test_clean_strings_missing_values(nyc_311_df):
  """
  [Edge case] Test if existing missing values remain missing.
  """
  actual = clean_strings(nyc_311_df)

  assert pd.isna(actual.loc[300, 'incident_address'])
  assert pd.isna(actual.loc[100, 'facility_type'])

def test_clean_strings_does_not_modify_original(nyc_311_df):
  """
  [Edge case] Test if the original DataFrame remains unchanged.
  """
  expected = nyc_311_df.copy(deep=True)

  clean_strings(nyc_311_df)

  pd.testing.assert_frame_equal(expected, nyc_311_df)

def test_convert_numeric_data_types(nyc_311_df):
  """
  [Happy path] Test if numeric strings are converted to numeric values.
  """
  numeric_cols = ['latitude', 'longitude']
  df = nyc_311_df.copy()
  df[numeric_cols] = df[numeric_cols].astype('object')
  df.loc[100, 'latitude'] = "40.760960"
  df.loc[100, 'longitude'] = "-73.998617"

  expected_latitude = 40.760960
  expected_longitude = -73.998617

  actual = convert_data_types(df)

  assert actual.loc[100, 'latitude'] == expected_latitude
  assert actual.loc[100, 'longitude'] == expected_longitude
  assert pd.api.types.is_numeric_dtype(actual['latitude'])
  assert pd.api.types.is_numeric_dtype(actual['longitude'])

def test_convert_datetime_data_types(nyc_311_df):
  """
  [Happy path] Test if datetime strings are converted to timestamps.
  """
  expected_created_date = pd.Timestamp("2026-10-22 00:25:53")
  expected_resolution_date = pd.Timestamp("2026-10-22 02:00:00")

  actual = convert_data_types(nyc_311_df)

  assert actual.loc[100, 'created_date'] == expected_created_date
  assert actual.loc[100, 
    'resolution_action_updated_date'] == expected_resolution_date

def test_invalid_numeric_to_nan(nyc_311_df):
  """
  [Edge case] Test if invalid numeric values are converted to missing values.
  """
  numeric_cols = ['latitude', 'longitude']
  df = nyc_311_df.copy()
  df[numeric_cols] = df[numeric_cols].astype('object')
  df.loc[100, 'latitude'] = "invalid"
  df.loc[100, 'longitude'] = "unknown"

  actual = convert_data_types(df)

  assert pd.isna(actual.loc[100, 'latitude'])
  assert pd.isna(actual.loc[100, 'longitude'])

def test_invalid_datetime_to_nat(nyc_311_df):
  """
  [Edge case] Test if invalid datetime strings are converted to NaT.
  """
  df = nyc_311_df.copy()
  df.loc[100, 'created_date'] = "invalid date"
  df.loc[100, 'resolution_action_updated_date'] = "unknown"

  actual = convert_data_types(df)

  assert pd.isna(actual.loc[100, 'created_date'])
  assert pd.isna(actual.loc[100, 'resolution_action_updated_date'])

def test_missing_values_after_conversion(nyc_311_df):
  """
  [Edge case] Test if existing missing values remain missing.
  """
  actual = convert_data_types(nyc_311_df)

  assert pd.isna(actual.loc[300, 'latitude'])
  assert pd.isna(actual.loc[300, 'longitude'])
  assert pd.isna(actual.loc[300, 'created_date'])
  assert pd.isna(actual.loc[300, 'resolution_action_updated_date'])

def test_convert_data_types_does_not_modify_original(nyc_311_df):
  """
  [Edge case] Test if the original DataFrame remains unchanged.
  """
  expected = nyc_311_df.copy(deep=True)

  convert_data_types(nyc_311_df)

  pd.testing.assert_frame_equal(expected, nyc_311_df)

def test_valid_coordinates(nyc_311_df):
  """
  [Happy path] Test if valid coordinates are preserved.
  """
  expected_latitude = 40.76096011122231
  expected_longitude = -73.99861746470174

  actual = validate_coordinates(nyc_311_df)

  assert actual.loc[100, 'latitude'] == expected_latitude
  assert actual.loc[100, 'longitude'] == expected_longitude

def test_invalid_latitude(nyc_311_df):
  """
  [Edge case] Test if invalid latitude sets both coordinates to missing values.
  """
  df = nyc_311_df.copy()
  df.loc[100, 'latitude'] = 100.0

  actual = validate_coordinates(df)

  assert pd.isna(actual.loc[100, 'latitude'])
  assert pd.isna(actual.loc[100, 'longitude'])

def test_invalid_longitude(nyc_311_df):
  """
  [Edge case] Test if invalid longitude sets both coordinates to missing values.
  """
  df = nyc_311_df.copy()
  df.loc[100, 'longitude'] = -200.0

  actual = validate_coordinates(df)

  assert pd.isna(actual.loc[100, 'latitude'])
  assert pd.isna(actual.loc[100, 'longitude'])

def test_coordinate_boundary_values(nyc_311_df):
  """
  [Edge case] Test if coordinates at the valid boundaries are preserved.
  """
  df = nyc_311_df.copy()
  df.loc[100, ['latitude', 'longitude']] = [-90.0, -180.0]
  df.loc[200, ['latitude', 'longitude']] = [90.0, 180.0]

  actual = validate_coordinates(df)

  assert actual.loc[100, 'latitude'] == -90.0
  assert actual.loc[100, 'longitude'] == -180.0
  assert actual.loc[200, 'latitude'] == 90.0
  assert actual.loc[200, 'longitude'] == 180.0

def test_missing_coordinates(nyc_311_df):
  """
  [Edge case] Test if missing coordinates remain missing.
  """
  actual = validate_coordinates(nyc_311_df)

  assert pd.isna(actual.loc[300, 'latitude'])
  assert pd.isna(actual.loc[300, 'longitude'])

def test_one_missing_coordinate(nyc_311_df):
  """
  [Edge case] Test if one missing coordinate preserves the other valid value.
  """
  df = nyc_311_df.copy()
  df.loc[100, 'latitude'] = np.nan

  expected_longitude = -73.99861746470174

  actual = validate_coordinates(df)

  assert pd.isna(actual.loc[100, 'latitude'])
  assert actual.loc[100, 'longitude'] == expected_longitude

def test_invalid_coordinates_preserve_records(nyc_311_df):
  """
  [Edge case] Test if records are preserved even with invalid coordinates.
  """
  df = nyc_311_df.copy()
  df.loc[100, 'latitude'] = 100.0

  expected_count = len(df)

  actual = validate_coordinates(df)

  assert len(actual) == expected_count
  assert actual.loc[100, 'unique_key'] == 70838962

def test_validate_coordinates_does_not_modify_original(nyc_311_df):
  """
  [Edge case] Test if the original DataFrame remains unchanged.
  """
  expected = nyc_311_df.copy(deep=True)

  validate_coordinates(nyc_311_df)

  pd.testing.assert_frame_equal(expected, nyc_311_df)

def test_remove_duplicates_keep_last(nyc_311_df):
  """
  [Happy path] Test if the last duplicate record is retained.
  """
  df = nyc_311_df.copy()
  duplicate = df.loc[[100]].copy()
  duplicate['agency'] = "DOHMH"
  df = pd.concat([df, duplicate], ignore_index=True)

  expected_count = 3
  expected_agency = "DOHMH"

  actual = remove_duplicates(df, subset=['unique_key'], keep='last')

  assert len(actual) == expected_count
  assert actual.loc[2, 'agency'] == expected_agency

def test_remove_duplicates_keep_first(nyc_311_df):
  """
  [Happy path] Test if the first duplicate record is retained.
  """
  df = nyc_311_df.copy()
  duplicate = df.loc[[100]].copy()
  duplicate['agency'] = "DOHMH"
  df = pd.concat([df, duplicate], ignore_index=True)

  expected_count = 3
  expected_agency = "NYPD"

  actual = remove_duplicates(df, subset=['unique_key'], keep='first')

  assert len(actual) == expected_count
  assert actual.loc[0, 'agency'] == expected_agency

def test_remove_duplicates_keep_false(nyc_311_df):
  """
  [Edge case] Test if all occurrences of duplicated records are removed.
  """
  df = nyc_311_df.copy()
  duplicate = df.loc[[100]].copy()
  df = pd.concat([df, duplicate], ignore_index=True)

  expected_count = 2

  actual = remove_duplicates(df, subset=['unique_key'], keep=False)

  assert len(actual) == expected_count
  assert 70838962 not in actual['unique_key'].values

def test_remove_duplicates_no_duplicates(nyc_311_df):
  """
  [Edge case] Test if records are preserved when there are no duplicates.
  """
  expected_count = len(nyc_311_df)

  actual = remove_duplicates(nyc_311_df, subset=['unique_key'])

  assert len(actual) == expected_count

def test_remove_duplicates_reset_index(nyc_311_df):
  """
  [Happy path] Test if the index is reset after deduplication.
  """
  expected_index = [0, 1, 2]

  actual = remove_duplicates(nyc_311_df, subset=['unique_key'])

  assert actual.index.tolist() == expected_index

def test_remove_duplicates_empty_dataframe(nyc_311_df):
  """
  [Edge case] Test if an empty DataFrame is handled correctly.
  """
  df = nyc_311_df.iloc[0:0].copy()

  actual = remove_duplicates(df, subset=['unique_key'])

  assert actual.empty
  assert len(actual) == 0

def test_remove_duplicates_does_not_modify_original(nyc_311_df):
  """
  [Edge case] Test if the original DataFrame remains unchanged.
  """
  expected = nyc_311_df.copy(deep=True)

  remove_duplicates(nyc_311_df, subset=['unique_key'])

  pd.testing.assert_frame_equal(expected, nyc_311_df)

def test_strip_internal_spaces(nyc_311_df):
  """
  [Happy path] Test if multiple internal spaces are replaced with one space.
  """
  expected_incident_address = "605 West 42 Street"
  expected_street_name = "WEST 42 STREET"

  actual = strip_internal_spaces(nyc_311_df)

  assert actual.loc[100, 'incident_address'] == expected_incident_address
  assert actual.loc[100, 'street_name'] == expected_street_name

def test_strip_internal_leading_trailing_spaces(nyc_311_df):
  """
  [Happy path] Test if leading and trailing spaces are removed.
  """
  expected_incident_address = "12 Main St"
  expected_street_name = "MAIN STREET"

  actual = strip_internal_spaces(nyc_311_df)

  assert actual.loc[200, 'incident_address'] == expected_incident_address
  assert actual.loc[200, 'street_name'] == expected_street_name

def test_strip_internal_spaces_missing_values(nyc_311_df):
  """
  [Edge case] Test if missing values remain missing.
  """
  actual = strip_internal_spaces(nyc_311_df)

  assert pd.isna(actual.loc[300, 'incident_address'])
  assert pd.isna(actual.loc[300, 'street_name'])

def test_strip_internal_spaces_only_whitespace(nyc_311_df):
  """
  [Edge case] Test if whitespace-only strings become empty strings.
  """
  df = nyc_311_df.copy()
  df.loc[100, 'incident_address'] = "   "

  expected_incident_address = ""

  actual = strip_internal_spaces(df)

  assert actual.loc[100, 'incident_address'] == expected_incident_address

def test_strip_internal_spaces_does_not_modify_original(nyc_311_df):
  """
  [Edge case] Test if the original DataFrame remains unchanged.
  """
  expected = nyc_311_df.copy(deep=True)

  strip_internal_spaces(nyc_311_df)

  pd.testing.assert_frame_equal(expected, nyc_311_df)

def test_str_to_title_borough(nyc_311_df):
  """
  [Happy path] Test if uppercase borough names are converted to title case.
  """
  expected_borough = "Manhattan"
  expected_park_borough = "Brooklyn"

  actual = str_to_title(nyc_311_df)

  assert actual.loc[100, 'borough'] == expected_borough
  assert actual.loc[300, 'park_borough'] == expected_park_borough

def test_str_to_title_address(nyc_311_df):
  """
  [Happy path] Test if uppercase addresses are converted to title case.
  """
  expected_street_name = "West  42 Street"
  expected_city = "New York"

  actual = str_to_title(nyc_311_df)

  assert actual.loc[100, 'street_name'] == expected_street_name
  assert actual.loc[100, 'city'] == expected_city

def test_str_to_title_complaint_type(nyc_311_df):
  """
  [Happy path] Test if complaint types are converted to title case.
  """
  expected_complaint_type = "Noise - Residential"

  actual = str_to_title(nyc_311_df)

  assert actual.loc[100, 'complaint_type'] == expected_complaint_type

def test_str_to_title_missing_values(nyc_311_df):
  """
  [Edge case] Test if missing string values remain missing.
  """
  actual = str_to_title(nyc_311_df)

  assert pd.isna(actual.loc[300, 'street_name'])
  assert pd.isna(actual.loc[300, 'address_type'])
  assert pd.isna(actual.loc[300, 'landmark'])

def test_str_to_title_already_title_case(nyc_311_df):
  """
  [Edge case] Test if strings already in title case remain unchanged.
  """
  expected_borough = "Manhattan "

  actual = str_to_title(nyc_311_df)

  assert actual.loc[200, 'borough'] == expected_borough

def test_str_to_title_does_not_modify_original(nyc_311_df):
  """
  [Edge case] Test if the original DataFrame remains unchanged.
  """
  expected = nyc_311_df.copy(deep=True)

  str_to_title(nyc_311_df)

  pd.testing.assert_frame_equal(expected, nyc_311_df)

def test_transform_success(nyc_311_df):
  """
  [Happy path] Test if the transformation process completes successfully.
  """
  expected_count = 3

  actual = transform(nyc_311_df)

  assert isinstance(actual, pd.DataFrame)
  assert len(actual) == expected_count

def test_transform_clean_strings(nyc_311_df):
  """
  [Happy path] Test if string cleaning is applied during transformation.
  """
  expected_agency = "NYPD"
  expected_agency_name = "New York City Police Department"

  actual = transform(nyc_311_df)

  assert actual.loc[1, 'agency'] == expected_agency
  assert actual.loc[1, 'agency_name'] == expected_agency_name

def test_transform_data_types(nyc_311_df):
  """
  [Happy path] Test if numeric and datetime columns are converted.
  """
  actual = transform(nyc_311_df)

  assert pd.api.types.is_numeric_dtype(actual['latitude'])
  assert pd.api.types.is_numeric_dtype(actual['longitude'])
  assert pd.api.types.is_datetime64_any_dtype(actual['created_date'])
  assert pd.api.types.is_datetime64_any_dtype(
    actual['resolution_action_updated_date'])

def test_transform_invalid_coordinates(nyc_311_df):
  """
  [Edge case] Test if invalid coordinates are removed during transformation.
  """
  df = nyc_311_df.copy()
  df.loc[100, 'latitude'] = 100.0

  actual = transform(df)

  assert pd.isna(actual.loc[0, 'latitude'])
  assert pd.isna(actual.loc[0, 'longitude'])

def test_transform_remove_duplicates(nyc_311_df):
  """
  [Edge case] Test if duplicate records are removed during transformation.
  """
  df = nyc_311_df.copy()
  duplicate = df.loc[[100]].copy()
  duplicate['agency'] = "DOHMH"
  df = pd.concat([df, duplicate], ignore_index=True)

  expected_count = 3
  expected_agency = "DOHMH"

  actual = transform(df)

  assert len(actual) == expected_count
  assert actual.loc[2, 'agency'] == expected_agency

def test_transform_missing_values(nyc_311_df):
  """
  [Edge case] Test if missing values are preserved during transformation.
  """
  actual = transform(nyc_311_df)

  assert pd.isna(actual.loc[2, 'park_facility_name'])
  assert pd.isna(actual.loc[2, 'latitude'])
  assert pd.isna(actual.loc[2, 'longitude'])

def test_transform_empty_dataframe(nyc_311_df):
  """
  [Edge case] Test if an empty DataFrame is handled correctly.
  """
  df = nyc_311_df.iloc[0:0].copy()

  actual = transform(df)

  assert actual.empty
  assert len(actual) == 0

def test_transform_does_not_modify_original(nyc_311_df):
  """
  [Edge case] Test if the original DataFrame remains unchanged.
  """
  expected = nyc_311_df.copy(deep=True)

  transform(nyc_311_df)

  pd.testing.assert_frame_equal(expected, nyc_311_df)
