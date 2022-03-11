drop table if exists album_table;
drop table if exists artist_table;
drop table if exists song_table;

create table song_table (
    field1 INTEGER PRIMARY KEY,
    field2 VARCHAR(255),
    field3 INTEGER
);

create table artist_table (
    field1 INTEGER PRIMARY KEY,
    field2 VARCHAR(255),
    field3 VARCHAR(255)
);

create table album_table (
    field1 INTEGER PRIMARY KEY,
    field2 VARCHAR(255),
    field3 INTEGER
);

-- some sample records
-- insert into test_table values ('abcde', 10), ('adkhe',12), ('badae', 3);