InterestsMap: A map of countries you're interested in, based on your Firefox history
# Usage

    $ python map_server.py

...then visit http://localhost:5000
# Requirements
* python2.7
* sqlite3
* flask

# Datasets
`countries_en.json` is based on data from the following sources:
* https://en.wikipedia.org/wiki/ISO_3166-1 (Alpha-2 code)
* https://en.wikipedia.org/wiki/List_of_adjectival_and_demonymic_forms_for_countries_and_nations
* http://jvectormap.com/examples/markers-world/ (long/lats for small territories)
* GeoNames long/lat database
