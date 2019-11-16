#!/usr/bin/python

# contour-osm -- write contour lines from a file or database source to an osm file
# Copyright (C) 2019  Roel Derickx <roel.derickx AT gmail>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, os, argparse, logging
from osgeo import ogr
from osgeo import osr

class Polyfile:
    def __init__(self, minlon, maxlon, minlat, maxlat):
        self.filename = None
        self.name = 'bbox'
        self.polygons = ogr.Geometry(ogr.wkbMultiPolygon)
        
        self.__create_from_boundaries(minlon, maxlon, minlat, maxlat)
    
    
    def __init__(self, filename):
        self.filename = filename
        self.name = None
        self.polygons = ogr.Geometry(ogr.wkbMultiPolygon)
        
        self.__read_poly()
    
    
    def __create_from_boundaries(self, minlon, maxlon, minlat, maxlat):
        polygon = ogr.Geometry(ogr.wkbPolygon)
        poly_section = ogr.Geometry(ogr.wkbLinearRing)
        poly_section.AddPoint(minlon, minlat)
        poly_section.AddPoint(maxlon, minlat)
        poly_section.AddPoint(maxlon, maxlat)
        poly_section.AddPoint(minlon, maxlat)
        poly_section.AddPoint(minlon, minlat)
        polygon.AddGeometry(poly_section)
        self.polygons.AddGeometry(polygon)

    
    def __read_poly(self):
        with open(self.filename, 'r') as f:
            self.name = f.readline().strip()
            polygon = None
            while True:
                section_name = f.readline()
                if not section_name:
                    # end of file
                    break
                section_name = section_name.strip()
                if section_name == 'END':
                    # end of file
                    break
                elif polygon and section_name and section_name[0] == '!':
                    polygon.AddGeometry(self.__read_poly_section(f))
                else:
                    polygon = ogr.Geometry(ogr.wkbPolygon)
                    polygon.AddGeometry(self.__read_poly_section(f))
                    self.polygons.AddGeometry(polygon)
        f.close()
    
    
    def __read_poly_section(self, f):
        poly_section = ogr.Geometry(ogr.wkbLinearRing)
        while True:
            line = f.readline()
            if not line or line[0:3] == 'END':
                # end of file or end of section
                break
            elif not line.strip():
                # empty line
                continue
            else:
                ords = line.split()
                poly_section.AddPoint(float(ords[0]), float(ords[1]))
        
        return poly_section


    def to_wkt_string(self, srs = 4326):
        src_srs = osr.SpatialReference()
        src_srs.ImportFromEPSG(4326)

        dest_srs = osr.SpatialReference()
        dest_srs.ImportFromEPSG(srs)

        transform = osr.CoordinateTransformation(src_srs, dest_srs)
        polygons = ogr.CreateGeometryFromWkt(self.polygons.ExportToWkt())
        polygons.Transform(transform)

        return polygons.ExportToWkt()


    def to_wkb_string(self, srs = 4326):
        src_srs = osr.SpatialReference()
        src_srs.ImportFromEPSG(4326)

        dest_srs = osr.SpatialReference()
        dest_srs.ImportFromEPSG(srs)

        transform = osr.CoordinateTransformation(src_srs, dest_srs)
        polygons = ogr.CreateGeometryFromWkt(self.polygons.ExportToWkt())
        polygons.Transform(transform)

        return ''.join(format(x, '02x') for x in polygons.ExportToWkb())



class DatabaseInput:
    def __init__(self, connectstring, tablename, elevation_column, contour_column, boundaries = None):
        self.datasource = ogr.Open(connectstring, 0)  # 0 means read-only
        if not self.datasource:
            logging.error("Unable to open OGR datasource '%s'" % source)
    
        self.tablename = tablename
        self.elevation_column = elevation_column
        self.contour_column = contour_column
        
        self.boundaries = boundaries
    
    
    def __get_query(self):
        sql = ''
        
        if self.boundaries:
            sql = '''select %s, ST_Intersection(%s, p.polyline)
from (select ST_GeomFromText(\'%s\', 4326)  polyline) p, %s
where ST_Intersects(%s, p.polyline)''' % \
                (self.elevation_column, self.contour_column, \
                self.boundaries.to_wkt_string(), self.tablename, \
                self.contour_column)
        else:
            sql = 'select %s, %s from %s' % \
                (self.elevation_column, self.contour_column, self.tablename)

        return sql


    def fetch_data(self):
        layer = self.datasource.ExecuteSQL(self.__get_query())
        layer.ResetReading()
        
        return [ layer ]
    
    

# this class does not (yet) support raster files
class FileInput:
    def __init__(self, filename, srs = 4326, boundaries = None):
        self.datasource = ogr.Open(filename, 0)  # 0 means read-only
        self.srs = 4326
        self.boundaries = boundaries


    def fetch_data(self):
        layers = []
        for i in range(self.datasource.GetLayerCount()):
            layer = self.datasource.GetLayer(i)
            
            if self.boundaries:
                # TODO: see https://gis.stackexchange.com/questions/82935/ogr-layer-intersection
                layer.SetSpatialFilter(ogr.CreateGeometryFromWkt(self.boundaries.to_wkt_string(self.srs)))

            layer.ResetReading()
            layers.append(layer)
        
        return layers



