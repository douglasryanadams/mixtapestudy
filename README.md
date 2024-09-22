# Mixtape Study

This website is used for research studying the effect of playlists generated with self selected songs used to augment patient therapies.

# Development

This is a Python Flask Application. It doesn't do REST, and it doesn't do much (if any) JavaScript. Everything is handled in the Python application so that it can be monitored and debugged without concerns for asynchronous programming, or various browser differences.

The most important thing about this application is that it is fully tested, easy to test, easy to debug, and easy to monitor. To achieve those goals, all logic must reside in the Python Flask application.

## How to Dev

You can run the project locally using the commands in the `makefile`. For example, to run the stack "like production":

```bash
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