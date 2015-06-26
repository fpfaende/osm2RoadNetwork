#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created in June 2015 in ComplexCity Lab

@author: fpfaende
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


G = nx.Graph()

# simple class that handles the parsed OSM data.
class Roads(object):
	roads = 0
	
	def coords(self, coords):
		for osmid, lon, lat in coords: 
			G.add_node(osmid,longitude=float(lon), latitude=float(lat))

	def edges(self, ways):
		# callback method for ways
		for osmid, tags, refs in ways:
			if 'highway' in tags:
				oneway = False
				lanes = 1
				if 'oneway' in tags:
					oneway = True if tags['oneway'] == 'yes' else False
				if 'lanes' in tags:
					lanes = tags['lanes']
					m = re.search('\D', lanes)
					if m:
						lanes = int(lanes[:m.start()])
					else:
						lanes = int(lanes)
						 
				for i in range(1, len(refs)):					
					G.add_edge(refs[i-1], refs[i], osmid=osmid, highway=str(tags['highway']), lanes=lanes, oneway=oneway)
					# G.add_edge(refs[i-1], refs[i], id=osmid, highway=tags['highway'], lanes=lanes, oneway=oneway

def clean(): 
	latitudes = nx.get_node_attributes(G,'latitude')
	for node in G.nodes():
		if node not in latitudes:
			G.remove_node(node)

	# remove individuals nodes
	degrees = G.degree(G)
	for node in G.nodes():
		if degrees[node] == 0:
			G.remove_node(node)

def boundingBox(coordinates):
	minlon = min(coordinates[0], coordinates[2])
	maxlon = max(coordinates[0], coordinates[2])
	minlat = min(coordinates[1], coordinates[3])
	maxlat = max(coordinates[1], coordinates[3])
	longitudes = nx.get_node_attributes(G,'longitude')
	latitudes = nx.get_node_attributes(G,'latitude')
	for node in G.nodes():
		if longitudes[node] < minlon or longitudes[node] > maxlon or latitudes[node] < minlat or latitudes[node] > maxlat:
			G.remove_node(node)

def writeGraph(format, outfile):
	if format == 'gexf':
		nx.write_gexf(G, outfile)
	elif format == 'gml':
		nx.write_gml(G, outfile)
	elif format == 'graphml':
		nx.write_graphml(G, outfile)
	elif format == 'json':
		data = nx.node_link_data(G)
		with open(outfile, 'w') as of:
			json.dump(data, of)
	elif format == 'shp':
		nx.write_shp(G, outfile)

def graphSummary():
	print 'Graphe properties'
	print '\tnodes: ', G.number_of_nodes()
	print '\tedges: ', G.number_of_edges()

parser = argparse.ArgumentParser(
			description='''Extract road networks from your osm file''',
			epilog='''Please be patient, this can take up to 300 sec for a city wide extract''')

parser.add_argument('osm_file', action='store', help='your .osm, .pbf, .osm.bz2 source file')
parser.add_argument('-o', '--output', action='store', dest='outfile', default='osmRoadNetwork.gexf', help='destination graph file')
parser.add_argument('-f', '--format', action='store', choices=['gexf', 'gml', 'graphml', 'json', 'shp'], default='gexf', help='graph format to choose from gexf, gml, graphml, json and shp. Format should match your outfile extension.')
parser.add_argument('-bb', '--boundingBox', action='store', help="Retrains the graph to the provided bounding box. It takes 2 coordinates lon,lat (top left, bottom right) separated by a comma. ex: '121.434, 31.4542, 122.453, 27.554'")
parser.add_argument('-c', '--clean', action='store_true', default=False, help="remove nodes without geographic informations and single nodes ")
parser.add_argument('-v', '--verbose', action='store_true', default=False, help="display processing informations")
arguments = parser.parse_args()

verbose = arguments.verbose

# instantiate counter and parser and start parsing
if verbose:
	begin = localtime()
	print strftime("%H:%M:%S", localtime()) + ' — Parsing ' + str(arguments.osm_file)
roadsNetwork = Roads()
osmParser = OSMParser(concurrency=4, coords_callback=roadsNetwork.coords, ways_callback=roadsNetwork.edges)
osmParser.parse(arguments.osm_file)

if verbose:
	graphSummary()

# bounding box the graph is necessary
if arguments.boundingBox:
	print strftime("%H:%M:%S", localtime()) + ' — Bounding Boxing to ' + arguments.boundingBox
	boundingBox([float(x) for x in arguments.boundingBox.split()])
	if verbose:
		graphSummary()

if arguments.clean:
	print strftime("%H:%M:%S", localtime()) + ' — Cleaning the graph '
	clean()
	graphSummary()

print strftime("%H:%M:%S", localtime()) + ' — writing ' + arguments.format + ' graph in ' + arguments.outfile
writeGraph(arguments.format, arguments.outfile)

print 'finished in ' + str(time.time() - time.mktime(begin))

'''
shanghai=# select count(*) as total, highway from planet_osm_line group by highway order by total desc;
+-------+--------------------+
| total | highway            |
+-------+--------------------+
| 24173 | residential        |
| 13596 | tertiary           |
| 13061 | secondary          |
| 11915 | NULL               |
| 10784 | service            |
| 10161 | primary            |
| 9411  | motorway           |
| 8965  | unclassified       |
| 6815  | motorway_link      |
| 3982  | footway            |
| 2549  | trunk              |
| 2362  | trunk_link         |
| 2358  | primary_link       |
| 1496  | cycleway           |
| 1027  | track              |
| 1009  | path               |
| 861   | secondary_link     |
| 653   | construction       |
| 595   | living_street      |
| 551   | pedestrian         |
| 514   | road               |
| 376   | steps              |
| 267   | tertiary_link      |
| 112   | platform           |
| 35    | demolished         |
| 28    | raceway            |
| 19    | bridleway          |
| 17    | services           |
| 7     | crossing           |
| 4     | unknown            |
| 4     | turning_circle     |
| 2     | proposed           |
| 2     | rest_area          |
| 2     | lane               |
| 1     | tertiary;secondary |
+-------+--------------------+
35 rows in set (0.12 sec)

'''