#!/bin/bash

wget https://dds.cr.usgs.gov/srtm/version2_1/SRTM3/Eurasia/N50E006.hgt.zip
unzip N50E006.hgt.zip

gdal_contour -i 10 -snodata 32767 -a height N50E006.hgt N50E006c10.shp
shapeindex N50E006c10.shp

ogr2ogr -s_srs EPSG:4326 -t_srs EPSG:3812 N50E006c10_3812.shp N50E006c10.shp
shapeindex N50E006c10_3812.shp

