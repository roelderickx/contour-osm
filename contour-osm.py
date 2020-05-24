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
import matplotlib.pyplot as pyplot
from osgeo import gdalconst
from osgeo import ogr
from osgeo import osr

class Polyfile:
    def __init__(self):
        self.filename = None
        self.name = None
        self.polygons = ogr.Geometry(ogr.wkbMultiPolygon)
    
    
    def set_boundaries(self, minlon, maxlon, minlat, maxlat):
        self.name = 'bbox'
        polygon = ogr.Geometry(ogr.wkbPolygon)
        poly_section = ogr.Geometry(ogr.wkbLinearRing)
        poly_section.AddPoint(minlon, minlat)
        poly_section.AddPoint(maxlon, minlat)
        poly_section.AddPoint(maxlon, maxlat)
        poly_section.AddPoint(minlon, maxlat)
        poly_section.AddPoint(minlon, minlat)
        polygon.AddGeometry(poly_section)
        self.polygons.AddGeometry(polygon)
    
    
    def read_file(self, filename):
        self.filename = filename
        self.polygons = ogr.Geometry(ogr.wkbMultiPolygon)
        
        self.__read_poly()
    
    
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
        if srs != 4326:
            src_srs = osr.SpatialReference()
            src_srs.ImportFromEPSG(4326)

            dest_srs = osr.SpatialReference()
            dest_srs.ImportFromEPSG(srs)

            transform = osr.CoordinateTransformation(src_srs, dest_srs)
            polygons = ogr.CreateGeometryFromWkt(self.polygons.ExportToWkt())
            polygons.Transform(transform)

            return polygons.ExportToWkt()
        else:
            return self.polygons.ExportToWkt()


    def to_wkb_string(self, srs = 4326):
        if srs != 4326:
            src_srs = osr.SpatialReference()
            src_srs.ImportFromEPSG(4326)

            dest_srs = osr.SpatialReference()
            dest_srs.ImportFromEPSG(srs)

            transform = osr.CoordinateTransformation(src_srs, dest_srs)
            polygons = ogr.CreateGeometryFromWkt(self.polygons.ExportToWkt())
            polygons.Transform(transform)

            return ''.join(format(x, '02x') for x in polygons.ExportToWkb())
        else:
            return ''.join(format(x, '02x') for x in self.polygons.ExportToWkb())



