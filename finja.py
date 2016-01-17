import argparse
import array
import binascii
import codecs
import hashlib
import math
import os
import sqlite3
import stat
import struct
import sys

import six
from binaryornot.check import is_binary

import finja_shlex as shlex

# TODO: Helper for \0 to colons
# TODO: Helper for raw: You can pipe raw output and it will duplicate the raw
# output

_cache_size = 1024 * 1024 / 2

_db_cache = None

_do_second_pass = False

_shlex_settings = {
    '.default': {
        'commenters': ""
    },
    '.override0': {
    },
    '.override1': {
        'whitespace_split': True
    },
    '.override2': {
        'quotes': ""
    },
}

_ignore_dir = set([
    ".git",
    ".svn"
])

_args = None

_index_count = 0

_python_26 = sys.version_info[0] == 2 and sys.version_info[1] < 7

# Conversion functions

if six.PY2:
    def blob(x):
        return sqlite3.Binary(x)

    def binstr(x):
        return str(x)
else:
    def blob(x):
        return x

    def binstr(x):
        return x

if _python_26:
    def path_compress(path, db):
        return path

    def path_decompress(path, db):
        return path
else:
    def path_compress(path, db):
        token_dict = db[1]
        path_arr   = path.split(os.sep)
        path_ids   = array.array('I')
        path_ids.extend([token_dict[x] for x in path_arr])
        if six.PY2:
            return path_ids.tostring()
        else:
            return path_ids.tobytes()

    def path_decompress(path, db):
        string_dict = db[2]
        path_arr    = array.array('I')
        if six.PY2:
            path_arr.fromstring(path)
        else:
            path_arr.frombytes(path)
        path_strs = [string_dict[x] for x in path_arr]
        return os.sep.join(path_strs)


def cleanup(string):
    if len(string) <= 16:
        return string.lower()
    return hashlib.md5(string.lower().encode("UTF-8")).digest()


def md5(fname):
    hash = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hash.update(chunk)
    return hash.digest()


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
        token(string)
    VALUES
        (?);
"""

_token_to_string = """
    SELECT
        string
    FROM
        token
    WHERE
        id = ?;
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
    WHERE
        token_id=?
    {ignore}
"""

_clear_found_files = """
    UPDATE
        file
    SET found = 0
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

_find_file = """
    SELECT
        id,
        inode,
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
        inode = null,
        md5 = null
    WHERE
        md5=?;
"""

_create_new_file_entry = """
    INSERT INTO
        file(path, md5, inode, found)
    VALUES
        (?, ?, ?, 1);
"""

