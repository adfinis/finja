=====
Finja
=====

An awesome hack.

Index and find your stuff.

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

Thats it and it works.

Caveat: We do not support languages that don't do spaces nor interpunct. Hey we
are not google!

By dv@winged.ch and ganwell@fangorn.ch
