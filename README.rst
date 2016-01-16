=====
Finja
=====

Index and find your stuff:

.. code:: bash

   finja --index

Indexes the current directly.

.. code:: bash

   finja huhu

Find huhu in the index.

.. code:: bash

   finja --index
   cd submdir
   find huhu

Thats it and it works.

Tipp: If you are sure that your system survives till everything is indexed use:

.. code:: bash

   eatmydata finja -i

if it is a extremly large project you can index incrementally

.. code:: bash

   rm FINJA; finja -i -b 1; while eatmydata finja -u -b 10000 a; do echo inc; done;


By dv@winged.ch and ganwell@fangorn.ch
