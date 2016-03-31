# coding=UTF-8
import argparse
import codecs
import hashlib
import math
import os
import re
import sqlite3
import stat
import sys
import time
import pickle

import six
from binaryornot.check import is_binary
from chardet.universaldetector import UniversalDetector
from termcolor import colored

logo = """

   ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄        ▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄
  ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░▌      ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌
  ▐░█▀▀▀▀▀▀▀▀▀  ▀▀▀▀█░█▀▀▀▀ ▐░▌░▌     ▐░▌ ▀▀▀▀▀█░█▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌
  ▐░▌               ▐░▌     ▐░▌▐░▌    ▐░▌      ▐░▌    ▐░▌       ▐░▌
  ▐░█▄▄▄▄▄▄▄▄▄      ▐░▌     ▐░▌ ▐░▌   ▐░▌      ▐░▌    ▐░█▄▄▄▄▄▄▄█░▌
  ▐░░░░░░░░░░░▌     ▐░▌     ▐░▌  ▐░▌  ▐░▌      ▐░▌    ▐░░░░░░░░░░░▌
  ▐░█▀▀▀▀▀▀▀▀▀      ▐░▌     ▐░▌   ▐░▌ ▐░▌      ▐░▌    ▐░█▀▀▀▀▀▀▀█░▌
  ▐░▌               ▐░▌     ▐░▌    ▐░▌▐░▌      ▐░▌    ▐░▌       ▐░▌
  ▐░▌           ▄▄▄▄█░█▄▄▄▄ ▐░▌     ▐░▐░▌ ▄▄▄▄▄█░▌    ▐░▌       ▐░▌
  ▐░▌     /)   ▐░░░░░░░░░░░▌▐░▌      ▐░░▌▐░░░░░░░▌    ▐░▌       ▐░▌
   ▀     //     ▀▀▀▀▀▀▀▀▀▀▀  ▀        ▀▀  ▀▀▀▀▀▀▀      ▀         ▀
.-------| |--------------------------------------------.__
|WMWMWMW| |>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>:>
`-------| |--------------------------------------------'^^
         \\
          \)
"""

_database_version = 4

# If the user pipes we write our internal encoding which is UTF-8
# This is one of the great things about Python 3, no more hacky hacky
if six.PY2:
    if not sys.stdout.isatty():
        writer = codecs.getwriter("UTF-8")
        sys.stdout = writer(sys.stdout)

_pgrs_last_pos   = 1289  # Only evil prime number work
_pgrs_last_time  = 0
_pgrs_rotation   = [
    [
        "   ",
        ".  ",
        ".. ",
        "...",
        "..o",
        "..O",
        "..O",
        "..O",
        "..O",
        "..o",
        "...",
        ".. ",
        ".  ",
        "   ",
    ],
    ["(``)", "(  )", "('')"]
]
_pgrs_mod1 = len(_pgrs_rotation[0])
_pgrs_mod2 = 71  # only supersingular primes work

_positive_word_match = re.compile("\w+")

_whitespace_split = " \t\n\r"
_semantic_split = "\~\^$&#%=,:;!\?\+\"'\`\´*/\\\(\)<>{}\[\]\|"
_interpunct_split = "··᛫•‧∘∙⋅●◦⦁⸰・･𐂧ּ⸱"

_positive_regex = [
    _positive_word_match,
]

_split_regex = []

_cache_size = 1024 * 1024

_db_cache = None

_do_second_pass = False

_ignore_dir = set([
    "__pycache__",
    "__MACOSX",
])

# Very common binary files and annoying text-files like svg

_ignore_ext = set([
    "log",
    "svg",
    "hex",
    "ihex",
    "vmdk",
    "vdi",
    "pyc",
    "ai",
    "ps",
    "pdf",
    "png",
    "bmp",
    "gif",
    "tif",
    "tiff",
    "jpg",
    "jpeg",
    "ico",
    "avi",
    "mpg",
    "mpeg",
    "mp3",
    "wav",
    "aiff",
    "mp4",
    "m4a",
    "m4v",
    "zip",
    "gz",
    "tar",
    "rar",
    "mov",
    "ogg",
    "ogv",
    "raw",
    "tiff",
    "pdf",
    "jar",
    "so",
    "ko",
    "o",
    "bin",
])

