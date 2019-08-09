import numpy as np
import pandas as pd
import geopandas as gpd
from tobler.area_weighted import area_interpolate_binning, area_tables_raster, area_interpolate
from tobler.util.util import _check_presence_of_crs

def harmonize(raw_community, 
              target_year_of_reference,
              weights_method = 'area', 
              extensive_variables = [], 
              intensive_variables = [],
              allocate_total = True,
              raster_path = None,
              codes = [21, 22, 23, 24],
              force_crs_match = True):
    """
    Harmonize Multiples GeoData Sources with different approaches

    Parameters
    ----------

    raw_community : list
        Multiple GeoDataFrames given by a list (see (1) in Notes).
    
    target_year_of_reference : string
        The target year that represents the bondaries of all datasets generated in the harmonization. Could be, for example '2010'.
        
    weights_method : string
        The method that the harmonization will be conducted. This can be set to:
            "area"                          : harmonization according to area weights.
            "land_type_area"                : harmonization according to the Land Types considered 'populated' areas.
            "land_type_Poisson_regression"  : NOT YET INTRODUCED.
            "land_type_Gaussian_regression" : NOT YET INTRODUCED.

    extensive_variables : list
        The names of variables in each dataset of raw_community that contains extensive variables to be harmonized (see (2) in Notes).
        
    intensive_variables : list
        The names of variables in each dataset of raw_community that contains intensive variables to be harmonized (see (2) in Notes).
    
    allocate_total : boolean
        True if total value of source area should be allocated.
        False if denominator is area of i. Note that the two cases
        would be identical when the area of the source polygon is
        exhausted by intersections. See (3) in Notes for more details.
        
    raster_path : the path to the associated raster image that has the types of each pixel in the spatial context.
        Only taken into consideration for harmonization raster based.
        
    codes : an integer list of codes values that should be considered as 'populated'.
        Since this draw inspiration using the National Land Cover Database (NLCD), the default is 21 (Developed, Open Space), 22 (Developed, Low Intensity), 23 (Developed, Medium Intensity) and 24 (Developed, High Intensity).
        The description of each code can be found here: https://www.mrlc.gov/sites/default/files/metadata/landcover.html
        Only taken into consideration for harmonization raster based.
        
    force_crs_match : bool. Default is True.
        Wheter the Coordinate Reference System (CRS) of the polygon will be reprojected to the CRS of the raster file. 
        It is recommended to let this argument as True.
        Only taken into consideration for harmonization raster based.

    
    Notes
    -----
    
    1) Each GeoDataFrame of raw_community is assumed to have a 'year' column. Also, all GeoDataFrames must have the same Coordinate Reference System (CRS).
    
    2) A quick explanation of extensive and intensive variables can be found here: http://ibis.geog.ubc.ca/courses/geob370/notes/intensive_extensive.htm.
    
    3) For an extensive variable, the estimate at target polygon j (default case) is:

        v_j = \sum_i v_i w_{i,j}
    
        w_{i,j} = a_{i,j} / \sum_k a_{i,k}
    
        If the area of the source polygon is not exhausted by intersections with
        target polygons and there is reason to not allocate the complete value of
        an extensive attribute, then setting allocate_total=False will use the
        following weights:
    
        v_j = \sum_i v_i w_{i,j}
    
        w_{i,j} = a_{i,j} / a_i
    
        where a_i is the total area of source polygon i.
    
        For an intensive variable, the estimate at target polygon j is:
    
        v_j = \sum_i v_i w_{i,j}
    
        w_{i,j} = a_{i,j} / \sum_k a_{k,j}
    
    """
    
    for i in raw_community:
        _check_presence_of_crs(i)
        
    if not all(i.crs == raw_community[0].crs for i in raw_community):
        raise ValueError('There is, at least, one pairwise difference in the Coordinate Reference System (CRS) of the GeoDataFrames of raw_community. All of them must be the same.')
    
    years_set = [i['year'].unique()[0] for i in raw_community]
    reference_idx_year = years_set.index(target_year_of_reference)
    
    source_years = years_set.copy()
    del source_years[reference_idx_year]
    
    source_idx_year = list(np.where(np.isin(years_set, source_years) == True)[0])
    
    reference_df = raw_community[reference_idx_year]
    
    interpolated_dfs = {}
    
    for i in source_idx_year:
        print('Starting to Harmonize the year of {}...'.format(years_set[i]))
        source_df = raw_community[i]
        
        if (weights_method == 'area'):
            
            # In area_interpolate, the resulting variable has same lenght as target_df
            interpolation = area_interpolate_binning(source_df, 
                                                     reference_df,
                                                     extensive_variables = extensive_variables,
                                                     intensive_variables = intensive_variables,
                                                     allocate_total = allocate_total)
            
        if (weights_method == 'land_type_area'):
            
            area_tables_raster_fitted = area_tables_raster(source_df, reference_df, raster_path, codes = codes, force_crs_match = force_crs_match)
            
            # In area_interpolate, the resulting variable has same lenght as target_df
            interpolation = area_interpolate(source_df, 
                                             reference_df,
                                             extensive_variables = extensive_variables,
                                             intensive_variables = intensive_variables,
                                             allocate_total = allocate_total,
                                             tables = area_tables_raster_fitted)

            
        for j in list(range(interpolation[0].shape[1])):
            print('Harmonizing extensive variable {} of the year {}.'.format(extensive_variables[j], years_set[i]))
            profile = pd.DataFrame.from_dict({'interpolated_' + extensive_variables[j] : interpolation[0][:,j]})
            reference_df = pd.concat([reference_df.reset_index(drop=True), profile], axis = 1)
            
        for k in list(range(interpolation[1].shape[1])):
            print('Harmonizing intensive variable {} of the year {}.'.format(intensive_variables[k], years_set[i]))
            profile = pd.DataFrame.from_dict({'interpolated_' + intensive_variables[k] : interpolation[1][:,k]})
            reference_df = pd.concat([reference_df.reset_index(drop=True), profile], axis = 1)
        
        # Resetting the year column to the year that it is been harmonized
        reference_df['year'] = years_set[i]
            
        interpolated_dfs.update({years_set[i] : reference_df})
        
        # Resets the reference_df to refresh the loop (this has to be present)
        del reference_df
        reference_df = raw_community[reference_idx_year]
        
    harmonized_df = gpd.GeoDataFrame()
    for value in interpolated_dfs.values():
        harmonized_df = pd.concat([harmonized_df.reset_index(drop=True), value], axis = 0)
        
    
    return harmonized_df