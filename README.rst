=====
Finja
=====

An awesome hack. Your friendly finding ninja.

Usage
=====

Index and find your stuff.

Index the current directory.

.. code:: bash

   finja --index

Find huhu in the index.

.. code:: bash

   finja huhu

Update outdated files and find huhu in the index.

.. code:: bash

   finja -u huhu

Also works from a subdirectory.

.. code:: bash

   finja --index
   cd subdir
   finja huhu

Tip: If you are sure that your system survives till everything is indexed use
eatmydata.

.. code:: bash

   eatmydata finja -i

Raw mode is meant for machines, but you can replace the \\0 with colons.

.. code:: bash

   finja -r huhu | finjacol

Get reduplicated raw human readable output.

.. code:: bash

   finja -r stuff | finjadup | finjacol

Get reduplicated raw output.

.. code:: bash

   finja -r stuff | finjadup

Index git files only.

.. code:: bash

   git ls-tree -r --name-only master > FINJA.lst
   finja -i

Filter unwanted output by path.

.. code:: bash

   finja -p spamfolder gold

Cleanup free (unused) tokens and rebuild the database.

.. code:: bash

   finja --vacuum

If there are some badly formatted files that seriously cramp your style.

.. code:: bash

   finja readlines for | cut -c -`tput cols`

Index stuff in read-only directories.

.. code:: bash

   mkdir sysinclude
   cd sysinclude
   find /usr/include/ -xdev > FINJA.lst
   eatmydata finja -i
   finja AF_INET6

Caveat: We do not support languages that don't do spaces nor interpunct. Hey we
are not google!

Using in vim/neovim:

* Install https://github.com/mileszs/ack.vim

* Create a finjaack script

.. code:: bash

   #!/bin/sh

   finja -r "$@" | finjagrep

* Set finjaack as ackprg

.. code:: vim

   let g:ackprg = 'finjack'


Installation
============

.. code:: bash

   pip install -U finja


Why?
====

Unlike many of the great alternatives to finja, finja is generic. It doesn't
know what it is indexing. Finja achieves good indexing quality by doing multiple
passes with different tokenization methods and splitting character lists.
Therefore it is slower and has a bigger index than non-generic indexers, but it
just indexes your stuff and won't miss any files it doesn't know about.

Finja is doing something wrong, can I customize the settings?
=============================================================

We would like to keep settings to a minimum. At the moment there is only
international interpunct, that can be switched on. Please open an issue on Github
and describe your problem, we will try to find a generic solution. If we don't
find such a solution we might add a setting.

By ganwell@fangorn.ch and David Vogt, Stefan Heinemann, Pablo Vergés

Changes
=======

1.1.1

* Ignore empty lines in finjacol/finjagrep

1.1.0

* Add finjagrep which emulates grep output for usage with ack.vim

1.0.11

* Add workaround for VACUUM bug in python

* Multiple version due bugs in packaging (rereleases)

1.0.8

* Conditionally add the argparse dependancy on python 2.6 (@ganwell)

1.0.7

* Case-insensitive highlighting (@ganwell)

1.0.6

* Add argparse as requires for CentOS6 (@Pablo Verges)
* Add search term coloring (@schtibe)
* Add finja logo to help (@ganwell)