_args = None

_index_count = 0

_cwd = os.getcwd()

_finja_path = None

# Regex


def prepare_regex(interpunct=False):
    global _split_regex
    interpunct_split = ""
    if interpunct:
        interpunct_split = _interpunct_split
    _split_regex = []
    _split_regex.append(re.compile("[%s]" % _whitespace_split))
    _split_regex.append(re.compile("[.\_\-%s%s%s]" % (
        _semantic_split,
        _whitespace_split,
        interpunct_split
    )))
    _split_regex.append(re.compile("[.\-%s%s%s]" % (
        _semantic_split,
        _whitespace_split,
        interpunct_split
    )))
    _split_regex.append(re.compile("[.\_%s%s%s]" % (
        _semantic_split,
        _whitespace_split,
        interpunct_split
    )))
    _split_regex.append(re.compile("[%s%s%s]" % (
        _semantic_split,
        _whitespace_split,
        interpunct_split
    )))

# Database Keys


class DatabaseKey(object):
    INTERPUNCT = 0
    MAX_ID     = 1
    VERSION    = 2


def cleanup(string):
    string = string.strip()
    if len(string) < 2:
        return None
    if len(string) <= 16:
        return string.lower()
    key = hashlib.md5(string.lower().encode("UTF-8")).digest()
    if six.PY2:
        return sqlite3.Binary(key)
    else:
        return key


def md5(fname):
    hash = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hash.update(chunk)
    if six.PY2:
        return sqlite3.Binary(hash.digest())
    else:
        return hash.digest()


# Progress

def progress(flush=True):
    """Write progress to stdout if needed"""
    global _pgrs_last_pos
    global _pgrs_last_time
    if _args.raw:
        return
    now = time.time()
    if (now - _pgrs_last_time) < 0.16:  # noqa
        return
    _pgrs_last_time = now  # noqa
    _pgrs_last_pos += 1  # noqa
    pos1 = _pgrs_last_pos % _pgrs_mod1
    pos2 = min(_pgrs_last_pos % _pgrs_mod2, 2)
    sys.stdout.write(" %s%s" % (
        _pgrs_rotation[1][pos2],
        _pgrs_rotation[0][pos1]
    ))
    sys.stdout.write("\b\b\b\b\b\b\b\b")
    if flush:  # pragma: no cover
        sys.stdout.flush()


# SQL Queries

_string_to_token = """
    SELECT
        id
    FROM
        token
    WHERE
        string = ?;
"""

_insert_token = """
    INSERT INTO
        token(id, string)
    VALUES
        (?, ?);
"""

_token_cardinality = """
    SELECT
        COUNT(id) count
    FROM
        finja
    WHERE
        token_id = ?
"""

_search_query = """
    SELECT DISTINCT
        {projection}
    FROM
        finja as i
    JOIN
        file as f
    ON
        i.file_id = f.id
    {finja_joins}
    WHERE
        i.token_id=?
    {terms}
    {ignore}
    {file_mode_hint}
"""

_clear_found_files = """
    UPDATE
        file
    SET found = 0
"""

_clear_inodes = """
    UPDATE
        file
    SET inode_mod = null
"""

_delete_missing_indexes = """
    DELETE FROM
        finja
    WHERE
        file_id IN (
            SELECT
                id
            FROM
                file
            WHERE
                found = 0
        )
"""

_find_missing_files = """
    SELECT
        count(*)
    FROM
        file
    WHERE
        found = 0;
"""

_delete_missing_files = """
    DELETE FROM
        file
    WHERE
        id IN (
            SELECT
                f.id
            FROM
                file as f
            JOIN
                file as ff
            ON
                f.md5 = ff.md5
            WHERE
                ff.found = 0
        )
"""

_delete_free_tokens = """
    DELETE FROM
        token
    WHERE
        id IN (
            SELECT
                t.id
            FROM
                token as t
            LEFT JOIN
                finja as f
            ON
                t.id = f.token_id
            WHERE
                f.token_id is null
        )
"""

