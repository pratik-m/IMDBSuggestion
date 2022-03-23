"""	
	IMDB Suggestion
	IMDB has a undocumented api to fetch the suggestion results that you
	type on the search box. This is a wrapper around that API

	By Pratik Munot | 30 June 2018

	Dependent modules/library: BeautifulSoup, requests

	USAGE:
	-----------------------------------------------------------------------
	>>> import IMDBSuggest
	>>> imdb_suggest = IMDBSuggest.IMDBSuggestion()
	>>> results = imdb_suggest.search('Captain')
"""

import json
import logging
import pprint
import string
import sys
import unicodedata
import warnings

import bs4 as bs
import requests

#Constants
MAX_TRY_COUNT = 3
DECREMENT_QUERY_LEN = [15, 10, 5]
IMDB_SUGGESTS_URL = 'https://v2.sg.media-imdb.com/suggests/'
IMDB_TITLE_URL = 'https://www.imdb.com/title/'

#other setup
def warning_on_one_line(message, category, filename, lineno, file=None, line=None):
    return '{0} {1}: {2}: {3}\n'.format('[Warning]', lineno, category.__name__, message)

#warnings.formatwarning = warning_on_one_line
#logging.basicConfig(level=logging.DEBUG)


class IMDBSuggestion(object):
	"""
		Wrapper for the IMDB suggestion API. This API is involved when
	   	you type in the search bar and it returns the instant suggestion.
	   	The API accepts only 20 characters and returns matching results 
	   	for the search query. 
	"""

	def __init__(self):
		self.top = 99
		self.debug = False
		self.query = ''		
		self.imdb_results = []
		self.orginal_query = ''
		self.imdb_json_response = {}
		self.fetch_additional_details = False
		self.valid_chars = string.ascii_letters + string.digits + '_' + ' '
		
	def search(self, query, category='All', top=99, 
			fetch_additional_details=False, debug=False):
		"""
			Search function will lookup the query and return the results:

			Args:
				query: the search query
				category: do you want to search All or Titles etc
				top: return no. of results. Top should be greater than 0
				fetch_additional_details: True if fetches rating and genre
				debug: True if debugging has to be turned on else False

			Returns:
				Array of IMDBSearchResult objects if found else []
		"""
		# Put all guard clauses at the beginning 

		#IMDB instant suggestion only works with All or Title
		#this will be the part of the URL
		if category == 'All':
			cat_path = ''
		elif category == 'Titles':
			cat_path = '/titles/'
		else:
			raise ValueError('Category can only be All or Titles')

		#check for top is position and greater than 0. if not, throw a 
		#warning and set it to 99
		if top <= 0:
			logging.warn('Top should be greater than 0, returning all results')
			top = 99

		self.debug = debug
		self.top = top
		self.fetch_additional_details = fetch_additional_details
		
		#clean the query - the API only accepts characters, underscores,
		#space and numbers. Replace accented chars, strip special chars.
		#The API only takes in 20 characters as input
		query = self._clean_string(query)

		#stored the stripped version of query for later use
		self.orginal_query = self.query = query.lower()
		self.query = self.query[:20].replace(' ', '_')

		#the endpoint only accepts lower, it takes in alphabets as well 
		#as numbers. It accepts _ as well
		char_index = self.query[0]

		#generate the URL and get response
		try_count = 0
		while True:
			request_url = (IMDB_SUGGESTS_URL 
						+ cat_path 
						+ char_index + '/' 
						+ self.query + '.json')
			
			print('Requested URL: {}'.format(request_url))

			try:
				response = requests.get(request_url)
			except requests.exceptions.RequestException as e:
				logging.error('[ERROR] Bad URL recieved or timeout occured.'
								'Retry after some time')
				logging.debug(e)

			#parse the response
			search_results = self._parse_result(response.text)

			#check the lenght of the query..if less than decrement
			#query length, then exclude those options
			if len(search_results) == 0 and try_count < MAX_TRY_COUNT:
				while True:
					#if lenght of the query is already less than first
					#decrement, go for the next decemental length
					if len(self.query) < DECREMENT_QUERY_LEN[try_count] and \
						try_count < MAX_TRY_COUNT:
						try_count += 1
					else:
						break

				self.query = self.query[:DECREMENT_QUERY_LEN[try_count]]
			else:
				break

			try_count += 1

		return search_results

	def _parse_result(self, response):
		"""
			To parse the response from the suggestion API. The response
			is wrapped in a javascript function in format of 
			imdb$<query>(<json output>). 

			Args:
				repsonse: raw response returned from the API
				
			Returns:
				json object for the search results
		"""

		#reset the variables when parse is called
		self.imdb_results = []
		self.imdb_json_response = {}

		#Remove the javascript function imdb$<search query>(  ) 
		#from the response
		start_pos = len('imdb$') + len(self.query) + 1
		response =  response[start_pos:-1]

		#if no search results are return, return an empty array
		try:
			self.imdb_json_response = json.loads(response)['d']
		except Exception as e:
			logging.warn('No search results returned. Attempting to fetch'
						' results for shorter query.')
			return self.imdb_results 

		if self.debug: 
			self.print_json_dump()

		for idx, suggestion in enumerate(self.imdb_json_response):
			if self.top != -1 and idx > self.top:
				break

			#not all json attributes are returned based on the category
			#of the search results. As a precaution, setting them to 
			#default value, in case they dont exists
			suggestion.setdefault('y',0)
			suggestion.setdefault('q','unknown')

			#make a compare of title returned and actaual..the example is 
			#Once upon a time in AMerica/in West 
			match_percent = self._compare_string(self.orginal_query, suggestion['l'])

			suggestion = IMDBSearchResult(suggestion['id'],
									suggestion['l'],
								 	suggestion['y'],
								 	suggestion['q'], 
								 	idx + 1,
								 	match_percent,
								 	self.fetch_additional_details)
			self.imdb_results.append(suggestion)
			
		return self.imdb_results

	def _compare_string(self, string1, string2):
		"""
			the function compares the two strings and returns the 
			percentage match.
		"""
		x = string1
		y = self._clean_string(string2).lower()
		max_length = max(len(x), len(y))

		match_char_cnt = 0
		for i,j in zip(x, y):
			if i == j:
				match_char_cnt += 1

		return round((match_char_cnt/max_length) * 100, 2)

	def _clean_string(self, input):
		"""
			returns cleaned string.  
			The accented charcters are converted to normal english char 
			and all chacters except strings,numbers, underscore and space
			are stripped.
		"""
		str_encode = unicodedata.normalize('NFKD', input).encode('ASCII', 'ignore')
		str_decode = str_encode.decode()
		return ''.join(c for c in str_decode if c in self.valid_chars)

	def print_json_dump(self):
		#pretty printing the json with depth as 3
		pprint.pprint(self.imdb_json_response, depth=2)