class DataSource:
    def __init__(self, datasource, layername, preferred_feat, preferred_geom, srs, boundaries):
        self.datasource = ogr.Open(datasource, gdalconst.GA_ReadOnly)
        self.driver = self.datasource.GetDriver()
        self.intersect_ds = None # intersection datasource, should not go out of scope
        self.layername = layername
        self.featname = None
        self.geomname = None
        self.srs = srs
        self.boundaries = boundaries

        self.__get_layer_features(preferred_feat, preferred_geom)
        

    def __get_layer_features(self, preferred_feat, preferred_geom):
        layer = None
        if not self.layername:
            if self.datasource.GetLayerCount() > 0:
                layer = self.datasource.GetLayer(0)
                self.layername = layer.GetName()
            else:
                logging.error("No layer found and none was given.")
        else:
            layer = self.datasource.GetLayer(self.layername)
        logging.info("Using layer %s" % self.layername)

        layerdef = layer.GetLayerDefn()
        
        features_without_id = \
            [ layerdef.GetFieldDefn(i).GetName() \
                    for i in range(layerdef.GetFieldCount()) \
                    if layerdef.GetFieldDefn(i).GetName().lower() != 'id' ]

        if preferred_feat and preferred_feat in features_without_id:
            self.featname = preferred_feat
        elif len(features_without_id) == 0:
            logging.error("No feature found and none was given.")
        else:
            self.featname = features_without_id[0]
            if len(features_without_id) > 1:
                logging.warning("More than one feature found, using %s" % self.featname)
        
        geoms = [ layerdef.GetGeomFieldDefn(i).GetName() \
                        for i in range(layerdef.GetGeomFieldCount()) ]
        if preferred_geom and preferred_geom in geoms:
            self.geomname = preferred_geom
        elif len(geoms) == 0:
            logging.error("No geometry found and none was given.")
        else:
            self.geomname = geoms[0]
            if len(geoms) > 1:
                logging.warning("More than one geometry found, using %s" % self.geomname)
    
    
    def __get_query(self):
        sql = ''
        
        if self.boundaries:
            sql = '''select %s, ST_Intersection(%s, p.polyline)
from (select ST_GeomFromText(\'%s\', %d)  polyline) p, %s
where ST_Intersects(%s, p.polyline)''' % \
                (self.featname, self.geomname, \
                self.boundaries.to_wkt_string(), self.srs, \
                self.layername, self.geomname)
        else:
            sql = 'select %s, %s from %s' % \
                (self.featname, self.geomname, self.layername)

        logging.info('Generated SQL statement: %s' % sql)
        
        return sql


    def __calc_layer_intersection(self, layer, geometry):
        spatial_ref = osr.SpatialReference()
        spatial_ref.ImportFromEPSG(self.srs)
        
        dst_driver = ogr.GetDriverByName('MEMORY')
        self.intersect_ds = dst_driver.CreateDataSource('memdata')
        dst_layer = self.intersect_ds.CreateLayer(layer.GetName(), \
                                                  srs = spatial_ref, \
                                                  geom_type = ogr.wkbMultiLineString)
        dst_layer_def = dst_layer.GetLayerDefn()
        
        # add input layer field definitions to the output layer
        src_layer_def = layer.GetLayerDefn()
        for i in range(src_layer_def.GetFieldCount()):
            src_field_def = src_layer_def.GetFieldDefn(i)
            dst_layer.CreateField(src_field_def)
        
        # add intersection of input layer features with input geometry to output layer
        amount_intersections = 0
        for j in range(layer.GetFeatureCount()):
            src_feature = layer.GetNextFeature()
            src_geometry = src_feature.GetGeometryRef()
            
            if geometry.Intersects(src_geometry):
                amount_intersections += 1
                intersection = geometry.Intersection(src_geometry)
                
                dst_feature = ogr.Feature(dst_layer_def)
                for k in range(dst_layer_def.GetFieldCount()):
                    dst_field = dst_layer_def.GetFieldDefn(k)
                    dst_feature.SetField(dst_field.GetNameRef(), src_feature.GetField(k))
                dst_feature.SetGeometry(intersection)

                dst_layer.CreateFeature(dst_feature)
        
        logging.info('Amount of features in source: %d' % layer.GetFeatureCount())
        logging.info('Amount of intersections found: %d' % amount_intersections)
        
        return dst_layer
    
    
    def fetch_data(self):
        if self.boundaries:
            bound_spatial_ref = osr.SpatialReference()
            bound_spatial_ref.ImportFromEPSG(4326)
            spatial_ref = osr.SpatialReference()
            spatial_ref.ImportFromEPSG(self.srs)
            spatial_ref.AutoIdentifyEPSG()
            bound_coord_trans = osr.CoordinateTransformation(bound_spatial_ref, spatial_ref)
            if spatial_ref.EPSGTreatsAsLatLong() == 0:
                self.boundaries.polygons.SwapXY()
            self.boundaries.polygons.Transform(bound_coord_trans)
        
        layer = None
        if self.driver.GetName() == 'PostgreSQL':
            layer = self.datasource.ExecuteSQL(self.__get_query())
        else:
            src_layer = self.datasource.GetLayer(self.layername)
            
            if self.boundaries:
                layer = self.__calc_layer_intersection(src_layer, self.boundaries.polygons)
            else:
                layer = src_layer

        layer.ResetReading()
        
        return layer



class MatplotOutput:
    def __init__(self):
        pyplot.title('Contours data plot')
    
    
    def add_geometry(self, height, geometry):
        x = []
        y = []
        for i in range(geometry.GetPointCount()):
             x.append(geometry.GetX(i))
             y.append(geometry.GetY(i))
        pyplot.plot(x, y)


    def flush(self):
        pyplot.show() 



