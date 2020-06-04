# contour-osm

contour-osm is an application to export contour lines to an osm or pbf file. The datasource can be any vector file format supported by gdal or a database.
**NOTE:** It is not intended to upload such contours into OSM database, but to improve OSM output. **Do not try to upload the generated data to OSM server!**

## Phyghtmap

Since the idea for this application is borrowed from [Phyghtmap](http://katze.tfiu.de/projects/phyghtmap/) it's worth being credited here. Phyghtmap is a complete package which aims to do 3 tasks:
1. Download SRTM files from either NASA or viewfinder
2. Generate contour lines
3. Convert said contour lines to osm, o5m or pbf

There are a number of advantages to this all-in-one approach, especially for inexperienced users. But according to the unix philosophy one would rather write three separate programs to achieve every task independently. As it turns out those applications exist already:
1. NASA's dba which allows downloading a specific area as well, or any browser if you really want to download manually
2. the gdal suite, especially gdal_contour. this library is used internally by phyghtmap, however this information needs to be confirmed.
3. ogr2osm

Another limitation of Phyghtmap is the lack of support for datasources other than SRTM or viewfinder. As described below in [Obtaining elevation data](#obtaining_elevation_data) there are more accurate datasources which are not necessarily distributed as hgt files.

Also, in some circumstances you may already have converted the downloaded files to contour lines and possibly you even inserted them in a database (for example when you use [hikingmap](https://github.com/roelderickx/hikingmap) or [opentopomap](https://github.com/der-stefan/OpenTopoMap)).

## Obtaining elevation data

What you are looking for is often called DEM (digital elevation model) or DTM (digital terrain model). It is important to find a model with an acceptable resolution, generally a precision of 3 arc-seconds is enough, meaning that there is one value for the altitude in each area of 3 arc-seconds squared. This value may not be accurate when it is measured by a satelite, the height of trees, snow or other objects may be measured in stead of the height of the terrain itself.

* NASA's [Shuttle Radar Topography Mission](http://www2.jpl.nasa.gov/srtm/), version 2.1. For land areas between 60 degrees south and 60 degrees north they offer a resolution of [3 arc-seconds](http://dds.cr.usgs.gov/srtm/version2_1/SRTM3/), but for the United States a [1 arc-second version](http://dds.cr.usgs.gov/srtm/version2_1/SRTM1/) is available.
* NASA's Shuttle Radar Topography Mission, version 3. This source covers the same area as version 2.1, but in a 1 arc-second resolution. You need to register first before having access to the [EarthExplorer](https://earthexplorer.usgs.gov/) and it is suggested to use the Bulk Download Application to download vast areas. For more information please consult [the help index](https://lta.cr.usgs.gov/EEHelp/ee_help).
* However, version 3 of NASA's SRTM seems to contain large voids, a [void-filled version](https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/) is around as well. You need to register first and the user account is not the same as for the EarthExplorer.
* [Viewfinder Panoramas](http://www.viewfinderpanoramas.org/dem3.html). This source offers global coverage in a 3-arc second resolution, it is the only option beyond 60 degrees north. There is a limited selection of areas in a 1 arc-second resolution as well.
* Resolution does not always equal accuracy, data may have been interpolated from lower resolutions or inserted from other sources. For a limited selection of European countries there is a 1-arc second resolution available with a [higher accuracy](https://data.opendataportal.at/dataset/dtm-europe). The data is obtained using laserscan (LiDAR) in stead of satelites.
* Commercial elevation models, which may offer a higher resolution or more accurate data. Keep in mind that the data may be offered in a different projection, use the GDAL tools to reproject the data. Also note that each country has a different definition of sea level, your altitude lines may shift at the borders when importing several elevation models in the same database.

Make sure you obtain either HGT or GeoTIFF files or to convert them to either format using GDAL.

## Proof of concept

You can use ogr2osm to achieve the desired result. First you should build a query to fetch the data, or have a shape file ready containing the area you want to export.

An example SQL statement may look like this:
```sql
select height, ST_Intersection(geom, p.polyline)
from (select ST_GeomFromText('MULTIPOLYGON (((6.051 50.5191 0,6.1232 50.5191 0,6.1232 50.4792 0,6.051 50.4792 0,6.051 50.5191 0)))', 4326)  polyline) p, elevation
where ST_Intersects(geom, p.polyline)
```

Remark: contour-osm contains a Polyfile class to convert osmosis poly-files to WKT, which is usable in your query.

Create a translation for ogr2osm and save as `contour-translation.py`:
```python
'''
A translation function for contour data
'''

def filterTags(attrs):
    if not attrs:
        return
    
    tags={}
    
    if 'height' in attrs:
        tags['ele'] = attrs['height']
        tags['contour'] = 'elevation'
        
        height = int(attrs['height'])
        if height % 500 == 0:
            tags['contour_ext'] = 'elevation_major'
        elif height % 100 == 0:
            tags['contour_ext'] = 'elevation_medium'
        else:
            tags['contour_ext'] = 'elevation_minor'
    
    return tags
```

Then, run ogr2osm:
```bash
ogr2osm -t contour-translation.py -o test.osm --sql "select height, ST_Intersection(geom, p.polyline) from (select ST_GeomFromText('MULTIPOLYGON (((6.051 50.5191 0,6.1232 50.5191 0,6.1232 50.4792 0,6.051 50.4792 0,6.051 50.5191 0)))', 4326)  polyline) p, elevation where ST_Intersects(geom, p.polyline)" "PG:dbname=gis user=gis host=localhost"
```

The resulting OSM file is compatible with the output of [Phyghtmap](http://katze.tfiu.de/projects/phyghtmap/) and can be converted to a Garmin map image using [mkgmap](http://www.mkgmap.org.uk/download/mkgmap.html). For more information on this step see [the OSM wiki](https://wiki.openstreetmap.org/wiki/Mkgmap).

## Requirements

Because ogr2osm is not suitable to be imported in other python projects, it is rewritten to become [ogr2pbf](https://github.com/roelderickx/ogr2pbf). This is the only requirement for contour-osm, but ogr2pbf has itself a few other requirements.

## Usage

```bash
usage: contour-osm.py [-h] [--datasource DATASOURCE] [--tablename TABLENAME]
                      [--height-column HEIGHTCOLUMN]
                      [--contour-column CONTOURCOLUMN] [--src-srs SRCSRS]
                      [--poly POLY]

Write contour lines from a file or database source to an osm file

optional arguments:
  -h, --help            show this help message and exit
  --datasource DATASOURCE
                        Database connectstring or filename
  --tablename TABLENAME
                        Database table containing the contour data, only
                        required for database access.
  --height-column HEIGHTCOLUMN
                        Database column containg the elevation, only required
                        for database access.
  --contour-column CONTOURCOLUMN
                        Database column containing the contour, only required
                        for database access.
  --src-srs SRCSRS      EPSG code of input data. Do not include the EPSG:
                        prefix.
  --poly POLY           Osmosis poly-file containing the boundaries to process
```

