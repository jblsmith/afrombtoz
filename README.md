# afrombtoz
Variations of Echo Nest Remix API function AfromB

### AfromB
[Echo Nest Remix](http://echonest.github.io/remix/python.html) is a great tool for remixing music programmatically. I love the function [afromb.py](https://github.com/echonest/remix/blob/master/examples/afromb/afromb.py), which takes an input song B and uses fragments of it to reconstruct, as best as possible, input song A. But I have always wanted a more flexible tool. My wishlist includes:

* reconstruction from multiple songs
* reconstruction at multiple timescales
* reconstruction with constraints, such as "use a different segment B for each segment in A", or "use only 20 unique clips from B"

Initial commit: afrombc.py expands afromb.py to accept two inputes.