# class outline, not yet functional
class OsmOutput:
    def __init__(self, filename):
        self.filename = filename
    
    
    def add_geometry(self, height, geometry):
        print(height)
        print(geometry)
    
    
    def flush(self):
        pass



# TODO class PbfOutput:



class Transformation:
    def __init__(self, data_input, data_output):
        self.data_input = data_input
        self.data_output = data_output
        
        self.reproject = lambda geometry: None


    def add_reprojection(self, src_srs, dst_srs):
        spatial_ref = osr.SpatialReference()
        spatial_ref.ImportFromEPSG(src_srs)

        dest_spatial_ref = osr.SpatialReference()
        try:
            dest_spatial_ref.SetAxisMappingStrategy(osr.OAMS_AUTHORITY_COMPLIANT)
        except AttributeError:
            pass
        dest_spatial_ref.ImportFromEPSG(dst_srs)
        coordTrans = osr.CoordinateTransformation(spatial_ref, dest_spatial_ref)
        if spatial_ref.EPSGTreatsAsLatLong() != dest_spatial_ref.EPSGTreatsAsLatLong():
            self.reproject = lambda geometry: (geometry.Transform(coordTrans), geometry.SwapXY())
        else:
            self.reproject = lambda geometry: geometry.Transform(coordTrans)


    # TODO Ramer-Douglas-Peucker (RDP) simplification
    #      see phyghtmap
    def add_simplify_rdp(self, epsilon, max_distance):
        pass
    
    
    def __process_feature(self, height, ogrfeature):
        if not ogrfeature:
            return
        
        ogrgeometry = ogrfeature.GetGeometryRef() # TODO: directly?
        
        if not ogrgeometry:
            return

        if self.reproject:
            self.reproject(ogrgeometry)
        #elif self.simplify:
        #    self.simplify(ogrgeometry)

        self.data_output.add_geometry(height, ogrgeometry)
    
    
    def process(self):
        layer = self.data_input.fetch_data()

        # loop through layer features
        for j in range(layer.GetFeatureCount()):
            ogrfeature = layer.GetNextFeature()
            self.__process_feature(ogrfeature[self.data_input.featname], ogrfeature)
        
        self.data_output.flush()



# MAIN

logging.basicConfig(level = logging.DEBUG)

parser = argparse.ArgumentParser(description = 'Write contour lines from a file or databse source ' + \
                                               'to an osm file')
parser.add_argument('--datasource', dest = 'datasource', help = 'Database connectstring or filename')
parser.add_argument('--layername', dest = 'layername', \
                    help = 'Database table or layer name containing the contour data. ' + \
                           'If omitted the first layer will be taken')
parser.add_argument('--layer-feature', dest = 'layerfeat', \
                    help = 'Database column or layer feature containg the elevation')
parser.add_argument('--layer-geom', dest = 'layergeom', \
                    help = 'Database column or layer geometry containing the contour')
parser.add_argument('--src-srs', dest = 'srcsrs', type = int, default = 4326, \
                    help = 'EPSG code of input data. Do not include the EPSG: prefix.')
parser.add_argument('--dst-srs', dest = 'dstsrs', type = int, default = 4326, \
                    help = 'EPSG code of output file. Do not include the EPSG: prefix.')
parser.add_argument('--poly', dest = 'poly', \
                    help = 'Osmosis poly-file containing the boundaries to process')
args = parser.parse_args()

poly = None
if args.poly:
    poly = Polyfile()
    poly.read_file(args.poly)
    #poly.set_boundaries(6.051, 6.1232, 50.4792, 50.5191)

data_input = DataSource(args.datasource, args.layername, args.layerfeat, args.layergeom, args.srcsrs, poly)
#data_output = OsmOutput('test.osm')
data_output = MatplotOutput()

transform = Transformation(data_input, data_output)
transform.add_reprojection(args.srcsrs, args.dstsrs)
#transform.add_simplify_rdp(epsilon, max_distance)
transform.process()

