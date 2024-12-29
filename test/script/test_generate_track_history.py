from pathlib import Path

from generate_track_history import SpotifyTrack, load_history

PATH_ALL_DATA = Path("test/data/music_history_all.json")
PATH_PARTIAL_DATA = Path("test/data/music_history_missing_data.json")
PATH_REALISTIC_DATA = Path("test/data/music_history_realistic.json")
PATH_SHORT_DATA = Path("test/data/music_history_short.json")


def test_load_history() -> None:
    with PATH_SHORT_DATA.open("r") as data_file:
        assert load_history(data_file) == [
            SpotifyTrack(
                end_time="2023-04-09 03:55",
                artist_name="John Mayer",
                track_name="Heartbreak Warfare",
                ms_played=265550,
            ),
            SpotifyTrack(
                end_time="2023-04-09 04:00",
                artist_name="John Mayer",
                track_name="All We Ever Do Is Say Goodbye",
                ms_played=271011,
            ),
            SpotifyTrack(
                end_time="2023-04-09 04:01",
                artist_name="John Mayer",
                track_name="Half of My Heart",
                ms_played=90674,
            ),
        ]
