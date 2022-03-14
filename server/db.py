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
            artist_name = artist["artist_name"]
            country = artist["country"]
            # insert artists info
            insert_artist_info = """INSERT or IGNORE INTO artist_table
                               (artist_id, artist_name, country)
                               VALUES (?, ?, ?)"""
            c.execute(insert_artist_info, [artist_id, artist_name, country])

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
                insert_songs_artist_info = """INSERT OR IGNORE INTO song_artist_table
                                           (song_id, artist_id)
                                           VALUES (?, ?)"""
                c.execute(insert_songs_artist_info, [song_id, a_id])

            # insert songs info
            insert_song_info = """INSERT or IGNORE INTO song_table
                               (song_id, song_name, song_length)
                               VALUES (?, ?, ?)"""
            c.execute(insert_song_info, [song_id, song_name, song_length])
            # insert songs info based on song_id
            insert_songs_album_info = """INSERT INTO song_album_table
                                      (song_id, album_id)
                                      VALUES (?, ?)"""
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
        # select the song information
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
                              WHERE song_id =""" + str(song_id) + """
                              ORDER BY artist_id"""
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
                              WHERE song_id =""" + str(song_id) + """
                              ORDER BY album_id"""""
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
        # Your query should fetch (song_id, name, length, artist ids) based on album_id

        # select song_ids associated with given album id
        select_song_ids_for_album_id = """SELECT song_id
                              FROM song_album_table
                              WHERE album_id =""" + str(album_id)
        
        c.execute(select_song_ids_for_album_id)
        res_song_ids = to_json(c)

        if len(res_song_ids) == 0:
            logging.error("no songs associated with album")
            raise KeyNotFound(message="no songs associated with album")
        
        song_ids = []
        for song_id in res_song_ids:
            val = song_id["song_id"]
            song_ids.append(val)

        # extract song_name and length for given song_ids
        
        result_list = []
        for s_id in song_ids:
            result = {}
            select_song_name = """SELECT song_name
                              FROM song_table
                              WHERE song_id =""" + str(s_id)
            c.execute(select_song_name)
            res_song_names = to_json(c)
            print(res_song_names)
            select_song_length = """SELECT song_length
                              FROM song_table
                              WHERE song_id =""" + str(s_id)
            c.execute(select_song_length)
            res_song_lengths = to_json(c)
            print(res_song_lengths)
            # extract the artist ids associated w this song id
            select_artist_ids = """SELECT artist_id
                              FROM song_artist_table
                              WHERE song_id =""" + str(s_id) + """
                              ORDER BY artist_id"""
            c.execute(select_artist_ids)
            res_artist_ids = to_json(c)
            # push the artist_ids into a list
            artist_ids = []
            for a_id in res_artist_ids:
                val = a_id["artist_id"]
                artist_ids.append(val)

            result["song_id"] = int(s_id)
            result["song_name"] = res_song_names[0]["song_name"]
            result["length"] = res_song_lengths[0]["song_length"]
            result["artist_ids"] = artist_ids
            print(result)
            result_list.append(result)
            
        self.conn.commit()

        return result_list

    """
    Returns all an artists' songs
    raise KeyNotFound() if artist_id is not found
    """
    def find_songs_by_artist(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (song_id, name, length, artist id) based on artist_id
 
        # select song_ids associated with given artist id
        select_song_ids_for_artist_id = """SELECT song_id
                              FROM song_artist_table
                              WHERE artist_id =""" + str(artist_id)+ """
                              ORDER BY song_id"""
        c.execute(select_song_ids_for_artist_id)
        res_song_ids = to_json(c)

        if len(res_song_ids) == 0:
            logging.error("no songs associated with artist")
            raise KeyNotFound(message="no songs associated with artist")

        song_ids = []
        for song_id in res_song_ids:
            val = song_id["song_id"]
            song_ids.append(val)

        # extract song_name and length for given song_ids
        
        result_list = []
        for s_id in song_ids:
            result = {}
            select_song_name = """SELECT song_name
                              FROM song_table
                              WHERE song_id =""" + str(s_id)
            c.execute(select_song_name)
            res_song_names = to_json(c)
         
            select_song_length = """SELECT song_length
                              FROM song_table
                              WHERE song_id =""" + str(s_id)
            c.execute(select_song_length)
            res_song_lengths = to_json(c)
           
            # extract the artist ids associated w this song id
            select_artist_ids = """SELECT artist_id
                              FROM song_artist_table
                              WHERE song_id =""" + str(s_id)
            c.execute(select_artist_ids)
            res_artist_ids = to_json(c)
            # push the artist_ids into a list
            artist_ids = []
            for a_id in res_artist_ids:
                val = a_id["artist_id"]
                artist_ids.append(val)

            result["song_id"] = int(s_id)
            result["song_name"] = res_song_names[0]["song_name"]
            result["length"] = res_song_lengths[0]["song_length"]
            result["artist_ids"] = artist_ids
           
            result_list.append(result)
        
        self.conn.commit()
        return result_list
   
    """
    Returns a album's info
    raise KeyNotFound() if album_id is not found
    """
    def find_album(self, album_id):
        c = self.conn.cursor()
        # Your query should fetch (album_id, album_name, release_year) by album id
        # TODO milestone splat
        select_album_info = """SELECT album_id, album_name, release_year
                            FROM album_table
                            WHERE album_id =""" + str(album_id)
        c.execute(select_album_info)
        res_album_info = to_json(c)

        # extract the artist_ids associated with the album_id
        select_artist_ids_for_album_id = """SELECT artist_id
                              FROM artist_album_table
                              WHERE album_id =""" + str(album_id)+ """
                              ORDER BY artist_id"""
        c.execute(select_artist_ids_for_album_id)
        res_artist_ids = to_json(c)

        # push artist ids into a list
        artist_ids = []
        for a_id in res_artist_ids:
            val = a_id["artist_id"]
            artist_ids.append(val)

        # extract the song_ids associated with the album_id
        select_song_ids_for_album_id = """SELECT song_id
                              FROM song_album_table
                              WHERE album_id =""" + str(album_id)
        c.execute(select_song_ids_for_album_id)
        res_song_ids = to_json(c)

        # push song ids into a list
        song_ids = []
        for s_id in res_song_ids:
            val = s_id["song_id"]
            song_ids.append(val)

        result = {}
        result["album_id"] = res_album_info[0]["album_id"]
        result["album_name"] = res_album_info[0]["album_name"]
        result["release_year"] = res_album_info[0]["release_year"]
        result["artist_ids"] = artist_ids
        result["song_ids"] = song_ids

        self.conn.commit()
        return result

    """
    Returns a album's info
    raise KeyNotFound() if artist_id is not found 
    if artist exist, but there are no albums then return an empty result (from to_json)
    """
    def find_album_by_artist(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (album_id, album_name, release_year) by artist_id
    
        # select album_ids associated with given artist_id
        select_album_ids_for_artist_id = """SELECT album_id
                              FROM artist_album_table
                              WHERE artist_id =""" + str(artist_id)

        c.execute(select_album_ids_for_artist_id)
        res_album_ids = to_json(c)

        if len(res_album_ids) == 0:
            return res_album_ids

        album_ids = []
        for album_id in res_album_ids:
            val = album_id["album_id"]
            album_ids.append(val)

        # extract album_name and release year for given album_ids
        result_list = []
        for alb_id in album_ids:
            result = {}
            select_album_name = """SELECT album_name
                              FROM album_table
                              WHERE album_id =""" + str(alb_id)
            c.execute(select_album_name)
            res_alb_names = to_json(c)
         
            select_alb_release_year = """SELECT release_year
                              FROM album_table
                              WHERE album_id =""" + str(alb_id)
            c.execute(select_alb_release_year)
            res_alb_release_years = to_json(c)

            result["album_id"] = int(alb_id)
            result["album_name"] = res_alb_names[0]["album_name"]
            result["release_year"] = res_alb_release_years[0]["release_year"]
           
            result_list.append(result)

        self.conn.commit()
        return result_list

    """
    Returns a artist's info
    raise KeyNotFound() if artist_id is not found 
    """
    def find_artist(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (artist_id, artist_name, country) by artist id

        # extract artist info given artist_id
        select_artist_info = """SELECT * 
                                FROM artist_table
                                WHERE artist_id =""" + str(artist_id)

        c.execute(select_artist_info)

        if c.rowcount == 0:
            raise KeyNotFound()
        
        result = to_json(c)
        self.conn.commit()
        return result

    """
    Returns the average length of an artist's songs (artist_id, avg_length)
    raise KeyNotFound() if artist_id is not found 
    """
    def avg_song_length(self, artist_id):
        c = self.conn.cursor()
        # Your query should fetch (artist_id, avg_length) by artist_id

        # avg song length = add lengths of all songs , divide by # of songs (len(song_ids))
        
        # select album_ids associated with given artist_id
        select_artist_id = """SELECT artist_id
                              FROM song_artist_table
                              WHERE artist_id =""" + str(artist_id)

        c.execute(select_artist_id)
        res_artist_id = to_json(c)

        if len(res_artist_id) == 0:
            logging.error("artist_id is not found")
            raise KeyNotFound(message="artist_id is not found")
        
        # extract all the song_ids and corresponding lengths associated with artist_id
        select_song_ids = """SELECT song_id
                              FROM song_artist_table
                              WHERE artist_id =""" + str(artist_id)

        c.execute(select_song_ids)
        res_song_ids = to_json(c)

        if len(res_song_ids) == 0:
            logging.error("artist has no songs")
            raise KeyNotFound(message="artist has no songs")

        # push song ids into a list
        song_ids = []
        for s_id in res_song_ids:
            val = s_id["song_id"]
            song_ids.append(val)
        
        song_length_sum = 0
        # extract the length of each song and add to song_length_sum
        for sid in song_ids:
            select_song_len = """SELECT song_length
                              FROM song_table
                              WHERE song_id =""" + str(sid)
            c.execute(select_song_len)
            res_song_len = to_json(c)
            song_length_sum += res_song_len[0]["song_length"]

        # calculate ave song length
        avg_song_length = song_length_sum/len(song_ids)

        result = {}
        result["artist_id"] = int(artist_id)
        result["avg_length"] = round(avg_song_length, 1)

        self.conn.commit()
        return result


    """
    Returns top (n=num_artists) artists based on total length of songs
    """
    def top_length(self, num_artists):
        c = self.conn.cursor()

        select_top_len = """SELECT artist_id, SUM(song_length) as total_length
                              FROM artist_table
                              NATURAL JOIN song_artist_table
                              NATURAL JOIN song_table
                              GROUP BY artist_id
                              ORDER BY total_length DESC, artist_name ASC
                              LIMIT """ + str(num_artists)
        
        c.execute(select_top_len)
        
        res = to_json(c)
        self.conn.commit()
        return res
