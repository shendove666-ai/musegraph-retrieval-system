# Mao Wen · Technical portfolio

I studied piano performance at Nanjing University of the Arts. My portfolio follows my move from working with musical sources to representing those sources in code and testing what the resulting systems can tell me.

## Project 4 · MuseGraph

I developed MuseGraph to locate a remembered quotation, name, or argument in historical music writing and let the reader verify the match. The application ships with 2,286 passages from five Project Gutenberg books. I use TF-IDF for term matches, Winnowing for repeated wording, and a pretrained Sentence-BERT encoder for semantic similarity. The result page links back to the source edition and shows evidence that the reader can compare with the query. [Run MuseGraph](README.md)

The part I would ask a reviewer to examine first is how a five-word fingerprint leads back to an exact span in a passage. The code selects local minima with a deque, checks normalized word tuples before reporting a match, and retains the original character offsets. In the Leoni walkthrough, the semantic ranking favors a nearby passage about the same singer. The fingerprint identifies the passage that contains the wording. [Fingerprint code](musegraph/algorithms/fingerprint.py) · [Walkthrough](DEMO.md) · [Error analysis](ERROR_ANALYSIS.md)

## Connections across the portfolio

In `digital-music-network-mining`, I use a weighted graph to represent repeated recording credits from MusicBrainz. In `pytorch-cnn-image-classification`, I compare CNN architectures and data augmentation on CIFAR-10 over multiple random seeds. In MuseGraph I can open a single ranked result and trace its score to terms, shared wording, and the text window selected by the encoder. I compare the ranking methods on a fixed set of graded queries and use individual misses to examine their behavior. [Benchmark results](RESULTS.md)
