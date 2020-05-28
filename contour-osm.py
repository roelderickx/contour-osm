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
from xml.dom import minidom

class Polyfile:
    def __init__(self):
        self.__filename = None
        self.__name = None
        self.__polygons = ogr.Geometry(ogr.wkbMultiPolygon)
    
    
    def set_boundaries(self, minlon, maxlon, minlat, maxlat):
        self.__name = 'bbox'
        polygon = ogr.Geometry(ogr.wkbPolygon)
        poly_section = ogr.Geometry(ogr.wkbLinearRing)
        # add points in traditional GIS order (east, north)
        poly_section.AddPoint(minlon, minlat)
        poly_section.AddPoint(maxlon, minlat)
        poly_section.AddPoint(maxlon, maxlat)
        poly_section.AddPoint(minlon, maxlat)
        poly_section.AddPoint(minlon, minlat)
        polygon.AddGeometry(poly_section)
        self.__polygons.AddGeometry(polygon)
    
    
    def read_file(self, filename):
        self.__filename = filename
        self.__polygons = ogr.Geometry(ogr.wkbMultiPolygon)
        
        self.__read_poly()
    
    
    def __read_poly(self):
        with open(self.__filename, 'r') as f:
            self.__name = f.readline().strip()
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
                    self.__polygons.AddGeometry(polygon)
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
                # add point in traditional GIS order (east, north)
                poly_section.AddPoint(float(ords[0]), float(ords[1]))
                
        return poly_section


    def get_geometry(self, srs = 4326):
        polygons = self.__polygons.Clone()
        
        src_spatial_ref = osr.SpatialReference()
        src_spatial_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        src_spatial_ref.ImportFromEPSG(4326)

        dest_spatial_ref = osr.SpatialReference()
        dest_spatial_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        dest_spatial_ref.ImportFromEPSG(srs)

        transform = osr.CoordinateTransformation(src_spatial_ref, dest_spatial_ref)
        polygons.Transform(transform)
        
        return polygons
    
    '''
    def to_wkt_string(self, srs = 4326, force_eastnorth_orientation = False):
        return self.get_geometry(srs, force_eastnorth_orientation).ExportToWkt()


    def to_wkb_string(self, srs = 4326, force_eastnorth_orientation = False):
        polygons = self.get_geometry(srs, force_eastnorth_orientation)
        return ''.join(format(x, '02x') for x in polygons.ExportToWkb())
    '''


