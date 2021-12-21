'''
Toposcale class definition
S. Filhol, September 2021

project/
    config.ini
    -> input/
        -> dem/
        -> climate/
    -> output/

'''
import os
#import configparser
import sys

import pandas as pd
import numpy as np
from configobj import ConfigObj
import matplotlib.pyplot as plt
from TopoPyScale import fetch_era5 as fe
from TopoPyScale import topo_param as tp
from TopoPyScale import topo_sub as ts
from TopoPyScale import fetch_dem as fd
from TopoPyScale import solar_geom as sg
from TopoPyScale import topo_scale as ta
from TopoPyScale import topo_export as te

class Topoclass(object):
    '''
    A python class to bring the typical use-case of toposcale in a user friendly object
    '''

    def __init__(self, config_file):
        
        self.config = self.Config(config_file)
        self.toposub = self.Toposub()

        self.solar_ds = None
        self.horizon_da = None

        # add here a little routinr doing chek on start and end date in config.ini compare to forcing in case

        if not os.path.isfile(self.config.dem_path):
            fd.fetch_dem(self.config.project_dir, self.config.extent, self.config.dem_file)
        else:
            print('\n---> DEM file found')
            self.toposub.dem_path = self.config.dem_path

        # little routine extracting lat/lon extent from DEM
        self.config.extent = tp.get_extent_latlon(self.config.dem_path, self.config.dem_epsg)
        print('Project lat/lon extent:')
        print('\t----------------------------')
        print('\t|      North:{}          |\n\t|West:{}          East:{}|\n\t|      South:{}          |'.format(np.round(self.config.extent.get('latN'),1),
                                                          np.round(self.config.extent.get('lonW'),1),
                                                          np.round(self.config.extent.get('lonE'),1),
                                                          np.round(self.config.extent.get('latS'),1)))
        print('\t----------------------------')

        if self.config.climate_dataset.lower() == 'era5':
            self.get_era5()

    class Toposub:
        '''
        Class to initialize variables to store TopoSub variables
        '''
        def __init__(self):
            self.dem_path = None
            self.ds_param = None
            self.df_centroids = None
            self.kmeans_obj = None
            self.scaler = None

        def plot_clusters_map(self, var='cluster_labels', cmap=plt.cm.hsv, figsize=(14, 10)):
            ts.plot_center_clusters(self.dem_path, self.ds_param, self.df_centroids, var=var, cmap=cmap, figsize=figsize)

    def compute_dem_param(self):
        self.toposub.ds_param = tp.compute_dem_param(self.config.dem_path)

    def extract_pts_param(self, method='nearest', **kwargs):
        '''
        Function to use a list point as input rather than cluster centroids from DEM segmentation (topo_sub.py/self.clustering_dem()).
        :param df: pandas DataFrame
        :param method: method of sampling
        :param **kwargs: pd.read_csv() parameters
        :return:
        '''
        self.toposub.df_centroids = pd.read_csv(self.config.project_dir + 'inputs/dem/' + self.config.pt_list_file, **kwargs)
        self.toposub.df_centroids = tp.extract_pts_param(self.toposub.df_centroids, self.toposub.ds_param, method=method)

    def extract_dem_cluster_param(self):
        '''
        Function to segment a DEM in clusters and retain only the centroids of each cluster.
        :return:
        '''
        df_param = ts.ds_to_indexed_dataframe(self.toposub.ds_param)
        df_scaled, self.toposub.scaler = ts.scale_df(df_param)
        if self.config.clustering_method.lower() == 'kmean':
            self.toposub.df_centroids, self.toposub.kmeans_obj, df_param['cluster_labels'] = ts.kmeans_clustering(df_scaled, self.config.n_clusters, seed=self.config.random_seed)
        elif self.config.clustering_method.lower() == 'minibatchkmean':
            self.toposub.df_centroids, self.toposub.kmeans_obj, df_param['cluster_labels'] = ts.minibatch_kmeans_clustering(df_scaled, self.config.n_clusters, self.config.n_cores,  seed=self.config.random_seed)
        else:
            print('ERROR: {} clustering method not available'.format(self.config.clustering_method))
        self.toposub.df_centroids = ts.inverse_scale_df(self.toposub.df_centroids, self.toposub.scaler)
        self.toposub.ds_param['cluster_labels'] = (["y", "x"], np.reshape(df_param.cluster_labels.values, self.toposub.ds_param.slope.shape))

    def compute_solar_geometry(self):
        self.solar_ds = sg.get_solar_geom(self.toposub.df_centroids,
                                          self.config.start_date,
                                          self.config.end_date,
                                          self.config.time_step,
                                          self.config.dem_epsg,
                                          self.config.n_cores)

    def compute_horizon(self):
        '''
        Function to compute horizon angle and sample values for list of points
        :return:
        '''
        self.horizon_da = tp.compute_horizon(self.config.dem_path, self.config.horizon_az_inc, self.config.n_cores)
        tgt_x = tp.xr.DataArray(self.toposub.df_centroids.x.values, dims="points")
        tgt_y = tp.xr.DataArray(self.toposub.df_centroids.y.values, dims="points")
        for az in self.horizon_da.azimuth.values:
            self.toposub.df_centroids['hori_azi_'+str(az)] = self.horizon_da.sel(x=tgt_x,
                                                                            y=tgt_y,
                                                                            azimuth=az,
                                                                            method='nearest').values.flatten()

    def downscale_climate(self):
        self.downscaled_pts = ta.downscale_climate(self.config.climate_path,
                                        self.toposub.df_centroids,
                                        self.solar_ds,
                                        self.horizon_da,
                                        self.config.dem_epsg,
                                        self.config.start_date,
                                        self.config.end_date,
                                        self.config.lw_terrain_contrib_flag,
                                        self.config.time_step,
                                        self.config.n_cores)

    class Config:
        '''
        Class to contain all config.ini parameters
        '''
        def __init__(self, config_file):
            self.file_config = config_file 
            
            # parse configuration file into config class
            self._parse_config_file()
            
            # check if tree directory exists. If not create it
            if not os.path.exists('/'.join((self.project_dir, 'inputs/'))):
                os.makedirs('/'.join((self.project_dir, 'inputs/')))
            if not os.path.exists('/'.join((self.project_dir, 'inputs/climate/'))):
                os.makedirs('/'.join((self.project_dir, 'inputs/climate')))
            if not os.path.exists('/'.join((self.project_dir, 'inputs/dem/'))):
                os.makedirs('/'.join((self.project_dir, 'inputs/dem/')))
            if not os.path.exists('/'.join((self.project_dir, 'outputs/'))):
                os.makedirs('/'.join((self.project_dir, 'outputs/')))
                
        def _parse_config_file(self):
            '''
            Function to parse config file .ini into a python class
            '''
            try:
                conf = ConfigObj(self.file_config, raise_errors=False)
            except IOError:
                print('ERROR: config file does not exist. Check path.')

            self.project_dir = conf['main']['project_dir']
            self.project_description = conf['main']['project_description']
            self.project_name = conf['main']['project_name']
            self.project_author = conf['main']['project_authors']
            
            self.start_date = conf['main']['start_date']
            self.end_date = conf['main']['end_date']
            
            self.climate_dataset = conf['forcing'].get('dataset')
            if self.climate_dataset.lower() == 'era5':
                self.climate_era5_product = conf['forcing']['era5_product']
                self.climate_n_threads = conf['forcing'].as_int('n_threads_download')
            self.n_cores = conf['forcing'].as_int('n_cores')
            self.climate_path = self.project_dir + 'inputs/climate/'
                
            self.time_step = conf['forcing']['time_step']
            self.plevels = conf['forcing']['plevels']
            
            self.dem_file = conf['forcing'].get('dem_file')
            self.dem_epsg = conf['forcing'].get('dem_epsg')
            self.dem_path = self.project_dir + 'inputs/dem/' + self.dem_file
            self.horizon_az_inc = conf['forcing'].as_int('horizon_az_inc')

            self.n_clusters = conf['toposcale'].as_int('n_clusters')
            self.random_seed = conf['toposcale'].as_int('random_seed')
            self.clustering_method = conf['toposcale']['clustering_method']
            self.interp_method = conf['toposcale']['interpolation_method']
            self.pt_list_file = conf['toposcale']['pt_list']
            self.pt_sampling_method = conf['toposcale']['pt_sampling_method']
            self.lw_terrain_contrib_flag = conf['toposcale'].as_bool('lw_terrain_contribution')
            
    def get_era5(self):
        '''
        Funtion to call fetching of ERA5 data
        TODO:
        - merge monthly data into one file (cdo?)
        '''
        lonW = self.config.extent.get('lonW') - 0.25
        lonE = self.config.extent.get('lonE') + 0.25
        latN = self.config.extent.get('latN') + 0.25
        latS = self.config.extent.get('latS') - 0.25

        # retreive ERA5 surface data
        fe.retrieve_era5(
            self.config.climate_era5_product,
            self.config.start_date,
            self.config.end_date,
            self.config.climate_path,
            latN, latS, lonE, lonW,
            self.config.time_step,
            self.config.climate_n_threads,
            surf_plev='surf'
            )
        # retrieve era5 plevels
        fe.retrieve_era5(
            self.config.climate_era5_product,
            self.config.start_date,
            self.config.end_date,
            self.config.climate_path,
            latN, latS, lonE, lonW, 
            self.config.time_step,
            self.config.climate_n_threads,
            surf_plev='plev',
            plevels=self.config.plevels,
            )
            

    def to_cryogrid(self, fname_format='Cryogrid_pt_*.nc'):
        '''
        wrapper function to export toposcale output to cryosgrid format from TopoClass
        :param fname_format: str, filename format. point_id is inserted where * is
        '''
        path = self.config.project_dir+'outputs/'
        if 'cluster:labels' in self.toposub.ds_param.keys():
            label_map = True
            da_label = self.toposub.ds_param.cluster_labels
        else:
            label_map = False
            da_label = None
        te.to_cryogrid(self.downscaled_pts,
                       self.toposub.df_centroids,
                       fname_format=fname_format,
                       path=path,
                       label_map=label_map,
                       da_label=da_label,
                       climate_dataset_name=self.config.climate_dataset,
                       project_author=self.config.project_author)
        
    def to_fsm(self):
        '''
        function to export toposcale output to FSM format
        '''
        
    def to_crocus(self, fname_format='./outputs/CROCUS_pt_*.nc', scale_precip=1):
        '''
        function to export toposcale output to crocus format .nc. This functions saves one file per point_id

        :param fout_format: str, filename format. point_id is inserted where * is
        :param scale_precip: float, scaling factor to apply on precipitation. Default is 1
        '''
        te.to_crocus(self.downscaled_pts,
                     self.toposub.df_centroids,
                     fname_format=fname_format,
                     scale_precip=scale_precip,
                     climate_dataset_name=self.config.climate_dataset,
                     project_author=self.config.project_author)

    
    def to_snowmodel(self, fname_format='./outputs/Snowmodel_stn_*.csv'):
        '''
        function to export toposcale output to snowmodel format .ascii, for single station standard

        :param fout_format: str, filename format. point_id is inserted where * is
        '''
        te.to_micromet_single_station(self.downscaled_pts, self.toposub.df_centroids, fname_format=fname_format, na_values=-9999, headers=False)
    
    def to_netcdf(self, file_out='./outputs/output.nc'):
        '''
        function to export toposcale output to one single generic netcdf format, compressed
        '''
        encod_dict = {}
        for var in list(self.downscaled_pts.keys()):
            scale_factor, add_offset = te.compute_scaling_and_offset(self.downscaled_pts[var], n=10)
            encod_dict.update({var:{"zlib": True,
                                   "complevel": 9,
                                   'dtype':'int16',
                                   'scale_factor':scale_factor,
                                   'add_offset':add_offset}})
        self.downscaled_pts.to_netcdf(file_out, encoding=encod_dict)
        print('---> File {} saved'.format(file_out))