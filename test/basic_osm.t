  $ [ "$0" != "/bin/bash" ] || shopt -s expand_aliases
  $ [ -n "$PYTHON" ] || PYTHON="`which python`"
  $ alias contourosm="$PYTHON $TESTDIR/../contour-osm.py"

usage:
  $ contourosm -h
  usage: contour-osm.py [-h] --datasource DATASOURCE [--tablename TABLENAME]
                        [--height-column HEIGHTCOLUMN]
                        [--contour-column CONTOURCOLUMN] [--src-srs SRCSRS]
                        [--poly POLY] [-M CATEGORY] [-m CATEGORY] [--osm]
                        OUTPUT
  
  Write contour lines from a file or database source to an osm file
  
  positional arguments:
    OUTPUT                Output osm or pbf file
  
  optional arguments:
    -h, --help            show this help message and exit
    --datasource DATASOURCE
                          Database connectstring or filename
    --tablename TABLENAME
                          Database table containing the contour data, only
                          required for database access.
    --height-column HEIGHTCOLUMN
                          Database column containg the elevation. Contour-osm
                          will try to find this column in the given table when
                          this parameter is omitted.
    --contour-column CONTOURCOLUMN
                          Database column containg the contour. Contour-osm will
                          try to find this column in the given table when this
                          parameter is omitted.
    --src-srs SRCSRS      EPSG code of input data. Do not include the EPSG:
                          prefix.
    --poly POLY           Osmosis poly-file containing the boundaries to process
    -M CATEGORY, --major CATEGORY
                          Major elevation category (default=500)
    -m CATEGORY, --medium CATEGORY
                          Medium elevation category (default=100)
    --osm                 Write the output as an OSM file in stead of a PBF file

#epsg4326osm:
#  $ contourosm --osm --datasource $TESTDIR/shapefiles/N50E006c10.shp $TESTDIR/epsg4326.osm

epsg4326osm-poly:
  $ contourosm --osm --datasource $TESTDIR/shapefiles/N50E006c10.shp --poly $TESTDIR/shapefiles/botrange.poly epsg4326-poly.osm
  Amount of features in source: 23691
  Amount of intersections found: 35
  $ xmllint --xpath '/osm/node/@id|/osm/node/@lat|/osm/node/@lon' --format epsg4326-poly.osm | diff -uNr - $TESTDIR/epsg4326_nodes.txt
  $ xmllint --xpath '/osm/way' --format epsg4326-poly.osm | diff -uNr - $TESTDIR/ways.txt

epsg3812osm-poly:
  $ contourosm --osm --datasource $TESTDIR/shapefiles/N50E006c10_3812.shp --src-srs 3812 --poly $TESTDIR/shapefiles/botrange.poly epsg3812-poly.osm
  Amount of features in source: 23691
  Amount of intersections found: 35
  $ xmllint --xpath '/osm/node/@id|/osm/node/@lat|/osm/node/@lon' --format epsg3812-poly.osm | diff -uNr - $TESTDIR/epsg3812_nodes.txt
  $ xmllint --xpath '/osm/way' --format epsg3812-poly.osm | diff -uNr - $TESTDIR/ways.txt

