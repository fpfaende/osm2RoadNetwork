#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created in June 2016 in ComplexCity Lab

@author: github.com/fpfaende
'''

# standard python libraries
import time
from time import localtime, strftime
import argparse
import json
import re

# external python lirabries
from imposm.parser import OSMParser
import networkx as nx
from networkx.readwrite import json_graph
import osr, ogr

#internal python librairies
from roadTypes import franceRoads

G = nx.Graph()

# simple class that handles the parsed OSM data.
class Roads(object):
	def nodes(self, coords):
		for osmid, lon, lat in coords:
			G.add_node(osmid,longitude=float(lon), latitude=float(lat))

	def edges(self, ways):
		for osmid, tags, refs in ways:
			if 'highway' in tags:
				highway = tags['highway']
				bicycle = False
				footway = True
				oneway = False
				lanes = 1
				level = -1
				
				# Update bicycling information using specific tag (priority) or 'highway' tag
				if 'bicycle' in tags:
					bicycle = True if tags['bicycle'] == 'yes' or tags['bicycle'] == 'designated' else False
				elif highway == 'cycleway' or highway == 'cyleway' :
					bicycle = True
				else:
					bicycle = False

				# Update pedestrian information using specific tag (priority) or 'highway' tag
				if 'foot' in tags:
					footway = True if tags['foot'] == 'yes' else False 
				elif highway == 'pedestrian' or highway == 'footway':
					footway = True
				else:
					footway = False

				if 'oneway' in tags:
					oneway = True if tags['oneway'] == 'yes' else False
				
				# Look for any number in tag 'lanes' and extract it as the lane count
				if 'lanes' in tags:
					lanes = tags['lanes']
					m = re.search('\D', lanes)
					try:
						if m:
							lanes = int(lanes[:m.start()])
						else:
							lanes = int(lanes)
					except ValueError, e:
						lanes = 1
						print 'lanes value error for',tags['lanes'],'osmid',osmid
				# Load 'highway' tag value. If error, tag is not osm compliant, defaulted to 'unclassified'
				try:
					highway.encode('ascii')
				except UnicodeEncodeError:
					highway = 'unclassified'

				for levelItem in franceRoads['levels']:
					key, values = levelItem.keys()[0], levelItem.values()[0]
					if str(highway).lower() in values:
						level = key
				
				# if the level is unknow you might want to include it in the level file (roadTypes.py)
				# it oftens comes from miswritten osm tag
				if level == -1:
					if verbose:
						print 'highway tag',highway,'unknow for osmid',osmid,'default to level 3'
					level = 3

				for i in range(1, len(refs)):
					G.add_edge(refs[i-1], refs[i], osmid=osmid, highway=str(highway), level=int(level), lanes=lanes, oneway=oneway)
					
def updateEdgesWithMetricDistance(epsgCode):
	# we assume initial epsg is wsg84 (merctor projection)
	metricDistance = {}
	sourceProjection = osr.SpatialReference()
	sourceProjection.ImportFromEPSG(4326)
	destinationProjection = osr.SpatialReference()
	destinationProjection.ImportFromEPSG(epsgCode) # https://epsg.io/2154
	coordTrans = osr.CoordinateTransformation(sourceProjection, destinationProjection)
	
	for edge in G.edges():
		node1, node2 =  edge
		line = ogr.Geometry(ogr.wkbLineString)
		line.AddPoint(G.node[node1]['latitude'], G.node[node1]['longitude'])
		line.AddPoint(G.node[node2]['latitude'], G.node[node2]['longitude'])
		line.Transform(coordTrans)
		length = line.Length()
		metricDistance[edge] = length
	nx.set_edge_attributes(G, 'length', metricDistance)

def clean(): 
	#remove node without complete geographic information
	for node in G.nodes():
		if 'latitude' not in G.node[node] or 'longitude' not in G.node[node]:
			G.remove_node(node)

	# remove nodes with degree 0
	for node in G.nodes():
		if len(G[node].keys()) == 0:
			G.remove_node(node)

	# remove self referencing edges
	for u,v in G.edges():
		if u == v:
			G.remove_edge(u,v)


def simplify():
	for node in G.nodes():
		if len(G[node].keys()) == 2:
			node1 = G[node].keys()[0]
			node2 = G[node].keys()[1]

			if(node1 in G[node2]):
				continue

			if G[node][node1]['level'] == G[node][node2]['level']:
				attributes = G[node][node1]
				if 'length' in attributes:
					attributes['length'] = G[node][node1]['length'] + G[node][node2]['length']
				G.add_edge(node1,node2, attributes)
				G.remove_node(node)

def boundingBox(coordinates):
	minlon = min(coordinates[0], coordinates[2])
	maxlon = max(coordinates[0], coordinates[2])
	minlat = min(coordinates[1], coordinates[3])
	maxlat = max(coordinates[1], coordinates[3])

	for node in G.nodes():
		if 'latitude' not in G.node[node]:
			G.remove_node(node)
			continue
		if G.node[node]['longitude'] < minlon:
			G.remove_node(node)
			continue
		if G.node[node]['longitude'] > maxlon:
			G.remove_node(node)
			continue
		if G.node[node]['latitude'] < minlat:
			G.remove_node(node)
			continue
		if G.node[node]['latitude'] > maxlat:
			G.remove_node(node)
			continue

def writeGraph(format, outfile):
	if format == 'gexf':
		nx.write_gexf(G, outfile)
	elif format == 'gml':
		nx.write_gml(G, outfile)
	elif format == 'graphml':
		nx.write_graphml(G, outfile)
	elif format == 'json':
		data = json_graph.node_link_data(G)
		with open(outfile, 'w') as of:
			json.dump(data, of)

def graphSummary():
	print nx.info(G)

parser = argparse.ArgumentParser(
			description='''Extract road networks from your osm file''',
			epilog='''Please be patient, this can take up to 300 sec for a city wide extract''')

parser.add_argument('osm_file', action='store', help='your .osm, .pbf, .osm.bz2 source file')
parser.add_argument('-o', '--output', action='store', dest='outfile', default='osmRoadNetwork.gexf', help='destination graph file')
parser.add_argument('-f', '--format', action='store', choices=['gexf', 'gml', 'graphml', 'json'], default='gexf', help='graph format to choose from gexf, gml, graphml, json and shp. Format should match your outfile extension.')
parser.add_argument('-b', '--boundingBox', action='store', help="Retrains the graph to the provided bounding box. It takes 2 coordinates lon,lat (top left, bottom right) separated by a comma. ex: '121.434, 31.4542, 122.453, 27.554'")
parser.add_argument('-c', '--clean', action='store_true', default=False, help="remove nodes without geographic informations and single nodes")
parser.add_argument('-s', '--simplify', action='store_true', default=False, help="simplify path for network analysis. transform all path like into one edge. add length and keep geo measure only if distance has been calculated beforehand. Equivalent to Ramer Douglas Peucker Algorithm with an infinite epsilon")
parser.add_argument('-d', '--distance', action='store', dest='distance', type=int, default=2154, help="calculate distance for every edge on the graph based on lat & lon")
parser.add_argument('-v', '--verbose', action='store_true', default=False, help="display processing informations")
parser.add_argument('-rdp', action='store_true', default=False, help="display processing informations")
# Ramer Douglas Peucker
arguments = parser.parse_args()

verbose = arguments.verbose

# instantiate counter and parser and start parsing
if verbose:
	begin = localtime()
	print strftime("%H:%M:%S", localtime()) + ' — Parsing ' + str(arguments.osm_file)
roadsNetwork = Roads()
osmParser = OSMParser(concurrency=4, coords_callback=roadsNetwork.nodes, ways_callback=roadsNetwork.edges)
osmParser.parse(arguments.osm_file)

if verbose:
	graphSummary()

# bounding box the graph is necessary
if arguments.boundingBox:
	if verbose:
		print strftime("%H:%M:%S", localtime()) + ' — Bounding Boxing to ' + arguments.boundingBox
	coordinates = [float(x.strip()) for x in arguments.boundingBox.split(',')]
	boundingBox(coordinates)
	if verbose:
		graphSummary()

if arguments.clean:
	if verbose:
		print strftime("%H:%M:%S", localtime()) + ' — Cleaning the graph'
	clean()
	if verbose:
		graphSummary()

if arguments.distance:
	if verbose:
		print strftime("%H:%M:%S", localtime()) + ' — Calculating distance the graph'
	updateEdgesWithMetricDistance(arguments.distance)

if arguments.simplify:
	if verbose:
		print strftime("%H:%M:%S", localtime()) + ' — Simplifying path in graph'
	simplify()
	if verbose:
		graphSummary()

if verbose:
	print strftime("%H:%M:%S", localtime()) + ' — writing ' + arguments.format + ' graph in ' + arguments.outfile
writeGraph(arguments.format, arguments.outfile)

if verbose:
	print 'finished in ' + str(time.time() - time.mktime(begin))
