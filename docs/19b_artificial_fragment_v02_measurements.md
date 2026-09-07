# Artificial Fragment Experiment v0.2 measurements

44 validation tasks; 604 mask-region survival measurements; 16 tasks with no detected regions.

Survival is observed pixel retention under a controlled synthetic transformation, not recoverability. Regions are model outputs and may omit or mislabel visible content.

Categories: fully removed = 0; mostly destroyed = (0, 0.05]; partial = (0.05, 0.95); almost complete = [0.95, 1].

## By mask family

| Group | Tasks | Regions | Page mean survival | Region mean | Region median | Min | Max | Population SD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| irregular | 22 | 302 | 0.550008 | 0.791322 | 0.939837 | 0.000000 | 1.000000 | 0.324415 |
| rectangular | 22 | 302 | 0.550113 | 0.821520 | 0.981503 | 0.000000 | 1.000000 | 0.297022 |

## By requested severity

| Group | Tasks | Regions | Page mean survival | Region mean | Region median | Min | Max | Population SD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.3 | 22 | 302 | 0.700070 | 0.941220 | 1.000000 | 0.000000 | 1.000000 | 0.166894 |
| 0.6 | 22 | 302 | 0.400051 | 0.671621 | 0.798116 | 0.000000 | 1.000000 | 0.360178 |

## By manuscript

| Group | Tasks | Regions | Page mean survival | Region mean | Region median | Min | Max | Population SD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fmb-cb-0902 | 20 | 20 | 0.550047 | 0.780744 | 0.816486 | 0.149389 | 1.000000 | 0.226236 |
| sbs-gen0020 | 12 | 328 | 0.550098 | 0.843689 | 0.997246 | 0.000000 | 1.000000 | 0.284626 |
| ubb-F-IX-0068 | 12 | 256 | 0.550045 | 0.760677 | 0.917754 | 0.000000 | 1.000000 | 0.342125 |

## By page

| Group | Tasks | Regions | Page mean survival | Region mean | Region median | Min | Max | Population SD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 425d05fd9a5871117c02 | 4 | 144 | 0.550038 | 0.718645 | 0.836027 | 0.000000 | 1.000000 | 0.330414 |
| 44b0f45256bf210d6896 | 4 | 128 | 0.550075 | 0.858051 | 1.000000 | 0.000000 | 1.000000 | 0.301682 |
| 5e6ff8c7c454a2c27b94 | 4 | 8 | 0.550074 | 0.743292 | 0.880263 | 0.149389 | 1.000000 | 0.303647 |
| 6538cbcb609973816c5a | 4 | 0 | 0.550090 | undefined | undefined | undefined | undefined | undefined |
| 6c1543ed764a6265f96a | 4 | 0 | 0.550053 | undefined | undefined | undefined | undefined | undefined |
| 86236cd76a738eebc657 | 4 | 112 | 0.550021 | 0.814719 | 1.000000 | 0.000000 | 1.000000 | 0.349263 |
| 95a6f2c3d5cf0d195a1b | 4 | 120 | 0.550035 | 0.825913 | 1.000000 | 0.000000 | 1.000000 | 0.283662 |
| 95c524bbf6593575149b | 4 | 0 | 0.549988 | undefined | undefined | undefined | undefined | undefined |
| a57947d883c928bdeae4 | 4 | 0 | 0.550076 | undefined | undefined | undefined | undefined | undefined |
| d704f482fd5fd52f0df9 | 4 | 80 | 0.550184 | 0.847373 | 0.915414 | 0.000000 | 1.000000 | 0.254984 |
| d861c556a5079b0f562b | 4 | 12 | 0.550032 | 0.805713 | 0.816486 | 0.569986 | 1.000000 | 0.149260 |

## By layout class

| Group | Tasks | Regions | Page mean survival | Region mean | Region median | Min | Max | Population SD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Embellished | 4 | 4 | 0.550074 | 0.642105 | 0.709515 | 0.149389 | 1.000000 | 0.370375 |
| Gloss | 4 | 4 | 0.550021 | 0.028788 | 0.000000 | 0.000000 | 0.115153 | 0.049863 |
| Main script black | 28 | 292 | 0.550066 | 0.818090 | 0.929316 | 0.000000 | 1.000000 | 0.271726 |
| Main script coloured | 4 | 16 | 0.550038 | 0.625099 | 0.818982 | 0.000000 | 1.000000 | 0.416469 |
| Music | 12 | 148 | 0.550081 | 0.800697 | 0.914291 | 0.000000 | 1.000000 | 0.289571 |
| Page Number | 4 | 4 | 0.550075 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| Plain initial - Black | 4 | 4 | 0.550038 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| Plain initial - Highlighted | 16 | 124 | 0.550042 | 0.884759 | 1.000000 | 0.000000 | 1.000000 | 0.310392 |
| Plain initial- coloured | 4 | 4 | 0.550035 | 0.303972 | 0.207067 | 0.000000 | 0.801756 | 0.333438 |
| Variant script coloured | 4 | 4 | 0.550021 | 0.520426 | 0.540852 | 0.000000 | 1.000000 | 0.480443 |

Population SD; null for fewer than two observations. Region statistics weight instances equally; class task counts count only tasks containing that class. Repeated tasks are controlled transformations, not independent manuscript observations.

Exact category frequencies and page-level distribution statistics are in the machine-readable measurements artifact.