class IMDBSearchResult(object):
	"""
		Class to house the result recieved from IMDB suggestions. A match
		percent attribute is also added. User can refer to this percentage
	"""

	def __init__(self, id, l, y , q, idx, 
				match_percent, fetch_additional_details=False):
		self.id = id
		self.label = l
		self.year = y
		self.category = q
		self.idx = idx
		self.genre = []
		self.rating = 0.0
		self.match_percent = match_percent
		self.type = ''

		if self.id.startswith('nm'): 
			self.type = 'Actor'
		elif self.id.startswith('tt'): 
			self.type ='Title'

		if fetch_additional_details:
			self._get_additional_info()

	def _get_additional_info(self):
		"""
			Fetch the rating and genre of the title passed. 
			No results will be fetched for any other category.
		"""
		if self.id.startswith('tt'):
			url = IMDB_TITLE_URL + self.id
			print('Request url for IMDB title search: {}'.format(url))
			try:
				response = requests.get(url)
				if debug: pprint.pprint(repsonse)
				body = bs.BeautifulSoup(response.text, 'html.parser')
				self.rating = body.find('div', class_='ratingValue').strong.span.text
				self.genre = [t.text for t in body.find_all('span', itemprop='genre')]
			except Exception as e:
				warnings.warn('Error occured while fetching additional details.'
					  'Check the URL/repsonse. Continuing with other requests')

	def __str__(self):
		if self.type == 'Title': 
			return '{0} ({1}) | {2} {3} | Match: {4}%'.format(self.type, self.id,
				 self.label, self.year, self.match_percent)
		elif self.type == 'Actor': 
			return '{0} ({1}) | {2}'.format(self.type, self.id, self.label)
		
	def __repr__(self):
		print_str = '{}.{}({},{},{},{},{})'
		return print_str.format(self.__class__.__module__,
								self.__class__.__qualname__,
								self.id,
								self.label,
								self.year,
								self.category,
								self.idx)