_find_file = """
    SELECT
        id,
        inode_mod,
        md5
    FROM
        file
    WHERE
        path=?;
"""

_check_for_duplicates = """
    SELECT
        count(*)
    FROM
        file
    WHERE
        md5=?;
"""

_clear_inode_md5_of_duplicates = """
    UPDATE
        file
    SET
        inode_mod = null,
        md5 = null
    WHERE
        md5=?;
"""

_create_new_file_entry = """
    INSERT INTO
        file(path, md5, inode_mod, found)
    VALUES
        (?, ?, ?, 1);
"""

_update_file_entry = """
    UPDATE
        file
    SET
        md5 = ?,
        inode_mod = ?,
        found = 1
    WHERE
        id = ?
"""

_clear_existing_index = """
    DELETE FROM
        finja
    WHERE
        file_id=?;
"""

_insert_index = """
    INSERT INTO
        finja(token_id, file_id, line)
    VALUES
        (?, ?, ?);
"""

_update_file_info = """
    UPDATE
        file
    SET
        found = 1,
        encoding = ?
    WHERE
        path = ?
"""

_mark_found = """
    UPDATE
        file
    SET
        found = 1
    WHERE
        path = ?
"""

_find_duplicates = """
    SELECT
        f.path
    FROM
        file as f
    JOIN
        file as ff
    ON
        ff.md5 = f.md5
    WHERE
        ff.id = ?
        AND
        f.id != ?
"""

_set_key = """
    INSERT OR REPLACE INTO
        key_value(key, value)
    VALUES(?, ?)
"""

_get_key = """
    SELECT
        value
    FROM
        key_value
    WHERE
        key = ?
"""

# Cache classes


class TokenDict(dict):
    def __init__(self, db, *args, **kwargs):
        super(TokenDict, self).__init__(*args, **kwargs)
        self.db = db
        self.token_id = 41
        self.bulk_insert = []
        res = get_key(DatabaseKey.MAX_ID, con=self.db)
        if res:
            self.token_id = res

    def __missing__(self, key):
        with self.db:
            cur = self.db.cursor()
            res = cur.execute(_string_to_token, (key,)).fetchall()
            if res:
                ret = res[0][0]
            else:
                self.token_id += 1
                ret = self.token_id
                self.bulk_insert.append((ret, key))
        self[key] = ret
        return ret

    def commit(self):
        if self.token_id >= 2 ** 63 - 1:
            ValueError("Out of token-space. Delete the database and reindex")
        bulk_insert = self.bulk_insert
        new = len(bulk_insert)
        self.db.executemany(_insert_token, bulk_insert)
        self.bulk_insert = []
        set_key(DatabaseKey.MAX_ID, self.token_id, con=self.db)
        return new

# DB functions


def set_key(key, value, con=None):
    bin_value = pickle.dumps(value)
    if six.PY2:
        bin_value = sqlite3.Binary(bin_value)
    if not con:
        con = get_db()[0]
    with con:
        con.execute(_set_key, (key, bin_value))


def get_key(key, con=None):
    if not con:
        con = get_db()[0]
    with con:
        res = con.execute(_get_key, (key,)).fetchall()
        if res:
            return pickle.loads(res[0][0])
        return None


