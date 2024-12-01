# Mixtape Study

This website is used for research studying the effect of playlists generated with self selected songs used to augment patient therapies.

# Development

This is a Python Flask Application. It doesn't do REST, and it doesn't do much (if any) JavaScript. Everything is handled in the Python application so that it can be monitored and debugged without concerns for asynchronous programming, or various browser differences.

The most important thing about this application is that it is fully tested, easy to test, easy to debug, and easy to monitor. To achieve those goals, all logic must reside in the Python Flask application.

Trello board for tracking progress and goals: https://trello.com/b/yGCs72Ff/mixtape-study

## How to Dev

You can run the project locally using the commands in the `makefile`. For example, to run the stack "like production":

```bash
# Note: Requires a .env file containing required environment variables
make run
```

To run a check of the code including formatting, linters, and tests:

```bash
make check
```

Please read the `makefile` to find other supported commands.



## Requirements

1. Python 3.12+
2. Make (from gcc)


# Version 2.0

On November 27, 2024 [Spotify Deprecrated several critical APIs for this application](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api) which puts mixtapestudy.com in a difficult position. They removed access to these APIs without warning or any alternative.

On November 28th, I started looking for an alternative that would provide comparable functionality that begins to decouple the application from Spotify. Thankfully, that day an amazing community based project with similar goals posted an [incredibly timely blog post](https://blog.metabrainz.org/2024/11/) that pointed me in a new direction.
There are rumors that Spotify may extend a grace period to applications that submitted for extension on this day, I have submitted the app for the extension. There are other rumors that a comparable, improved, set of features will be made available by Spotify in a few days or weeks.
While I hope those rumors are true, it's not clear that we can not depend on Spotify exclusively.

I'm beginning work on a fall-back capability that adheres to the same user interface while Spotify sorts out these changes. For now, the listening experience will still take place within Spotify and user their player.
I am focused first on replacing the playlist song generation component.

## Notes

### Playlist Generation

This site looks like a great tool, that's comparable to what we need: https://listenbrainz.org/explore/lb-radio/

The API documentation that supports that query is here: https://listenbrainz.readthedocs.io/en/latest/users/api/misc.html#get--1-explore-lb-radio

The prompt language is documented here: https://troi.readthedocs.io/en/stable/lb_radio.html

Repo for the underlying source code: https://github.com/metabrainz/troi-recommendation-playground

Source code for the API call is here: 

* https://github.com/metabrainz/listenbrainz-server/blob/master/listenbrainz/webserver/views/explore_api.py#L148-L191
* https://github.com/metabrainz/troi-recommendation-playground/blob/main/troi/patches/lb_radio.py

```bash
# Example Query
curl -v 'https://api.listenbrainz.org/1/explore/lb-radio?prompt=artist%3A(noah%20gundersen)&mode=easy' | jq
```

To translate the songs returned by this API need to be translated to Spotify track IDs for the playlist generation.

For this we need to use Spotify's Search API: https://developer.spotify.com/documentation/web-api/reference/search

If we have an isrc:

```bash
curl -v -H 'Authorizaiton: Bearer ...' 'https://api.spotify.com/v1/search?q=isrc%3AUSUM71313944&type=track' | jq
```

### Music Search

We need an API for translating search terms that aren't artists into artists for the search algorithm. That means we need a way to search for traacks by name. A sibling project supports such a search API based on a Lucene search of the MusicBrainz database.

This API will allow me to populate the search results and I'll feed the artists from the tracks into the "generate playlist" using the recommendation API above.

Link to search documentation: https://musicbrainz.org/doc/MusicBrainz_API/Search

```bash
# Example Query
curl -v -H 'user-agent: mixtapestudy/0.0 ( douglas@builtonbits.com )' 'https://musicbrainz.org/ws/2/recording?query=noah%20gundersen&fmt=json&limit=2' | jq '.recordings[0].id'
```

### Music Features/Metadata

Finally, we need an API to analyze the tracks and extract data about the tracks for analysis. AcousticBrainz appears to provide some of that support. Unfortunately it was shelved 2 years ago.

Beyond AcousticBrainz, Last.fm API has some limited data, and Deezer can provide BPM

AcousticBrainz API: https://acousticbrainz.readthedocs.io/api.html

```bash
# Example Query
curl -v -H 'user-agent: mixtapestudy/0.0 ( douglas@builtonbits.com )' 'https://acousticbrainz.org/api/v1/bc8a3cbf-6d03-494b-b040-0baeb845030d/high-level' | jq
```