# class outline, not yet functional
class OsmOutput:
    def __init__(self, filename):
        self.filename = filename
    
    
    def add_geometry(self, height, geometry):
        print(height)
        print(geometry)



# TODO class O5mOutput:
# TODO class PbfOutput:



class Transformation:
    def __init__(self, data_input, data_output):
        self.data_input = data_input
        self.data_output = data_output
        
        self.reproject = None


    def add_reprojection(self, src_srs, dst_srs):
        spatial_ref = None
        if src_srs:
            spatial_ref = osr.SpatialReference()
            spatial_ref.ImportFromEPSG(src_srs)
        else:
            spatial_ref = layer.GetSpatialRef()

        if spatial_ref:
            logging.info("Detected projection metadata:\n" + str(spatial_ref))
            
            dest_spatial_ref = osr.SpatialReference()
            try:
                dest_spatial_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            except AttributeError:
                pass
            # Destionation projection will *always* be EPSG:4326, WGS84 lat-lon
            dest_spatial_ref.ImportFromEPSG(dst_srs)
            coordTrans = osr.CoordinateTransformation(spatial_ref, dest_spatial_ref)
            self.reproject = lambda geometry: geometry.Transform(coordTrans)
        else:
            logging.info("No projection metadata, falling back to EPSG:4326")
            
            # No source proj specified yet? Then default to do no reprojection.
            # Some python magic: skip reprojection altogether by using a dummy
            # lamdba funcion. Otherwise, the lambda will be a call to the OGR
            # reprojection stuff.
            self.reproject = lambda geometry: None


    # TODO Ramer-Douglas-Peucker (RDP) simplification
    #      see phyghtmap
    def add_simplify_rdp(self, epsilon, max_distance):
        pass
    
    
    def __process_feature(self, height, ogrfeature):
        if not ogrfeature:
            return
        
        ogrgeometry = ogrfeature.GetGeometryRef()
        
        if not ogrgeometry:
            return

        if self.reproject:
            self.reproject(ogrgeometry)
        #elif self.simplify:
        #    self.simplify(ogrgeometry)

        self.data_output.add_geometry(height, ogrgeometry)
    
    
    def process(self):
        layers = self.data_input.fetch_data()
        
        for layer in layers:
            # get feature fields from layer
            feature_definition = layer.GetLayerDefn()
            feature_fields = []
            for j in range(feature_definition.GetFieldCount()):
                feature_fields.append(feature_definition.GetFieldDefn(j).GetNameRef())
            
            # there should be at least 1 feature field and this is considered to be the height
            if len(feature_fields) == 0:
                logging.error("No fields present in feature")
            elif len(feature_fields) > 1:
                logging.warning("Feature contains more than 1 field, considering '%s' as elevation" % \
                                feature_fields[-1])

            # loop through layer features
            for j in range(layer.GetFeatureCount()):
                ogrfeature = layer.GetNextFeature()
                self.__process_feature(ogrfeature[feature_fields[-1]], ogrfeature)



# MAIN

parser = argparse.ArgumentParser(description = 'Write contour lines from a file or databse source ' + \
                                               'to an osm file')
parser.add_argument('--db', dest = 'connectstring', help = 'Database connectstring')
parser.add_argument('--db-table', dest = 'dbtable', default = 'elevation', \
                    help = 'Database table containing the contour data')
parser.add_argument('--db-height-column', dest = 'dbheightcolumn', default = 'height', \
                    help = 'Database column containg the elevation')
parser.add_argument('--db-contour-column', dest = 'dbcontourcolumn', default = 'geom', \
                    help = 'Database column containing the contour')
parser.add_argument('--sourcefile', dest = 'sourcefile', \
                    help = 'Filename containing the contour data, only taken into account ' + \
                           'when --db is not given')
parser.add_argument('--src-srs', dest = 'srcsrs', type = int, default = 4326, \
                    help = 'EPSG code of input data. Do not include the EPSG: prefix.')
parser.add_argument('--dst-srs', dest = 'dstsrs', type = int, default = 4326, \
                    help = 'EPSG code of output file. Do not include the EPSG: prefix.')
parser.add_argument('--poly', dest = 'poly', \
                    help = 'Osmosis poly-file containing the boundaries to process')
args = parser.parse_args()

poly = None
if args.poly:
    poly = Polyfile(args.poly)

data_input = None
if args.connectstring:
    data_input = DatabaseInput(args.connectstring, \
                               args.dbtable, args.dbheightcolumn, args.dbcontourcolumn, poly)
else:
    data_input = FileInput(args.sourcefile, args.srcsrs, poly)

data_output = OsmOutput('test.osm')

transform = Transformation(data_input, data_output)
transform.add_reprojection(args.srcsrs, args.dstsrs)
#transform.add_simplify_rdp(epsilon, max_distance)
transform.process()