def get_db(create=False):
    global _db_cache
    if _db_cache:
        return _db_cache  # noqa
    exists = os.path.exists("FINJA")
    if not (create or exists):
        raise ValueError("Could not find FINJA")
    connection = sqlite3.connect("FINJA")  # noqa
    connection.execute('PRAGMA encoding = "UTF-8";')
    if not exists:
        # We use inline queries here
        connection.execute("""
            CREATE TABLE
                finja(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id INTEGER,
                    file_id INTEGER,
                    line INTEGER
                );
        """)
        connection.execute("""
            CREATE INDEX finja_token_id_idx ON finja (token_id);
        """)
        connection.execute("""
            CREATE INDEX finja_file_idx ON finja (file_id);
        """)
        connection.execute("""
            CREATE INDEX finja_file_line_idx ON finja (file_id, line);
        """)
        connection.execute("""
            CREATE TABLE
                token(
                    string TEXT UNIQUE PRIMARY KEY,
                    id INTEGER
                );
        """)
        connection.execute("""
            CREATE TABLE
                file(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT,
                    md5 BLOB,
                    inode_mod INTEGER,
                    found INTEGER DEFAULT 1,
                    encoding TEXT
                );
        """)
        connection.execute("""
            CREATE INDEX file_md5_idx ON file (md5);
        """)
        connection.execute("""
            CREATE INDEX file_path_idx ON file (path);
        """)
        connection.execute("""
            CREATE INDEX file_found_idx ON file (found);
        """)
        connection.execute("""
            CREATE TABLE
                key_value(
                    key INTEGER PRIMARY KEY,
                    value BLOB
                );
        """)
        connection.execute("""
            CREATE INDEX key_value_key_idx ON key_value (key);
        """)
        set_key(DatabaseKey.INTERPUNCT, _args.interpunct, connection)
        set_key(DatabaseKey.VERSION, _database_version, connection)
    connection.commit()
    version = get_key(DatabaseKey.VERSION, connection)
    if version != _database_version:
        raise ValueError("Database version not correct. Please reindex")
    _db_cache = (
        connection,
        TokenDict(connection),
    )
    return _db_cache


def gen_search_query(pignore, file_mode, terms=1):
    if file_mode:
        projection = """
            f.path,
            f.id
        """
    else:
        projection = """
            f.path,
            f.id,
            i.line,
            f.encoding
        """
    join_list = []
    term_list = []
    if file_mode:
        file_mode_hint = "AND i.line = -1"
        for x in range(terms - 1):
            join_list.append("""
                JOIN
                    finja as i{0}
                ON
                    i.file_id == i{0}.file_id
                    AND
                    i.line = -1
                    AND
                    i{0}.line = -1
            """.format(x))
    else:
        file_mode_hint = "AND i.line != -1"
        for x in range(terms - 1):
            join_list.append("""
                JOIN
                    finja as i{0}
                ON
                    i.file_id == i{0}.file_id
                    AND
                    i.line == i{0}.line
                    AND
                    i.line != -1
                    AND
                    i{0}.line != -1
            """.format(x))
    for x in range(terms - 1):
        term_list.append("AND i{0}.token_id = ?".format(x))
    ignore_list = []
    filter_ = "AND f.path NOT LIKE ?"
    for ignore in pignore:
        ignore_list.append(filter_)
    return _search_query.format(
        projection = projection,
        ignore = "\n".join(ignore_list),
        finja_joins = "\n".join(join_list),
        terms = "\n".join(term_list),
        file_mode_hint = file_mode_hint
    )

# OS access


def get_line(file_path, lineno, file_):
    line = "!! Bad encoding "
    try:
        if file_:
            file_.seek(0)
            for _ in range(lineno):
                line = file_.readline()
        else:
            with codecs.open(file_path, "r", encoding="UTF-8") as f:
                for _ in range(lineno):
                    line = f.readline()
    except UnicodeDecodeError:
        pass
    except (IOError, OSError):
        line = "!! File not found "
    return line


def find_finja():
    global _finja_path
    cwd = os.path.abspath(".")
    lcwd = cwd.split(os.sep)
    while lcwd:
        cwd = os.sep.join(lcwd)
        check = os.path.join(cwd, "FINJA")
        if os.path.isfile(check):
            _finja_path = cwd  # noqa
            return cwd
        lcwd.pop()
    raise ValueError("Could not find FINJA")

# Indexing drivers


def index():
    db = get_db(create=True)
    do_index(db)
    print("Indexing done")


def do_index(db, update=False):
    # Reindexing duplicates that have changed is a two pass process
    global _do_second_pass
    con = db[0]
    if _args.clear_inodes:
        con.execute(_clear_inodes)
    interpunct = get_key(DatabaseKey.INTERPUNCT, con)
    prepare_regex(interpunct)
    _do_second_pass = False
    do_index_pass(db, update)
    if _do_second_pass:
        if not update:
            print("Second pass")
        do_index_pass(db, True)


