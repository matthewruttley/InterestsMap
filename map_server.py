#!/usr/bin/env python

#Module to generate a map based on places you're interested in
#from your Firefox History
# mruttley - 2015-04-14

from json import load
from codecs import open as copen
from re import findall
from collections import defaultdict
from os import listdir, path
from sqlite3 import connect

from flask import Flask, render_template, request, make_response
app = Flask(__name__)

def load_countries():
	"""Creates a useful datatype from the countries json file, where
	each keyword is turned into a tuple and references a countrycode"""
	
	with copen('countries_en.json', encoding='utf8') as f:
		payload = load(f)
	
	keywords = {} #mapping kw --> country
	for entry in payload:
		if 'latlong' in entry:
			code = tuple(entry['latlong'])
		elif 'country_code' in entry:
			code = (entry['country_code'])
		else:
			continue
		
		for k,v in entry.iteritems():
			if k != 'latlong':
				for kw in v:
					keywords[tuple(kw.split())] = code
				
	return keywords

def create_ngrams(kw_iterable):
	"""takes a list of keywords and computes all possible ngrams e.g.
		in> ['nice', 'red', 'wine']
		out> [
			('nice',),
			('red',),
			('wine',),
			('nice', 'red'),
			('red', 'wine'),
			('nice', 'red', 'wine')
			]
	"""
	kwCount = len(kw_iterable)
	output = []
	for n in reversed(range(kwCount+1)[1:]):
		for tokenIndex in range(kwCount-n+1):
			output.append(tuple(kw_iterable[tokenIndex:tokenIndex+n]))
	return output

def find_places_location():
	"""Finds the location of the largest places.sqlite file"""
	location = ""
	filesize = 0
	for user in listdir('/Users'):
		profile_dir = '/Users/' + user + '/Library/Application Support/Firefox/Profiles/'
		if path.exists(profile_dir):
			for profile in listdir(profile_dir):
				places_location = profile_dir + profile + "/places.sqlite"
				if path.exists(places_location):
					size = path.getsize(places_location)
					if size > filesize:
						filesize = size
						location = places_location
	return location

def find_country_urls():
	"""Scans the firefox history for country URLs"""
	#get a list of urls in the history
	location = find_places_location()
	conn = connect(location)
	c = conn.cursor()
	query = """
		SELECT url, count(moz_historyvisits.id) as hits
		FROM moz_historyvisits
		INNER JOIN moz_places ON moz_historyvisits.place_id = moz_places.id
		GROUP BY url
	"""
	
	#load the json
	mappings = load_countries()
	
	#set up the results datatype
	results = defaultdict(lambda: [0, defaultdict(int)])

	#iterate through urls
	for result in c.execute(query):
		url = result[0].lower()
		keywords = findall("[a-z]{2,}", url) #tokenize the url
		ngrams = create_ngrams(keywords) #generate all possible ngrams
		
		#a url can't reference the same country twice so we have to do a count instead
		tmp_countries = defaultdict(int)
		tmp_ngrams = defaultdict(lambda: defaultdict(int))
		
		for ngram in ngrams:
			if ngram in mappings: #1 url can't reference the same country twice
				tmp_countries[mappings[ngram]] += 1
				tmp_ngrams[mappings[ngram]][" ".join(ngram)] += 1
		
		for country in tmp_countries.iterkeys():
			results[country][0] += result[1]
		
		for country, ngrams in tmp_ngrams.iteritems():
			for ngram in ngrams:
				results[country][1][ngram] += result[1]
	
	results = sorted(results.items(), key=lambda x: x[1][0], reverse=True)
	for x in range(len(results)):
		results[x][1][1] = sorted(results[x][1][1].items(), key=lambda y: y[1], reverse=True)
	
	return results

def country_code_to_name():
	"""Basic mapping"""
	mapping = {}
	
	with copen('countries_en.json', encoding='utf8') as f:
		payload = load(f)
		for entry in payload:
			if 'country_code' in entry:
				mapping[entry['country_code']] = entry['country_names'][0]
	
	return mapping

@app.route('/')
def show_main_page():
	#get a list of countries
	data = {'countries': []}
	
	code_mapping = country_code_to_name()
	
	for x in find_country_urls():
		if type(x[0]) != tuple: #will deal with islands later
			data['countries'].append(
				[
					x[0],   #country code
					x[1][0],#hits
					x[1][1], #specific 2nd tier keyword hits
					code_mapping[x[0]]   #country name
				]
			)
	
	#render the template
	return render_template("map.html", data=data, main_page=True)

if __name__ == '__main__':
	app.debug = True
	app.run()



