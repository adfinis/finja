import argparse
import sys
import sqlite3
import os
import shlex
import stat
from binaryornot.check import is_binary

_connection = None

_shlex_settings = {
    '.default': {
    }
}


def get_db(create=False, path="FINJA"):
    global _connection
    if _connection:
        return _connection  # noqa
    exists = os.path.exists(path)
    if not (create or exists):
        raise ValueError("Could not find FINJA")
    _connection = sqlite3.connect(path)  # noqa
    if not exists:
        _connection.execute("""
            CREATE TABLE
                finja(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token BLOB,
                    file TEXT,
                    line INTEGER
                );
        """)
        _connection.execute("""
            CREATE TABLE
                file(
                    path TEXT PRIMARY KEY,
                    inode INTEGER
                );
        """)
        _connection.execute("""
            CREATE INDEX finja_token_idx ON finja (token);
        """)
        _connection.execute("""
            CREATE INDEX finja_file_idx ON finja (file);
        """)
    return _connection


def apply_shlex_settings(ext, lex):
    to_apply = [_shlex_settings['.default']]
    if ext in _shlex_settings:
        to_apply.append(_shlex_settings[ext])
    for settings in to_apply:
        for key in settings.keys():
            setattr(lex, key, settings[key])


def index_file(con, file_path):
    sys.stdout.write("%s%s" % (file_path, ": "))
    if is_binary(file_path):
        print("is binary, skipping")
        return
    else:
        mode = os.stat(file_path)
        inode = mode[stat.ST_INO]
        old_inode = None
        with con:
            res = con.execute("""
                SELECT
                    inode
                FROM
                    file
                WHERE
                    path=?;
            """, (file_path,)).fetchall()
            if res:
                old_inode = res[0][0]
        if old_inode != inode:
            with open(file_path, "r") as f:
                inserts = []
                lex = shlex.shlex(f, file_path)
                ext = file_path.split(os.path.extsep)[-1]
                apply_shlex_settings(ext, lex)
                t = lex.get_token()
                while t:
                    inserts.append((t, file_path, lex.lineno))
                    t = lex.get_token()
            with con:
                con.execute("""
                    DELETE FROM
                        finja
                    WHERE
                        file=?;
                """, (file_path,))
                con.executemany("""
                    INSERT INTO
                        finja(token, file, line)
                    VALUES
                        (?, ?, ?);
                """, inserts)
                con.execute("""
                    INSERT OR REPLACE INTO
                        file(path, inode)
                    VALUES
                        (?, ?);
                """, (file_path, inode))
        print("ok")


def index():
    con = get_db(create=True)
    for dirpath, _, filenames in os.walk("."):
        for filename in filenames:
            file_path = os.path.join(
                dirpath,
                filename
            )
            index_file(con, file_path)
    con.execute("VACUUM;")


def find_finja():
    cwd = os.path.abspath(".")
    lcwd = cwd.split(os.sep)
    while lcwd:
        cwd = os.sep.join(lcwd)
        check = os.path.join(cwd, "FINJA")
        if os.path.exists(check):
            return check
        lcwd.pop()
    raise ValueError("Could not find FINJA")


def search(search):
    finja = find_finja()
    con = get_db(create=False, path=finja)


def main(argv=None):
    """Parse the args and excute"""
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
        'search',
        help='search string',
        type=str,
        nargs='*',
        default='all'
    )
    args = parser.parse_args(argv)
    if args.index:
        index()
    if args.search:
        search(args.search)