def is_dotfile(path):
    """
    Return true if any path component of the given path starts with a dot.

    Note that single-dot paths ("./") do not count as such.

    >>> is_dotfile('./foo/bar/baz')
    False
    >>> is_dotfile('./foo/.bar/baz')
    True

    """
    return any([
        p.startswith('.')
        for p
        in path.split(os.sep)
        if p not in ('..', '.')
    ])


def do_index_pass(db, update=False):
    global _do_second_pass
    con = db[0]
    if not _args.batch > 0:
        with con:
            con.execute(_clear_found_files)
    if os.path.exists("FINJA.lst"):
        with codecs.open("FINJA.lst", "r", encoding="UTF-8") as f:
            for path in f.readlines():
                file_path = os.path.relpath(path.strip())
                index_file(db, file_path, update)
    else:
        for dirpath, _, filenames in os.walk("."):
            if is_dotfile(dirpath):
                # Skip "hidden" dirs
                continue

            if set(dirpath.split(os.sep)).intersection(_ignore_dir):
                continue
            for filename in filenames:
                if is_dotfile(filename) or filename in ('FINJA', 'FINJA.lst'):
                    # Skip "hidden" and index files
                    continue
                ext  = None
                ext2 = None
                if '.' in filename:
                    split = filename.split(os.path.extsep)
                    ext = split[-1].lower()
                    if len(split) > 2:
                        ext2 = split[-2].lower()
                        if len(ext2) > 4:
                            ext2 = None
                if ext not in _ignore_ext and ext2 not in _ignore_ext:
                    file_path = os.path.relpath(os.path.join(
                        dirpath,
                        filename
                    ))
                    index_file(db, file_path, update)
    with con:
        res = con.execute(_find_missing_files).fetchall()
        if res[0][0] > 0:
            con.execute(_delete_missing_indexes)
            con.execute(_delete_missing_files)
            _do_second_pass = True  # noqa

# Indexer


def index_file(db, file_path, update = False):
    global _index_count
    if six.PY2:
        if not isinstance(file_path, unicode):
            file_path = unicode(file_path, encoding="UTF-8")
    con        = db[0]
    # Bad symlinks etc.
    try:
        stat_res = os.stat(file_path)
    except OSError:
        if not update:
            print("%s: not found, skipping" % (file_path,))
        return
    if not stat.S_ISREG(stat_res[stat.ST_MODE]):
        if not update:
            print("%s: not a plain file, skipping" % (file_path,))
        return
    inode_mod     = (stat_res[stat.ST_INO] * stat_res[stat.ST_MTIME]) % 2 ** 62
    old_inode_mod = None
    old_md5       = None
    file_         = None
    with con:
        res = con.execute(_find_file, (file_path,)).fetchall()
        if res:
            file_         = res[0][0]
            old_inode_mod = res[0][1]
            old_md5       = res[0][2]
    if old_inode_mod != inode_mod:
        do_index, file_ = check_file(
            con, file_, file_path, inode_mod, old_md5, update
        )
        if not do_index:
            return
        encoding = read_index(db, file_, file_path, update)
        con.execute(_update_file_info, (encoding, file_path))
    else:
        if not update:
            print("%s: uptodate" % (file_path,))
        with con:
            con.execute(_mark_found, (file_path,))


def check_file(con, file_, file_path, inode_mod, old_md5, update=False):
    global _do_second_pass
    md5sum = md5(file_path)
    with con:
        # We assume duplicated
        duplicated = True
        if old_md5:
            res = con.execute(_check_for_duplicates, (old_md5,)).fetchall()
            had_duplicates = res[0][0] > 1
            if had_duplicates and old_md5 != md5sum:
                _do_second_pass = True  # noqa
                con.execute(_clear_inode_md5_of_duplicates, (old_md5,))
                # We know for sure not duplicated
                duplicated = False
        # This was the assumption, we have to check
        if duplicated:
            res = con.execute(_check_for_duplicates, (md5sum,)).fetchall()
            duplicated = res[0][0] > 0
        if file_ is None:
            cur = con.cursor()
            cur.execute(
                _create_new_file_entry, (file_path, md5sum, inode_mod)
            )
            file_ = cur.lastrowid
        else:
            con.execute(_update_file_entry, (md5sum, inode_mod, file_))
        if duplicated:
            if not update:
                if md5sum == old_md5:
                    print("%s: not changed, skipping" % (file_path,))
                else:
                    print("%s: duplicated, skipping" % (file_path,))
            return (False, file_)
    return (old_md5 != md5sum, file_)