class DataSource:
    def __init__(self, datasource, layername, preferred_feat, preferred_geom, boundaries, \
                 src_srs, dest_srs):
        self.datasource = ogr.Open(datasource, gdalconst.GA_ReadOnly)
        self.driver = self.datasource.GetDriver()
        self.intersect_ds = None # intersection datasource, should not go out of scope
        self.layername = layername
        self.featname = None
        self.geomname = None
        self.src_srs = src_srs
        self.dest_srs = dest_srs
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
                self.boundaries.get_geometry(self.src_srs).ExportToWkt(), self.src_srs, \
                self.layername, self.geomname)
        else:
            sql = 'select %s, %s from %s' % \
                (self.featname, self.geomname, self.layername)

        logging.info('Generated SQL statement: %s' % sql)
        
        return sql


    def __calc_layer_intersection(self, layer, geometry):
        spatial_ref = osr.SpatialReference()
        spatial_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        spatial_ref.ImportFromEPSG(self.src_srs)
        
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
    
    
    def __fetch_data(self):
        layer = None
        if self.driver.GetName() == 'PostgreSQL':
            layer = self.datasource.ExecuteSQL(self.__get_query())
        else:
            src_layer = self.datasource.GetLayer(self.layername)
            
            if self.boundaries:
                bounds = self.boundaries.get_geometry(self.src_srs)
                layer = self.__calc_layer_intersection(src_layer, bounds)
            else:
                layer = src_layer

        layer.ResetReading()

        return layer
    
    
    # datawriter should be a class with two public member functions:
    # - add_geometry(height, geometry)
    # - flush()
    def process_data(self, datawriter):
        layer = self.__fetch_data()
        
        src_spatial_ref = layer.GetSpatialRef()
        dest_spatial_ref = osr.SpatialReference()
        dest_spatial_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        dest_spatial_ref.ImportFromEPSG(self.dest_srs)
        coord_transform = osr.CoordinateTransformation(src_spatial_ref, dest_spatial_ref)
        
        for j in range(layer.GetFeatureCount()):
            ogrfeature = layer.GetNextFeature()
            
            if ogrfeature:
                height = ogrfeature[self.featname]
                ogrgeometry = ogrfeature.GetGeometryRef()
                
                if ogrgeometry and ogrgeometry.GetPointCount() > 0:
                    ogrgeometry.Transform(coord_transform)
                    datawriter.add_geometry(height, ogrgeometry)
        
        datawriter.flush()



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
        self.__filename = filename
        self.__current_id = 0
        
        self.__osmdoc = minidom.Document()
        self.__osmnode = self.__osmdoc.createElement('osm')
        self.__osmnode.setAttribute("version", "0.6")
        self.__osmnode.setAttribute("generator", "contour-osm")
        self.__osmnode.setAttribute("upload", "false")
        self.__waynodes = []
    
    
    def __classify(self, height):
        if height % 100 == 0: # height % majorDivisor
            return "elevation_major"
        elif height % 20 == 0: # height % mediumDivisor
            return "elevation_medium"
        else:
            return "elevation_minor"


    def __add_node_nodes(self, geometry):
        for i in range(geometry.GetPointCount()):
            self.__current_id = self.__current_id - 1
            nodenode = self.__osmdoc.createElement('node')
            nodenode.setAttribute("visible", "true")
            nodenode.setAttribute("id", str(self.__current_id))
            nodenode.setAttribute("lat", "%f" % geometry.GetY(i))
            nodenode.setAttribute("lon", "%f" % geometry.GetX(i))
            self.__osmnode.appendChild(nodenode)
    
    
    def __add_way_tag_node(self, waynode, key, value):
        waytagnode = self.__osmdoc.createElement('tag')
        waytagnode.setAttribute("k", key)
        waytagnode.setAttribute("v", value)
        waynode.appendChild(waytagnode)
    
    
    def __create_way_node(self, way_id, first_node_id, last_node_id, height):
        waynode = self.__osmdoc.createElement('way')
        waynode.setAttribute("visible", "true")
        waynode.setAttribute("id", str(way_id))
        
        for i in range(way_id - 1, self.__current_id - 1, -1):
            waynodenode = self.__osmdoc.createElement('nd')
            waynodenode.setAttribute("ref", str(i))
            waynode.appendChild(waynodenode)
        
        self.__add_way_tag_node(waynode, "ele", "%d" % int(height))
        self.__add_way_tag_node(waynode, "contour", "elevation")
        self.__add_way_tag_node(waynode, "contour_ext", self.__classify(height))
        
        return waynode
    
    
    def add_geometry(self, height, geometry):
        self.__current_id = self.__current_id - 1
        way_id = self.__current_id
        
        self.__add_node_nodes(geometry)
        self.__waynodes.append(self.__create_way_node(way_id, way_id - 1, self.__current_id, height))
    
    
    def flush(self):
        for waynode in self.__waynodes:
            self.__osmnode.appendChild(waynode)
        self.__osmdoc.appendChild(self.__osmnode)
        
        f = open(self.__filename, 'w')
        self.__osmdoc.writexml(f, "", "", "\n")
        f.close()



# TODO class PbfOutput:



# MAIN

logging.basicConfig(level = logging.DEBUG)

parser = argparse.ArgumentParser(description = 'Write contour lines from a file or database source ' + \
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

data_input = DataSource(args.datasource, args.layername, args.layerfeat, args.layergeom, poly, \
                        args.srcsrs, args.dstsrs)
data_output = OsmOutput('test.osm')
#data_output = MatplotOutput()

data_input.process_data(data_output)

