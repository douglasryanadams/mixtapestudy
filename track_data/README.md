Since Spotify removed access to their data, these scripts will collect as much as they can and consolidate it into a single searchable document from Kaggle datasets.

There are three scripts that work together and hand off artifacts. Eventually as this concept solidifies a more unified, well designed implementation may emerge. I would consider the current state a usable prototype.

generate_feature_source.py
==========================

This script consolidates Kaggle data into features.db, it has several optimizations:

1. Only downloads zip files that don't exist already
2. Maps CSV headings to column names we care about in the DB
3. Only reads each file once and can resume reading if interrupted

Room for further optimization/work in progress:

1. Loading the CSV files in for-loops is slow, could be sped up dramatically with pandas
2. Currently doesn't write songs without spotify_id or isrc


generate_track_history.py
=========================

1. Fetches track IDs from Spotify based on track name and artist search
2. Uses the spotify track IDs or isrcs to pair data up with tracks in features.db (generated above)
3. Caches track IDs in cache.db to avoid extra hits to Spotify API

Room for further optimization:

1. Could skip the Spotify API calls for Track IDs altogether if we only use kaggle data

generate_soundstat_data.py
==========================

A new project has arrived in response to Spotify removing their service. [soundstat.info](soundstat.info) (note: not related to soundstats.com)

This project will generate data based on spotify track IDs. [Documentation](https://soundstat.info/api/v1/docs#/)

Example response data:

```json
{
  "id": "0HLWvLKQWpFdPhgk6ym58n",
  "name": "Who Says",
  "artists": [
    "John Mayer"
  ],
  "genre": "singer-songwriter",
  "popularity": 57,
  "features": {
    "tempo": 90.67,
    "key": 9,
    "mode": 1,
    "key_confidence": 0.7,
    "energy": 0.28,
    "danceability": 0.41,
    "valence": 0.64,
    "instrumentalness": 0.8,
    "acousticness": 0.97,
    "loudness": 0.39,
    "segments": {
      "count": 43,
      "average_duration": 0.66
    },
    "beats": {
      "count": 43,
      "regularity": 0.94
    }
  }
}
```

Note that these fields do not match 1-1 with Spotify's data, and for the fields that it does share, the values are not comparable.

This script allows us to use the CSV files generated from `generate_track_history.py` which contains Spotify Track IDs and fill out a complete dataset with Soundstat data.

Note, currently this API will return a lot of 404s as tracks we request are not available in the dataset. However, over time it will analyze tracks and fill in the dataset.