def read_index(db, file_, file_path, update = False):
    global _index_count
    con          = db[0]
    token_dict   = db[1]
    encoding     = "UTF-8"
    if is_binary(file_path):
        if not update:
            print("%s: is binary, skipping" % (file_path,))
    else:
        if _args.batch > 0:
            _index_count += 1  # noqa
            if _index_count > _args.batch:
                con.close()
                sys.exit(0)
        try:
            inserts      = set()
            insert_count = parse_file(db, file_, file_path, inserts, encoding)
        except UnicodeDecodeError as e:
            try:
                with open(file_path, "rb") as f:
                    detector = UniversalDetector()
                    for line in f.readlines():
                        detector.feed(line)
                        if detector.done:
                            break
                    detector.close()
                    encoding = detector.result['encoding']
                if not encoding:
                    raise e
                inserts      = set()
                insert_count = parse_file(
                    db, file_, file_path, inserts, encoding
                )
            except UnicodeDecodeError:
                print("%s: decoding failed %s" % (
                    file_path,
                    encoding
                ))
                inserts.clear()
                return encoding
        tokens = set([x[0] for x in inserts])
        for token in tokens:
            inserts.add((token, file_, -1))
        with con:
            new = token_dict.commit()
            con.execute(_clear_existing_index, (file_,))
            con.executemany(_insert_index, inserts)
        unique_inserts = len(inserts)
        print("%s: indexed %s/%s (%.3f) new: %s %s" % (
            file_path,
            unique_inserts,
            insert_count,
            float(unique_inserts) / (insert_count + 0.0000000001),
            new,
            encoding
        ))
        clear_cache(db)
    return encoding


def regex_parser_postive(f, file_, regex, db, inserts, insert_count):
    token_dict   = db[1]
    lineno = 1
    for line in f.readlines():
        for match in regex.finditer(line):
            word = cleanup(match.group(0))
            if word:
                insert_count += 1
                inserts.add((
                    token_dict[word],
                    file_,
                    lineno,
                ))
        lineno += 1
    return insert_count


def regex_parser_split(f, file_, regex, db, inserts, insert_count):
    token_dict   = db[1]
    lineno = 1
    for line in f.readlines():
        tokens = re.split(regex, line)
        for token in tokens:
            word = cleanup(token)
            if word:
                insert_count += 1
                inserts.add((
                    token_dict[word],
                    file_,
                    lineno,
                ))
        lineno += 1
    return insert_count


def parse_file(db, file_, file_path, inserts, encoding="UTF-8"):
    insert_count = 0
    with codecs.open(file_path, "r", encoding=encoding) as f:
        for positive_match in _positive_regex:
            insert_count = regex_parser_postive(
                f, file_, positive_match, db, inserts, insert_count
            )
            f.seek(0)
        for split in _split_regex:
            insert_count = regex_parser_split(
                f, file_, split, db, inserts, insert_count
            )
            f.seek(0)
    return insert_count


def clear_cache(db):
    # clear cache
    db = list(db)[1:]
    size = 0
    for cache_dict in db:
        size += len(cache_dict)
    if size > _cache_size:
        print("Clear cache")
        for cache_dict in db:
            cache_dict.clear()

# Search


def search_term_cardinality(term_id):
    db         = get_db(create = False)
    con        = db[0]

    curs = con.cursor()
    res = curs.execute(_token_cardinality, [term_id]).fetchall()
    return res[0][0]


def order_search_terms(search):
    res = sorted(search, key=search_term_cardinality)
    return res


