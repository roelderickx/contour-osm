  $ [ "$0" != "/bin/bash" ] || shopt -s expand_aliases
  $ [ -n "$PYTHON" ] || PYTHON="`which python`"
  $ alias contourosm="$PYTHON $TESTDIR/../contour-osm.py"
  $ alias osmosis=$TESTDIR/../../osmosis/bin/osmosis

#epsg4326pbf:
#  $ contourosm --datasource $TESTDIR/shapefiles/N50E006c10.shp $TESTDIR/epsg4326.osm.pbf

epsg4326pbf-poly:
  $ contourosm --datasource $TESTDIR/shapefiles/N50E006c10.shp --poly $TESTDIR/shapefiles/botrange.poly epsg4326-poly.osm.pbf
  Amount of features in source: 23691
  Amount of intersections found: 35
  $ osmosis --read-pbf file=epsg4326-poly.osm.pbf --write-xml epsg4326-poly.osm 2> /dev/null
  $ xmllint --xpath '/osm/node/@id|/osm/node/@lat|/osm/node/@lon' --format epsg4326-poly.osm | diff -uNr - $TESTDIR/epsg4326_pbf_nodes.txt
  $ xmllint --xpath '/osm/way/@id|/osm/way/nd|/osm/way/tag' --format epsg4326-poly.osm | diff -uNr - $TESTDIR/ways.txt

