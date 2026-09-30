---
title: Semantic Image Search Demo
emoji: 🔍
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Search 5,000 COCO photos by describing them
---

# Semantic Image Search: demo API

The search service behind the public demo. It finds photos from a text description using OpenAI's CLIP model and a FAISS index over the 5,000 images of COCO val2017.

- `POST /search` with `{"text": "a dog catching a frisbee", "k": 12}`
- `GET /browse?offset=0&limit=24` lists the photos
- `GET /images/<file>` serves the thumbnails

Source code, design notes and benchmark: https://github.com/HypothesisTester/semantic-image-search

COCO images are from Flickr under their original licences; captions are CC BY 4.0 (cocodataset.org).