def search(
        search,
        pignore,
        file_mode=False,
        update=False,
):
    finja = find_finja()
    os.chdir(finja)
    db              = get_db(create = False)
    con             = db[0]
    token_dict      = db[1]
    if update:
        do_index(db, update=True)
    if _args.vacuum:
        con.set_progress_handler(progress, 100000)
        con.execute(_delete_free_tokens)
        con.execute("VACUUM;")
        con.set_progress_handler(None, 100000)
    if not search:
        return
    res = []
    with con:
        pignore = ["%{}%".format(x) for x in pignore]
        query = gen_search_query(pignore, file_mode, len(search))
        search_tokens = order_search_terms([
            token_dict[cleanup(x)] for x in search
        ])
        args = []
        args.extend(search_tokens)
        args.extend(pignore)
        con.set_progress_handler(progress, 1000000)
        res = con.execute(query, args).fetchall()
        con.set_progress_handler(None, 1000000)
        if not _args.raw:
            sys.stdout.write("\b\b\b\b\b\b\b\b")
    if file_mode:
        for match in sorted(
                res,
                key=lambda x: x[0],
        ):
            print(os.path.relpath(match[0], _cwd))
            if not _args.raw:
                display_duplicates(db, match[1])
    else:
        sort_format_result(db, res, search)


def sort_format_result(db, res_set, search):
    dirname = None
    old_file = -1
    for match in sorted(
            res_set,
            key=lambda x: (x[0], x[2]),
    ):
        file_ = match[1]
        if file_ != old_file and old_file != -1:
            display_duplicates(db, old_file)
        old_file = file_
        path = match[0]
        encoding = match[3]
        try:
            with codecs.open(path, "r", encoding=encoding) as f:
                if not _args.raw:
                    new_dirname = os.path.dirname(path)
                    if not new_dirname:
                        new_dirname = "."
                    if dirname != new_dirname:
                        dirname = new_dirname
                        print("%s:" % (
                            colored(os.path.relpath(dirname, _cwd), "yellow")
                        ))
                    file_name = os.path.basename(path)
                else:
                    file_name = path
                context = _args.context
                if context == 1 or _args.raw:
                    display_no_context(f, match, path, file_name, search)
                else:
                    display_context(f, context, match, path, file_name)
        except (OSError, IOError):
            if _args.raw:
                print("%s\0%5d\0%s" % (
                    os.path.abspath(path),
                    match[2],
                    "!! File not found "
                ))
            else:
                print("%s:%5d:%s" % (
                    os.path.relpath(path, _cwd),
                    match[2],
                    "!! File not found "
                ))
    display_duplicates(db, old_file)


def display_context(f, context, match, path, file_name):
    offset = int(math.floor(context / 2))
    context_list = []
    for x in range(context):
        x -= offset
        context_list.append(
            get_line(path, match[2] + x, f)
        )
    strip_list = []
    inside = False
    # Cleaning emtpy lines
    for line in reversed(context_list):
        if line.strip() or inside:
            inside = True
            strip_list.append(line)
    context_list = []
    inside = False
    # Cleaning emtpy lines (other side of the list)
    for line in reversed(strip_list):
        if line.strip() or inside:
            inside = True
            context_list.append(line)
    context = "|".join(context_list)
    print("%s:%5d\n|%s" % (
        file_name,
        match[2],
        context
    ))


def display_no_context(f, match, path, file_name, search):
    if _args.raw:
        print("%s\0%5d\0%s" % (
            os.path.abspath(file_name),
            match[2],
            get_line(path, match[2], f)[:-1]
        ))
    else:
        line = get_line(path, match[2], f)[:-1]
        for term in search:
            line = line.replace(term, colored(term, 'red'))
        print("%s:%s:%s" % (
            colored(file_name, 'magenta'),
            colored("%5d" % match[2], 'green'),
            line
        ))


def display_duplicates(db, file_):
    if _args.raw:
        return
    con = db[0]
    with con:
        res = con.execute(_find_duplicates, (file_, file_)).fetchall()
        if res:
            print("duplicates:")
            for file_path in res:
                print("\t%s" % os.path.relpath(file_path[0], _cwd))

