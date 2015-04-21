#!/usr/bin/env python

#Module to generate a map based on places you're interested in
#from your Firefox History
# mruttley - 2015-04-14

from json import load, dumps
from codecs import open as copen
from re import findall
from collections import defaultdict
from os import listdir, path
from sqlite3 import connect
from datetime import date, timedelta
from calendar import timegm

from flask import Flask, render_template, request, make_response, Response
app = Flask(__name__)

def load_countries():
	"""Creates a useful datatype from the countries json file, where
	each keyword is turned into a tuple and references a countrycode"""
	
	with copen('countries_en_2.json', encoding='utf8') as f:
		payload = load(f)
	
	keywords = {} #mapping kw --> country
	for entry in payload:
		#if 'latlong' in entry:
		#	code = tuple(entry['latlong'])
		if 'country_code' in entry:
			code = (entry['country_code'])
		else:
			continue
		
		for k,v in entry.iteritems():
			if k != 'latlong':
				for kw in v:
					keywords[tuple(kw.lower().split())] = code
	
	return keywords

def load_cities():
	"""Creates a payload of (city) --> [latlong, country_code].
	Should be integrated into load_countries() in the future"""
	
	with copen('countries_en_2.json', encoding='utf8') as f:
		payload = load(f)
	
	cities = {}
	
	for country in payload:
		if type(country['cities']) == dict:
			for city, latlong in country['cities'].iteritems():
				city = tuple(city.split())
				cities[city] = latlong #[latlong, country_code]
	
	return cities

def import_payload():
	"""Create a payload of keyword --> location_id"""

def create_ngrams(kw_iterable, max_n=False):
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
		if n <= max_n:
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

def get_urls(recent=False, title=False):
	"""Gets an iterable of urls"""
	
	location = find_places_location()
	conn = connect(location)
	c = conn.cursor()
	
	if recent: #calculate last visit date from 30 days ago
		thirty_days_ago = (date.today()-timedelta(days=30))
		timestamp = timegm(thirty_days_ago.timetuple())
		timestamp = int(str(timestamp) + "000000")
		where_clause = "WHERE last_visit_date >= {0}".format(timestamp)
	else:
		where_clause = ""
	
	query = """
		SELECT url, count(moz_historyvisits.id) as hits, title
		FROM moz_historyvisits
		INNER JOIN moz_places ON moz_historyvisits.place_id = moz_places.id
		{0}
		GROUP BY url
	""".format(where_clause)
	
	urls = c.execute(query)
	return urls

def find_country_urls(recent=False):
	"""Scans the firefox history for country URLs"""
	#get a list of urls in the history
	
	
	#load the json
	mappings = load_countries()
	cities = load_cities()
	
	#set up the results datatype
	results = defaultdict(lambda: [0, defaultdict(int)])
	city_results = defaultdict(lambda: [0, False])

	#iterate through urls
	for result in get_urls(recent):
		url = result[0].lower()
		keywords = findall("[a-z]{2,}", url) #tokenize the url
		ngrams = create_ngrams(keywords, max_n=3) #generate all possible ngrams up to trigrams
		
		#a url can't reference the same country twice so we have to do a count instead
		tmp_countries = defaultdict(int)
		tmp_ngrams = defaultdict(lambda: defaultdict(int))
		tmp_cities = defaultdict(lambda: [0, False])
		
		for ngram in ngrams:
			if ngram in mappings: #1 url can't reference the same country twice
				tmp_countries[mappings[ngram]] += 1
				tmp_ngrams[mappings[ngram]][" ".join(ngram)] += 1
			if ngram in cities:
				tmp_cities[ngram][0] += 1
				tmp_cities[ngram][1] = cities[ngram]
		
		for country in tmp_countries.iterkeys():
			results[country][0] += result[1]
		
		for country, ngrams in tmp_ngrams.iteritems():
			for ngram in ngrams:
				results[country][1][ngram] += result[1]
		
		for city, info in tmp_cities.iteritems():
			city_results[city][0] += 1
			city_results[city][1] = info[1]
	
	results = sorted(results.items(), key=lambda x: x[1][0], reverse=True)
	for x in range(len(results)):
		results[x][1][1] = sorted(results[x][1][1].items(), key=lambda y: y[1], reverse=True)
	
	return [results, city_results]

def country_code_to_name():
	"""Basic mapping"""
	mapping = {}
	
	with copen('countries_en_2.json', encoding='utf8') as f:
		payload = load(f)
		for entry in payload:
			if 'country_code' in entry:
				mapping[entry['country_code']] = entry['country_names'][0]
	
	return mapping

@app.route('/relevant_urls')
def get_relevant_urls():
	country = request.args.get('country')
	city = request.args.get('city')
	recent = request.args.get('recent')
	
	#get urls
	urls = get_urls(recent=recent, title=True)
	
	if city:
		acceptable = set([tuple(findall("[a-z]{2,}", city))])
	else:
		acceptable = set()
		with copen('countries_en_2.json', encoding='utf8') as f:
			for x in load(f):
				if country.lower() in x['country_names']:
					for k, v in x.iteritems():
						if k not in ['latlong', 'country_code']:
							for z in v:
								acceptable.update(create_ngrams(z.split(), max_n=3))
					break
	relevant = []
	for result in urls:
		url = result[0].lower()
		keywords = findall("[a-z]{2,}", url) #tokenize the url
		ngrams = create_ngrams(keywords, max_n=3) #generate all possible ngrams up to trigrams
		for ngram in ngrams:
			if ngram in acceptable:
				relevant.append(result)
				break
	
	relevant = sorted(relevant, key=lambda x: x[1], reverse=True)
	
	dat = dumps(relevant)
	resp = Response(response=dat,
					status=200,
					mimetype="application/json")
	return(resp)
	
	


@app.route('/')
def show_main_page():
	#get a list of countries
	data = {'countries': []}
	
	code_mapping = country_code_to_name()
	searchword = request.args.get('recent')
	
	if searchword:
		countries, cities = find_country_urls(recent=True)
	else:
		countries, cities = find_country_urls()
	
	for x in countries:
		if type(x[0]) != tuple: #will deal with islands later
			data['countries'].append(
				[
					x[0],   #country code
					x[1][0],#hits
					x[1][1], #specific 2nd tier keyword hits
					code_mapping[x[0]]   #country name
				]
			)
	
	data['cities'] = []
	for city_name, info in cities.iteritems():
		data['cities'].append({
				'name': " ".join(city_name),
				'latlong': info[1],
				'hits': info[0]
			})
	
	#render the template
	return render_template("map.html", data=data, main_page=True)

if __name__ == '__main__':
	app.debug = True
	app.run()



