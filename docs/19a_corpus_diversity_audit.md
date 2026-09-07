# Complete-page corpus diversity audit v0.2

Read-only measurements of the registered corpus. eManuSkript masks are model-derived layout evidence, not manual annotations.

85 pages; 19 page-bearing manuscripts; 20 assigned manuscripts (including zero-page assignments).

| Split | Pages | Page-bearing manuscripts | Assigned manuscripts |
| --- | ---: | ---: | ---: |
| train | 59 | 13 | 14 |
| validation | 13 | 3 | 3 |
| test | 13 | 3 | 3 |

## Image characteristics

```json
{
  "width_px": {
    "count": 85,
    "mean": 2000,
    "median": 2000,
    "minimum": 2000,
    "maximum": 2000,
    "population_standard_deviation": 0.0
  },
  "height_px": {
    "count": 85,
    "mean": 2862.0352941176,
    "median": 2812,
    "minimum": 2471,
    "maximum": 3626,
    "population_standard_deviation": 267.1543042583
  },
  "aspect_ratio": {
    "count": 85,
    "mean": 0.7044254244,
    "median": 0.7112375533428165,
    "minimum": 0.5515719801434087,
    "maximum": 0.8093889113719142,
    "population_standard_deviation": 0.0606781761
  },
  "file_size_bytes": {
    "count": 85,
    "mean": 1383193.2470588235,
    "median": 1362440,
    "minimum": 847277,
    "maximum": 2188241,
    "population_standard_deviation": 240368.2606995263
  },
  "database_vs_acquired_dimensions_differ_count": 85,
  "dimension_note": "Image statistics use acquired rasters. Existing DB dimensions preserve advertised IIIF dimensions and are not rewritten.",
  "source_checksum_recorded_count": 85,
  "source_checksum_verified_count": 74
}
```

## Layout evidence

85 declared runs; 4230 regions; 4230 verified source-sized masks.

Regions per page: {'count': 85, 'mean': 49.7647058824, 'median': 42, 'minimum': 0, 'maximum': 125, 'population_standard_deviation': 31.77296189}

Union mask coverage (overlapping instances counted once): {'count': 85, 'mean': 0.3160131144, 'median': 0.31755176294073517, 'minimum': 0.0, 'maximum': 0.9159793741109531, 'population_standard_deviation': 0.1658264479}

Zero-region pages: 6538cbcb609973816c5a, 6c1543ed764a6265f96a, 95c524bbf6593575149b, a57947d883c928bdeae4. Low-confidence pages (mean < 0.4): 5e6ff8c7c454a2c27b94.

| Model class | Train regions | Validation regions | Test regions |
| --- | ---: | ---: | ---: |
| Border | 1 | 0 | 0 |
| Embellished | 3 | 1 | 6 |
| Gloss | 29 | 1 | 3 |
| Illustrations | 6 | 0 | 0 |
| Main script black | 3089 | 106 | 694 |
| Main script coloured | 5 | 6 | 0 |
| Music | 45 | 37 | 10 |
| Page Number | 16 | 2 | 1 |
| Plain initial - Black | 43 | 1 | 2 |
| Plain initial - Highlighted | 5 | 45 | 0 |
| Plain initial- coloured | 35 | 2 | 0 |
| Running header | 4 | 0 | 1 |
| Table | 1 | 0 | 0 |
| Variant script coloured | 21 | 1 | 8 |

## Quantitative gaps

Largest manuscript contributes 5.88% of pages. Pages per manuscript: `{'bbb-AA0091': 5, 'bc-b-0067': 5, 'bc-b-0103': 5, 'bcj-A2437': 5, 'bcul-Ms0403': 5, 'bke-0056': 5, 'cea-FaZellweger-90A-01-2': 0, 'csg-0059': 3, 'csg-0073': 5, 'csg-0300': 3, 'csg-0314': 3, 'csg-0916': 5, 'fmb-cb-0056': 5, 'fmb-cb-0902': 5, 'kba-Wett0004': 3, 'kba-WettF0001': 5, 'sbs-gen0020': 5, 'ubb-A-II-0013': 5, 'ubb-F-I-0021': 5, 'ubb-F-IX-0068': 3}`.

Provider concentration: `{'www.e-codices.unifr.ch': 85}`. Repository distribution: `{'Aarau, Aargauer Kantonsbibliothek': 8, 'Basel, Universitätsbibliothek': 13, 'Bern, Burgerbibliothek': 5, 'Cologny, Fondation Martin Bodmer': 10, 'Engelberg, Stiftsbibliothek': 5, 'Lausanne, Bibliothèque cantonale et universitaire - Lausanne': 5, 'Porrentruy, Bibliothèque cantonale jurassienne': 5, 'Schaffhausen, Stadtbibliothek': 5, 'St. Gallen, Stiftsbibliothek': 19, 'Zürich, Braginsky Collection': 10}`.

Classes absent in validation: Border, Illustrations, Running header, Table. Classes absent in test: Border, Illustrations, Main script coloured, Plain initial - Highlighted, Plain initial- coloured, Table.

Script metadata is missing for 20 assigned manuscripts; no script-diversity claim is supported. Outlier concentration: `{'fmb-cb-0902': 4, 'ubb-F-IX-0068': 1}`.

Missing/invalid artifact pages: `[{'page_id': '219352470825ee97ee12', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/sbs-gen0020/0113_sbs-gen0020_0055v.jpg']}, {'page_id': '460bd866fb80b903a9fb', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/bcj-A2437/0168_bcj-A2437_0161.jpg']}, {'page_id': '4cf06d901eb0b1a54363', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/bke-0056/0147_bke-0056_072v.jpg']}, {'page_id': '5db204561d9b7d37a1c3', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/ubb-F-I-0021/0154_ubb-F-I-0021_0075r.jpg']}, {'page_id': '62eacd9afde4dc6a4efe', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/sbs-gen0020/0067_sbs-gen0020_0032v.jpg']}, {'page_id': '78a173ee8c7c7e00814d', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/bke-0056/0186_bke-0056_092r.jpg']}, {'page_id': '83ac253c56dd15ea0ee6', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/bc-b-0067/0082_bc-b-0067_042v.jpg']}, {'page_id': '95761b8d0ee5433b8c6f', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/ubb-A-II-0013/0193_ubb-A-II-0013_0095v.jpg']}, {'page_id': 'a4f4e588f0055430b22f', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_validation_v0_1/kba-Wett0004/0022_kba-Wett0004_009v.jpg']}, {'page_id': 'c4be43f3de7496413f1b', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/ubb-A-II-0013/0202_ubb-A-II-0013_0100r.jpg']}, {'page_id': 'd2fdc913de8f7f2a98fe', 'reasons': ['unavailable_local_artifact_icloud_dataless:data/raw/ecodices_training_source_expansion_batch_01_v0_1/bbb-AA0091/0066_bbb-AA0091_031r.jpg']}]`.

Inspect the machine-readable audit for per-page dimensions, density, confidence and checksums. Image ratios describe acquired rasters, not physical codex dimensions. Zero detections do not establish zero manuscript content. Test inspection here is a read-only structural audit; test pages remain excluded from v0.2 experiments.