# Main functions (also for helpers)


def col_main():
    for line in sys.stdin.readlines():
        split = line.split('\0')
        split[0] = os.path.relpath(split[0], _cwd)
        sys.stdout.write(
            ":".join(split)
        )


def reduplicate(db, last_file_path, to_duplicate):
    con = db[0]
    res = con.execute(
        _find_file, (os.path.relpath(last_file_path),)
    ).fetchall()
    if res:
        file_     = res[0][0]
        with con:
            dups = con.execute(
                _find_duplicates, (file_, file_)
            ).fetchall()
            for dup_file_path in dups:
                for dup in to_duplicate:
                    sys.stdout.write("%s\0%s\0%s" % (
                        os.path.abspath(dup_file_path[0]),
                        dup[0],
                        dup[1]
                    ))


def dup_main():
    finja = find_finja()
    os.chdir(finja)
    db = get_db()
    to_duplicate = []
    last_file_path = "."
    for line in sys.stdin.readlines():
        (
            file_path,
            lineno,
            text
        ) = line.split('\0')
        if last_file_path != file_path:
            if not last_file_path:
                last_file_path = "."
            reduplicate(db, last_file_path, to_duplicate)
            to_duplicate = []
            last_file_path = file_path
        to_duplicate.append((lineno, text))
        sys.stdout.write(line)
    reduplicate(db, last_file_path, to_duplicate)


def main(argv=None):
    """Parse the args and excute"""
    global _args
    global _cache_size
    if not argv:  # pragma: no cover
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description='Index and find stuff',
        add_help=False
    )
    parser.add_argument(
        '--interpunct',
        help='use international seperators',
        action='store_true',
    )
    parser.add_argument(
        '--index',
        '-i',
        help='index the current directory',
        action='store_true',
    )
    parser.add_argument(
        '--update',
        '-u',
        help='update the index before searching',
        action='store_true',
    )
    parser.add_argument(
        '--file-mode',
        '-f',
        help='ignore line-number when matching search strings',
        action='store_true',
    )
    parser.add_argument(
        '--context',
        '-c',
        help='lines of context. Default: 1',
        default=1,
        type=int
    )
    parser.add_argument(
        '--raw',
        '-r',
        help="raw output to parse with tools: \\0 delimiter "
             "(doesn't display duplicates, use finjadup)",
        action='store_true',
    )
    parser.add_argument(
        '--batch',
        '-b',
        help='only read N files and then stop. Default 0 (disabled)',
        default=0,
        type=int
    )
    parser.add_argument(
        '--pignore',
        '-p',
        help='ignore path. Can be repeated',
        nargs='?',
        action='append'
    )
    parser.add_argument(
        '--vacuum',
        '-v',
        help='rebuild the whole database to make it smaller',
        action='store_true',
    )
    parser.add_argument(
        '--less-memory',
        '-l',
        help='use less memory',
        action='store_true',
    )
    parser.add_argument(
        '--clear-inodes',
        help='reset all inodes and modification dates, '
             'will cause finja to rescan everything. Use with -i or -u',
        action='store_true',
    )
    parser.add_argument(
        '--help',
        '-h',
        help='display help',
        action='store_true',
    )
    if six.PY2:
        parser.add_argument(
            'search',
            help='search string',
            type=lambda s: unicode(s, sys.stdin.encoding),  # noqa
            nargs='*',
        )
    else:
        parser.add_argument(
            'search',
            help='search string',
            nargs='*',
        )
    args = parser.parse_args(argv)
    if args.help:
        print(logo)
        parser.print_help()
        sys.exit(1)
    _args = args  # noqa
    if args.less_memory:
        _cache_size = int(_cache_size / 100)  # noqa
    if args.index:
        index()
    if not args.pignore:
        args.pignore = []
    if not args.search:
        args.search = []
    search(
        args.search,
        args.pignore,
        file_mode=args.file_mode,
        update=args.update
    )
    get_db()[0].close()
    if not _index_count and not args.search:
        sys.exit(1)
