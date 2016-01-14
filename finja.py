import argparse
import sys
import sqlite3
import os
import shlex
import stat
import linecache
from binaryornot.check import is_binary

_connection = None

_shlex_settings = {
    '.default': {
    }
}

_ignore_dir = set([
    ".git",
    ".svn"
])


def get_db(create=False):
    global _connection
    if _connection:
        return _connection  # noqa
    exists = os.path.exists("FINJA")
    if not (create or exists):
        raise ValueError("Could not find FINJA")
    _connection = sqlite3.connect("FINJA")  # noqa
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


def apply_shlex_settings(shlex_settings, ext, lex):
    to_apply = [shlex_settings['.default']]
    if ext in shlex_settings:
        to_apply.append(shlex_settings[ext])
    for settings in to_apply:
        for key in settings.keys():
            setattr(lex, key, settings[key])


def index_file(con, file_path, update=False):
    if is_binary(file_path):
        if not update:
            print("%s: is binary, skipping" % (file_path,))
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
                retry = 0
                shlex_settings = dict(_shlex_settings)
                while retry <= 1:
                    try:
                        inserts = []
                        lex = shlex.shlex(f, file_path)
                        ext = file_path.split(os.path.extsep)[-1]
                        apply_shlex_settings(
                            shlex_settings,
                            ext,
                            lex
                        )
                        t = lex.get_token()
                        while t:
                            inserts.append((t, file_path, lex.lineno))
                            t = lex.get_token()
                        break
                    except ValueError:
                        if retry == 0:
                            shlex_settings['.default']['quotes'] = ""
                        else:
                            raise
                    retry += 1
            with con:
                con.execute("""
                    DELETE FROM
                        finja
                    WHERE
                        file=?;
                """, (file_path,))
                try:
                    con.executemany("""
                        INSERT INTO
                            finja(token, file, line)
                        VALUES
                            (?, ?, ?);
                    """, inserts)
                except sqlite3.ProgrammingError:
                    if not update:
                        print("%s: is binary, skipping (late)" % (file_path,))
                    return
                con.execute("""
                    INSERT OR REPLACE INTO
                        file(path, inode)
                    VALUES
                        (?, ?);
                """, (file_path, inode))
            print("%s: indexed" % (file_path,))
        else:
            if not update:
                print("%s: uptodate" % (file_path,))


def index():
    con = get_db(create=True)
    do_index(con)


def do_index(con, update=False):
    for dirpath, _, filenames in os.walk("."):
        if set(dirpath.split(os.sep)).intersection(_ignore_dir):
            continue
        for filename in filenames:
            file_path = os.path.join(
                dirpath,
                filename
            )
            index_file(con, file_path, update)
    con.execute("VACUUM;")


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


def search(
        search,
        file_mode=False,
        update=False,
):
    finja = find_finja()
    os.chdir(finja)
    con = get_db(create=False)
    if update:
        do_index(con, update=True)
    res = []
    with con:
        if file_mode:
            for word in search:
                res.append(set(con.execute("""
                    SELECT DISTINCT
                        file
                    FROM
                        finja
                    WHERE
                        token=?
                """, (word,)).fetchall()))
        else:
            for word in search:
                res.append(set(con.execute("""
                    SELECT DISTINCT
                        file,
                        line
                    FROM
                        finja
                    WHERE
                        token=?
                """, (word,)).fetchall()))
    res_set = res.pop()
    for search_set in res:
        res_set.intersection_update(search_set)
    if file_mode:
        for match in res_set:
            print(match[0])
    else:
        for match in res_set:
            path = match[0]
            if path.startswith("./"):
                path = path[2:]
            print("%s:%5d\t%s" % (
                path,
                match[1],
                linecache.getline(match[0], match[1]).strip()
            ))


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
        search(
            args.search,
            file_mode=args.file_mode,
            update=args.update
        )