_update_file_entry = """
    UPDATE
        file
    SET
        md5 = ?,
        inode = ?,
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

# Cache classes


class TokenDict(dict):
    def __init__(self, db, *args, **kwargs):
        super(TokenDict, self).__init__(*args, **kwargs)
        self.db = db

    def __missing__(self, key):
        with self.db:
            cur = self.db.cursor()
            res = cur.execute(_string_to_token, (blob(key),)).fetchall()
            if res:
                ret = res[0][0]
            else:
                cur.execute(_insert_token, (blob(key),))
                ret = cur.lastrowid
        self[key] = ret
        return ret


class StringDict(dict):
    def __init__(self, db, *args, **kwargs):
        super(StringDict, self).__init__(*args, **kwargs)
        self.db = db

    def __missing__(self, key):
        with self.db:
            cur = self.db.cursor()
            res = cur.execute(_token_to_string, (key,)).fetchall()
        if not res:
            raise KeyError("Token not found")
        ret = binstr(res[0][0])
        self[key] = ret
        return ret

# DB functions


def get_db(create=False):
    global _db_cache
    if _db_cache:
        return _db_cache  # noqa
    exists = os.path.exists("FINJA")
    if not (create or exists):
        raise ValueError("Could not find FINJA")
    connection = sqlite3.connect("FINJA")  # noqa
    if six.PY2:
        connection.text_factory = str
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
            CREATE TABLE
                token(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    string BLOB
                );
        """)
        connection.execute("""
            CREATE INDEX token_string_idx ON token (string);
        """)
        connection.execute("""
            CREATE TABLE
                file(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path BLOB,
                    md5 BLOB,
                    inode INTEGER,
                    found INTEGER DEFAULT 1
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
    connection.commit()
    _db_cache = (
        connection,
        TokenDict(connection),
        StringDict(connection)
    )
    return _db_cache


def gen_search_query(pignore, file_mode):
    if file_mode:
        projection = """
            f.path,
            f.id
        """
    else:
        projection = """
            f.path,
            f.id,
            i.line
        """
    ignore_list = []
    if _python_26:
        filter_ = "AND f.path NOT LIKE ?"
    else:
        filter_ = "AND hex(f.path) NOT LIKE ?"
    for ignore in pignore:
        ignore_list.append(filter_)
    return _search_query.format(
        projection = projection,
        ignore = "\n".join(ignore_list)
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
    except IOError:
        line = "!! File not found "
    return line


def find_finja():
    cwd = os.path.abspath(".")
    lcwd = cwd.split(os.sep)
    while lcwd:
        cwd = os.sep.join(lcwd)
        check = os.path.join(cwd, "FINJA")
        if os.path.isfile(check):
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
    _do_second_pass = False
    do_index_pass(db, update)
    if _do_second_pass:
        if not update:
            print("Second pass")
        do_index_pass(db, True)


def do_index_pass(db, update=False):
    global _do_second_pass
    con = db[0]
    with con:
        con.execute(_clear_found_files)
    for dirpath, _, filenames in os.walk("."):
        if set(dirpath.split(os.sep)).intersection(_ignore_dir):
            continue
        for filename in filenames:
            file_path = os.path.abspath(os.path.join(
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
    con        = db[0]
    # Bad symlinks etc.
    try:
        stat_res = os.stat(file_path)
    except OSError:
        print("%s: not found, skipping" % (file_path,))
        return
    if not stat.S_ISREG(stat_res[stat.ST_MODE]):
        print("%s: not a plain file, skipping" % (file_path,))
        return
    inode      = stat_res[stat.ST_INO]
    old_inode  = None
    old_md5    = None
    file_      = None
    cfile_path = path_compress(file_path, db)
    with con:
        res = con.execute(_find_file, (cfile_path,)).fetchall()
        if res:
            file_     = res[0][0]
            old_inode = res[0][1]
            old_md5   = res[0][2]
    if old_inode != inode:
        do_index, file_ = check_file(
            con, file_, file_path, cfile_path, inode, old_md5
        )
        if not do_index:
            return
        read_index(db, file_, file_path, update)
    else:
        if not update:
            print("%s: uptodate" % (file_path,))
        with con:
            con.execute(_mark_found, (cfile_path,))


def check_file(con, file_, file_path, cfile_path, inode, old_md5):
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
                _create_new_file_entry, (cfile_path, md5sum, inode)
            )
            file_ = cur.lastrowid
        else:
            con.execute(_update_file_entry, (md5sum, inode, file_))
        if duplicated:
            if not _args.update:
                if md5sum == old_md5:
                    print("%s: not changed, skipping" % (file_path,))
                else:
                    print("%s: duplicated, skipping" % (file_path,))
            return (False, file_)
    return (old_md5 != md5sum, file_)


def read_index(db, file_, file_path, update = False):
    con          = db[0]
    token_dict   = db[1]
    string_dict  = db[2]
    inserts      = set()
    insert_count = 0
    if is_binary(file_path):
        if not update:
            print("%s: is binary, skipping" % (file_path,))
    else:
        if _args.batch > 0:
            _index_count += 1  # noqa
            if _index_count > _args.batch:
                con.close()
                sys.exit(0)
        pass_ = 0
        with open(file_path, "r") as f:
            while pass_ <= 2:
                try:
                    f.seek(0)
                    lex = shlex.shlex(f, file_path)
                    ext = file_path.split(os.path.extsep)[-1]
                    apply_shlex_settings(
                        pass_,
                        ext,
                        lex
                    )
                    t = lex.get_token()
                    while t:
                        if insert_count % 1024 == 0:
                            clear_cache(token_dict, string_dict)
                        insert_count += 1
                        word = cleanup(t)
                        inserts.add((
                            token_dict[word],
                            file_,
                            lex.lineno
                        ))
                        t = lex.get_token()
                except ValueError:
                    if pass_ >= 2:
                        raise
                pass_ += 1
        unique_inserts = len(inserts)
        print("%s: indexed %s/%s (%.3f)" % (
            file_path,
            unique_inserts,
            insert_count,
            float(unique_inserts) / (insert_count + 0.0000000001)
        ))
    with con:
        con.execute(_clear_existing_index, (file_,))
        con.executemany(_insert_index, inserts)


def clear_cache(token_dict, string_dict):
    # clear cache
    if len(token_dict) > _cache_size:
        print("Clear token cache")
        token_dict.clear()
    if len(string_dict) > _cache_size:
        print("Clear string cache")
        string_dict.clear()


def apply_shlex_settings(pass_, ext, lex):
    to_apply = [_shlex_settings['.default']]
    if ext in _shlex_settings:
        to_apply.append(_shlex_settings[ext])
    to_apply.append(
        _shlex_settings['.override%s' % pass_]
    )
    for settings in to_apply:
        for key in settings.keys():
            setattr(lex, key, settings[key])

# Search


def search(
        search,
        pignore,
        file_mode=False,
        update=False,
):
    finja = find_finja()
    os.chdir(finja)
    db         = get_db(create = False)
    con        = db[0]
    token_dict = db[1]
    if update:
        do_index(db, update=True)
    if _args.vacuum:
        con.execute("VACUUM;")
    if not search:
        return
    res = []
    with con:
        bignore = prepare_ignores(pignore, token_dict)
        query = gen_search_query(bignore, file_mode)
        for word in search:
            word = cleanup(word)
            args = [token_dict[word]]
            args.extend(bignore)
            res.append(set(con.execute(query, args).fetchall()))
    res_set = res.pop()
    for search_set in res:
        res_set.intersection_update(search_set)
    if file_mode:
        for match in sorted(
                res_set,
                key=lambda x: x[0],
                reverse=True
        ):
            path = path_decompress(match[0], db)
            print(path)
            if not _args.raw:
                display_duplicates(db, match[1])
    else:
        sort_format_result(db, res_set)


def sort_format_result(db, res_set):
    dirname = None
    old_file = -1
    res_set = [(
        path_decompress(x[0], db),
        x[1],
        x[2],
    ) for x in res_set]
    for match in sorted(
            res_set,
            key=lambda x: (x[0], -x[2]),
            reverse=True
    ):
        file_ = match[1]
        if file_ != old_file and old_file != -1:
            display_duplicates(db, old_file)
        old_file = file_
        path = match[0]
        with codecs.open(path, "r", encoding="UTF-8") as f:
            if not _args.raw:
                new_dirname = os.path.dirname(path)
                if dirname != new_dirname:
                    dirname = new_dirname
                    print("%s:" % dirname)
                file_name = os.path.basename(path)
            else:
                file_name = path
            context = _args.context
            if context == 1 or _args.raw:
                display_no_context(f, match, path, file_name)
            else:
                display_context(f, context, match, path, file_name)
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


def display_no_context(f, match, path, file_name):
    if _args.raw:
        print("%s\0%5d\0%s" % (
            file_name,
            match[2],
            get_line(path, match[2], f)[:-1]
        ))
    else:
        print("%s:%5d:%s" % (
            file_name,
            match[2],
            get_line(path, match[2], f)[:-1]
        ))


def prepare_ignores(pignore, token_dict):
    if _python_26:
        bignore = []
        for ignore in pignore:
            bignore.append("%{0}%".format(ignore))
    else:
        bignore = []
        for ignore in pignore:
            tignore = token_dict[ignore]
            bignore.append(
                "%{0}%".format(
                    binascii.b2a_hex(struct.pack('I', tignore)).upper()
                )
            )
    return bignore


def display_duplicates(db, file_):
    if _args.raw:
        return
    con = db[0]
    with con:
        res = con.execute(_find_duplicates, (file_, file_)).fetchall()
        if res:
            print("duplicates:")
            for cfile_path in res:
                print("\t%s" % path_decompress(cfile_path[0], db))

# Main functions (also for helpers)


def col_main():
    for line in sys.stdin.readlines():
        sys.stdout.write(
            ":".join(line.split('\0'))
        )


def main(argv=None):
    """Parse the args and excute"""
    global _args
    if not argv:  # pragma: no cover
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description='Index and find stuff')
    parser.add_argument(
        '--index',
        '-i',
        help='Index the current directory',
        action='store_true',
    )
    parser.add_argument(
        '--update',
        '-u',
        help='Update the index before searching',
        action='store_true',
    )
    parser.add_argument(
        '--file-mode',
        '-f',
        help='Ignore line-number when matching search strings',
        action='store_true',
    )
    parser.add_argument(
        '--context',
        '-c',
        help='Lines of context. Default: 1',
        default=1,
        type=int
    )
    parser.add_argument(
        '--raw',
        '-r',
        help="Raw output to parse with tools: \\0 delimiter "
             "(doesn't display duplicates, use finjadup)",
        action='store_true',
    )
    parser.add_argument(
        '--batch',
        '-b',
        help='Only read N files and then stop. Default 0 (disabled)',
        default=0,
        type=int
    )
    parser.add_argument(
        '--pignore',
        '-p',
        help='Ignore path that contain one of the elements. Can be repeated',
        nargs='?',
        action='append'
    )
    parser.add_argument(
        '--vacuum',
        '-v',
        help='Rebuild the hole database to make it smaller',
        action='store_true',
    )
    parser.add_argument(
        'search',
        help='search string',
        type=str,
        nargs='*',
    )
    args = parser.parse_args(argv)
    _args = args  # noqa
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
    if not _index_count and not args.search:
        get_db()[0].close()
        sys.exit(1)
