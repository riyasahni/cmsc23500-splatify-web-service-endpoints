import logging
import sqlite3
from flask.cli import with_appcontext

# helper function that converts query result to json list, after cursor has executed a query
# this will not work for all endpoints direct, just the ones where you can translate
# a single query to the required json. 
def to_json(cursor):
    results = cursor.fetchall()
    headers = [d[0] for d in cursor.description]
    return [dict(zip(headers, row)) for row in results]


# Error class for when a key is not found
class KeyNotFound(Exception):
    def __init__(self, message=None):
        Exception.__init__(self)
        if message:
            self.message = message
        else:
            self.message = "Key/Id not found"

    def to_dict(self):
        rv = dict()
        rv['message'] = self.message
        return rv


# Error class for when request data is bad
class BadRequest(Exception):
    def __init__(self, message=None, error_code=400):
        Exception.__init__(self)
        if message:
            self.message = message
        else:
            self.message = "Bad Request"
        self.error_code = error_code

    def to_dict(self):
        rv = dict()
        rv['message'] = self.message
        return rv


"""
Wraps a single connection to the database with higher-level functionality.
Holds the DB connection
"""
class DB:
    def __init__(self, connection):
        self.conn = connection

    # Simple example of how to execute a query against the DB.
    # Again NEVER do this, you should only execute parameterized query
    # See https://docs.python.org/3/library/sqlite3.html#sqlite3.Cursor.execute
    # This is the qmark style:
    # cur.execute("insert into people values (?, ?)", (who, age))
    # And this is the named style:
    # cur.execute("select * from people where name_last=:who and age=:age", {"who": who, "age": age})
    def run_query(self, query):
        c = self.conn.cursor()
        c.execute(query)
        res = to_json(c)
        self.conn.commit()
        return res

    # Run script that drops and creates all tables
    def create_db(self, create_file):
        print("Running SQL script file %s" % create_file)
        with open(create_file, "r") as f:
            self.conn.executescript(f.read())
        return "{\"message\":\"created\"}"

    # Add an album to the DB
    # An album has details, a list of artists, and a list of songs
    # If the artist or songs already exist then they should not be created
    # The album should be associated with the artists.  The order does not matter
    # Songs sould be associated with the album, the order *does* matter and should be retained.
    def add_album(self, post_body):
        try:
            logging.debug("Add Album with post %s" % post_body)
            album_id = post_body["album_id"]
            album_name = post_body["album_name"]
            release_year = post_body["release_year"]
            # An Artist is a dict of {"artist_id", "artist_name", "country" }
            # Arists is a list of artist [{"artist_id":12, "artist_name":"AA", "country":"XX"},{"arist_id": ...}]
            artists = post_body["artists"]
            # Songs is a list of { "song_id", "song_name", "length", "artist" }
            # Song Id an length are numbers, song_name is a string, artist is a list of artists (above)
            songs = post_body["songs"]
        except KeyError as e:
            raise BadRequest(message="Required attribute is missing")
        if isinstance(songs, list) is False or isinstance(artists, list) is False:
            logging.error("song_ids or artist_ids are not lists")
            raise BadRequest("song_ids or artist_ids are not lists")

        # check if song has artist associated with it
        c = self.conn.cursor()

        # insert album information
        insert_album_info = """INSERT OR IGNORE INTO album_table (album_id, album_name, release_year)
                        VALUES (?, ?, ?)"""
        c.execute(insert_album_info, [album_id, album_name, release_year])

        # check if album has at least one artist
        if artists == None:
            logging.error("album needs to have at least 1 artist")
            raise BadRequest("album needs to have at least 1 artist")

        for artist in artists:
            artist_id = artist["artist_id"]
            insert_artists_info = """INSERT OR IGNORE INTO artist_album_table (artist_id, album_id) VALUES (?, ?)"""
            c.execute(insert_artists_info, [artist_id, album_id])
    
        # check if album has at least one song
        if songs == None:
            logging.error("album needs to have at least 1 song")
            raise BadRequest("album needs to have at least 1 song")

        for song in songs:

            song_id = song["song_id"]
            song_name = song["song_name"]
            song_length = song["length"]

            # raise error if song does not have artist associated
            s_artists = song.get("artists")
            if s_artists == None:
                logging.error("song does not have associated artist")
                raise BadRequest("song does not have associated artist")
            
            for artist in s_artists:
                a_id = artist["artist_id"]
                # insert songs_artist info
                insert_songs_artist_info = """INSERT OR IGNORE INTO song_artist_table (song_id, artist_id) VALUES (?, ?)"""
                c.execute(insert_songs_artist_info, [song_id, a_id])

            # insert songs info
            insert_song_info = """INSERT or IGNORE INTO song_table (song_id, song_name, song_length) VALUES (?, ?, ?)"""
            c.execute(insert_song_info, [song_id, song_name, song_length])
            # insert songs info based on song_id
            insert_songs_album_info = """INSERT INTO song_album_table (song_id, album_id) VALUES (?, ?)"""
            c.execute(insert_songs_album_info, [song_id, album_id])
        
        self.conn.commit()

        return "{\"message\":\"album inserted\"}"

    """
    Returns a song's info
    raise KeyNotFound() if song_id is not found
    """
    def find_song(self, song_id):
        c = self.conn.cursor()
        # Your query should fetch (song_id, name, length, artist_ids, album_ids) based on song_id
        
        # fill up this object type, which I'll return in the end:
        result = {}
        # select the album information
        select_song_info = """SELECT song_id, song_name, song_length
                              FROM song_table
                              WHERE song_id =""" + str(song_id)
        c.execute(select_song_info)
        # write the album info into json format
        res_song_info = to_json(c)
        if len(res_song_info) == 0:
            logging.error("song with song_id is not found")
            raise KeyNotFound(message="song with song_id is not found")
        # select the artist ids
        select_song_artist_info = """SELECT artist_id
                              FROM song_artist_table
                              WHERE song_id =""" + str(song_id) + """ ORDER BY artist_id"""
        c.execute(select_song_artist_info)
        # write the artist ids into json format
        res_artist_ids = to_json(c)
        if len(res_artist_ids) == 0:
            logging.error("no artists associated with song")
            raise KeyNotFound(message="no artists associated with song")
        # convert the list of dictionaries into a list
        list_of_artist_ids = []
        for x in res_artist_ids:
            val = x["artist_id"]
            list_of_artist_ids.append(val)
        
        # select the album ids
        select_song_album_info =  """SELECT album_id, song_id
                              FROM song_album_table
                              WHERE song_id =""" + str(song_id) + """ ORDER BY album_id"""""
        c.execute(select_song_album_info)
        # write the album ids into json format
        res_album_ids = to_json(c)
        # print(res_album_ids)
        if len(res_album_ids) == 0:
            logging.error("no albums associated with song")
            raise KeyNotFound(message="no albums associated with song")
        list_of_album_ids = []
        for x in res_album_ids:
            val = x["album_id"]
            list_of_album_ids.append(val)
        print(list_of_artist_ids)
        print(list_of_album_ids)
        result["song_id"] = res_song_info[0]["song_id"]
        result["song_name"] = res_song_info[0]["song_name"]
        result["length"] = res_song_info[0]["song_length"]
        result["artist_ids"] = list_of_artist_ids
        result["album_ids"] = list_of_album_ids

        self.conn.commit()
        return result


    """
    Returns all an album's songs
    raise KeyNotFound() if album_id not found
    """
    def find_songs_by_album(self, album_id):

        c = self.conn.cursor()
        # Your query should fetch (song_id, name, length, artist id, album id) based on album_id
        # TODO milestone splat
        res = to_json(c)
        self.conn.commit()
        return res

    """
    Returns all an artists' songs
    raise KeyNotFound() if artist_id is not found
    """
    def find_songs_by_artist(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (song_id, name, length, artist id, album id) based on artist_id
        # TODO milestone splat
        res = to_json(c)
        self.conn.commit()
        return res
   
    """
    Returns a album's info
    raise KeyNotFound() if album_id is not found
    """
    def find_album(self, album_id):
        c = self.conn.cursor()
        # Your query should fetch (album_id, album_name, release_year) by album id
        # TODO milestone splat
        res = to_json(c)
        self.conn.commit()
        return res

    """
    Returns a album's info
    raise KeyNotFound() if artist_id is not found 
    if artist exist, but there are no albums then return an empty result (from to_json)
    """
    def find_album_by_artist(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (album_id, album_name, release_year) by artist_id
        # TODO milestone splat
        res = to_json(c)
        self.conn.commit()
        return res

    """
    Returns a artist's info
    raise KeyNotFound() if artist_id is not found 
    """
    def find_artist(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (artist_id, artist_name, country) by artist id
        # TODO milestone splat
        res = to_json(c)
        self.conn.commit()
        return res

    """
    Returns the average length of an artist's songs (artist_id, avg_length)
    raise KeyNotFound() if artist_id is not found 
    """
    def avg_song_length(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (artist_id, avg_length) by artist_id
        # TODO milestone splat
        res = to_json(c)
        self.conn.commit()
        return res


    """
    Returns top (n=num_artists) artists based on total length of songs
    """
    def top_length(self, num_artists):
        c = self.conn.cursor()
        # TODO milestone splat
        res = to_json(c)
        self.conn.commit()
        return res
