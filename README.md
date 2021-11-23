# TopoPyScale
Pure Python version of Toposcale packaged as a Pypi library. Toposcale is an original idea of Joel Fiddes to perform topography-based downscaling of climate data to the hillslope scale.

**References:**
- Fiddes, J. and Gruber, S.: TopoSCALE v.1.0: downscaling gridded climate data in complex terrain, Geosci. Model Dev., 7, 387–405, https://doi.org/10.5194/gmd-7-387-2014, 2014.
- Fiddes, J. and Gruber, S.: TopoSUB: a tool for efficient large area numerical modelling in complex topography at sub-grid scales, Geosci. Model Dev., 5, 1245–1257, https://doi.org/10.5194/gmd-5-1245-2012, 2012. 

## Contribution Workflow
**Please follow these simple rules:**
1. a bug -> fix it! 
2. an idea or a bug you cannot fix? -> create a new [issue](https://github.com/ArcticSnow/TopoPyScale/issues) after checking an issue doesn't already exist. If so, add material to that existing issue.
3. wanna develop a new feature/idea? -> create a new branch. Do the development. Merge with main branch when accomplished.
4. Create release version when significant improvements and bug fix has been done. Coordinate with others

And check out our Slack: tscaleworkspace.slack.com

Contributors to the current version (2021) are:
- Simon Filhol
- Joel Fiddes
- Kristoffer Aalstad

## TODO

- class `topoclass`:
    - [x] create project folder structure if not existing
    - [x] read config file
    - [x] get ERA5 data
    - [ ] create possibility to provide a list of points by lat,long to run toposcale completely
    - [ ] write save output in the various format version
    - [ ] fetch other dataset routines
    - [ ] implement routine to fecth DEM automatically from ArcticDEM/ASTER
    - [ ] add plotting routines.
- `topo_sub.py`:
  - [ ]look into alternative clustering method DBscan
  - [x] implement minibatch kmean for large DEM
  - [x] simplify `fetch_era5.py` routines. Code seems over complex
  - [ ] write download routine for CORDEX climate projection
- `topo_scale.py`:
    - [x] develop to do one point. then loop over a list of point
    - [ ] add metadata to the newly created dataset (variable name, units, etc)
    - [ ] try to rewrite function to skip for loop using the power of zarray
    - [ ] check against previous implementation of TopoScale
    
    
- `fetch_era5.py`:
  - [x] swap `parallel` for [`from multiprocessing import Pool`](https://docs.python.org/3/library/multiprocessing.html)  when launch downloads simulstaneously
  - [ ] figure out in which case to use other function tpmm and other? how to integrate them?   
    
- `topo_param.py`:
    - [x] add routine to sample dem or var at any given point. Do it for Horizons
    - [x] change aspect to have 0 as south. (same convention as in horizon)
- **Documentation**:
  - [ ] Complete `README.md` file
  - [ ] create small examples from a small dataset avail in the library
  - [ ] If readme is not enough, then make a ReadTheDoc 
  - [ ] make sure all functions and class have explicit docstring

## Design

1. Inputs
    - Climate data from reanalysis (ERA5, etc)
    - Climate data from future projections (CORDEX)
    - DEM from local source, or fetch from public repository: SRTM, ArcticDEM
2. Run TopoScale
    - compute derived values (from DEM)
    - toposcale (k-mean clustering)
    - interpolation (bilinear, inverse square dist.) (interpolation optional only if output as gridded data)
3. Output
    - Cryogrid format
    - FSM format
    - CROCUS format
    - Snowmodel format
    - basic netcfd
    - For each method, have the choice to output either the abstract cluster points, or the gridded product after interpolation
4. Validation toolset
    - validation to local observation timeseries
    - plotting
5. Gap filling algorithm
    - random forest temporal gap filling

Validation (4) and Gap filling (4) are future implementation.

## Installation

```bash
conda create -n downscaling
conda activate downscaling
conda install mamba -n base -c conda-forge
mamba install ipython numpy pandas xarray matplotlib netcdf4 ipykernel scikit-learn rasterio gdal
pip install cdsapi
pip install h5netcdf
pip install topocalc
pip install pvlib
pip install elevation
pip install configobj

cd github  # navigate to where you want to clone TopoPyScale
git clone git@github.com:ArcticSnow/TopoPyScale.git
pip install -e TopoPyScale    #install a development version

#----------------------------------------------------------
#            OPTIONAL: if using jupyter lab

# if you want to add this Python kernel to your jupyter lab
python -m ipykernel install --user --name downscaling
```

Then you need to setup your `cdsapi` with the Copernicus API key system. Follow [this tutorial](https://cds.climate.copernicus.eu/api-how-to#install-the-cds-api-key) after creating an account with [Copernicus](https://cds.climate.copernicus.eu/). On Linux, create a file `nano ~/.cdsapirc` with inside:

```
url: https://cds.climate.copernicus.eu/api/v2
key: {uid}:{api-key}
```

## Basic usage

1. Setup your Python environment
2. Create your project directory
3. Configure the file `config.ini` to fit your problem
4. Run TopoPyScale

```python
import pandas as pd
from TopoPyScale import topoclass as tc
from matplotlib import pyplot as plt

# ========= STEP 1 ==========
# Load Configuration
config_file = './config.ini'
mp = tc.Topoclass(config_file)
# Compute parameters of the DEM (slope, aspect, sky view factor)
mp.compute_dem_param()

# ========== STEP 2 ===========
# Extract DEM parameters for points of interest (centroids or physical points)

# ----- Option 1:
# Compute clustering of the input DEM and extract cluster centroids
mp.extract_dem_cluster_param()
# plot clusters
mp.toposub.plot_clusters_map()
# plot sky view factor
mp.toposub.plot_clusters_map(var='svf', cmap=plt.cm.viridis)

# ------ Option 2:
# provide a list of point coordinates for which extract the DEM parameters for
df_pts = pd.read_csv('pts_list.csv') # a file with points pt_name, x, y columns 
mp.extract_pts_param(df_pts)

# ========= STEP 3 ==========
# compute solar geometry and horizon angles
mp.compute_solar_geometry()
mp.compute_horizon()

# ========= STEP 4 ==========
# Perform the downscaling
mp.downscale_climate()

# ========= STEP 5 ==========
# Export output to desired format
mp.to_netcdf()
```

## Principle of TopoPyScale
