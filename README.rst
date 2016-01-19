=====
Finja
=====

An awesome hack.

Index and find your stuff.

.. code:: bash

   pip install -U git+https://github.com/adfinis-sygroup/finja.git

Indexes the current directory.

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
   cd submdir
   find huhu

Tipp: If you are sure that your system survives till everything is indexed use.

.. code:: bash

   eatmydata finja -i

Raw mode is meant for machines, but you can replace the \\0 with colons.

.. code:: bash

   finja -r huhu | finjacol

Index git files only.

.. code:: bash

   git ls-tree -r --name-only master > FINJA.lst
   finja -i

Filter unwanted output by path element (directory or file). Be aware:
directories and files are tokens too: no partial matches.

.. code:: bash

   finja -p spamfolder gold

Thats it and it works.

Caveat: We do not support languages that don't do spaces nor interpunct. Hey we
are not google!

By dv@winged.ch and ganwell@fangorn.ch
