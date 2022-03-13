drop table if exists song_artist_table;
drop table if exists song_album_table;
drop table if exists artist_album_table;
drop table if exists album_table;
drop table if exists artist_table;
drop table if exists song_table;


create table song_table (
    song_id INTEGER PRIMARY KEY,
    song_name VARCHAR(255),
    song_length INTEGER
);

create table artist_table (
    artist_id INTEGER PRIMARY KEY,
    artist_name VARCHAR(255) NOT NULL,
    country VARCHAR(255)
);

create table album_table (
    album_id INTEGER PRIMARY KEY,
    album_name VARCHAR(255) NOT NULL,
    release_year INTEGER CHECK(release_year > 1900)
);

create table artist_album_table (
    artist_id INTEGER NOT NULL,
    album_id INTEGER NOT NULL,
    FOREIGN KEY(artist_id) REFERENCES album_table(album_id),
    FOREIGN KEY(album_id) REFERENCES artist_table(artist_id),
    UNIQUE(artist_id, album_id)
);

create table song_album_table (
    song_id INTEGER NOT NULL,
    album_id INTEGER NOT NULL,
    FOREIGN KEY(song_id) REFERENCES album_table(album_id),
    FOREIGN KEY(album_id) REFERENCES song_table(song_id),
    UNIQUE(song_id, album_id)
);

create table song_artist_table (
    song_id INTEGER NOT NULL,
    artist_id INTEGER NOT NULL,
    FOREIGN KEY(song_id) REFERENCES artist_table(artist_id),
    FOREIGN KEY(artist_id) REFERENCES song_table(song_id),
    UNIQUE(song_id, artist_id)
);