# contour-osm

contour-osm is an application to export contour lines to an osm, o5m or pbf file. The datasource can be any vector file format supported by gdal or a database.
The resulting files are not intended to be uploaded to openstreetmap, actually this is not even allowed.

## NOTICE

This application is still under development. There is a proof-of-concept which is usable but there are some limitations.

## Usage

...

## Proof of concept

You can use ogr2osm to achieve the desired result. First you should build a query to fetch the data, or have a shape file ready containing the area you want to export.

An example SQL statement may look like this:
```sql
select height, ST_Intersection(geom, p.polyline)
from (select ST_GeomFromText('MULTIPOLYGON (((6.051 50.5191 0,6.1232 50.5191 0,6.1232 50.4792 0,6.051 50.4792 0,6.051 50.5191 0)))', 4326)  polyline) p, elevation
where ST_Intersects(geom, p.polyline)
```

Remark: contour-osm contains a Polyfile class to convert osmosis poly-files to WKT, which is usable in your query.

Then, run ogr2osm:
```bash
ogr2osm -t contour-translation.py -o test.osm --sql "select height, ST_Intersection(geom, p.polyline) from (select ST_GeomFromText('MULTIPOLYGON (((6.051 50.5191 0,6.1232 50.5191 0,6.1232 50.4792 0,6.051 50.4792 0,6.051 50.5191 0)))', 4326)  polyline) p, elevation where ST_Intersects(geom, p.polyline)" "PG:dbname=gis user=gis host=localhost"
```

The resulting OSM file is compatible with the output of [Phyghtmap](http://katze.tfiu.de/projects/phyghtmap/) and can be converted to a Garmin map image using [mkgmap](http://www.mkgmap.org.uk/download/mkgmap.html). For more information on this step see [the OSM wiki](https://wiki.openstreetmap.org/wiki/Mkgmap).

