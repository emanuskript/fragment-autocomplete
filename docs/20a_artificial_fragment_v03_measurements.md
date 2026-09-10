# Structured synthetic damage measurements v0.3

Known source pixels are ground truth; eManuSkript regions are model evidence. Survival is pixel retention, not semantic recoverability or historical likelihood.

Reuse v0.2 categories: 0 fully removed; (0,.05] mostly destroyed; (.05,.95) partial; [.95,1] almost complete. Mostly surviving is an explicit alias of almost complete, not a fifth category; do not sum both rates.

All v0.3: 156 tasks / 2424 region observations. Matched controls use 11 common pages.

## All v0.3 pages

| Family:severity | Tasks | Regions | Page loss | Severity error | Mean region survival | Median | Fully removed rate | Mostly removed | Partial | Almost complete / mostly surviving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| connected_piece_loss:0.30 | 13 | 202 | 0.30000000 | 0.00000000 | 0.42386266 | 0.39667455 | 0.14356436 | 0.02970297 | 0.71782178 | 0.10891089 |
| connected_piece_loss:0.60 | 13 | 202 | 0.60000000 | 0.00000000 | 0.15834810 | 0.02940087 | 0.44554455 | 0.06930693 | 0.44059406 | 0.04455446 |
| corner_loss:0.30 | 13 | 202 | 0.30000000 | 0.00000000 | 0.72014473 | 1.00000000 | 0.06435644 | 0.00495050 | 0.40594059 | 0.52475248 |
| corner_loss:0.60 | 13 | 202 | 0.60000000 | 0.00000000 | 0.23823717 | 0.13856503 | 0.24257426 | 0.01485149 | 0.65841584 | 0.08415842 |
| edge_loss:0.30 | 13 | 202 | 0.30000000 | 0.00000000 | 0.81971008 | 0.90022238 | 0.04455446 | 0.00000000 | 0.46039604 | 0.49504950 |
| edge_loss:0.60 | 13 | 202 | 0.60000000 | 0.00000000 | 0.33219277 | 0.27421314 | 0.34653465 | 0.02475248 | 0.50495050 | 0.12376238 |
| edge_tear:0.30 | 13 | 202 | 0.30000000 | 0.00000000 | 0.77674355 | 0.91056769 | 0.06435644 | 0.00495050 | 0.48514851 | 0.44554455 |
| edge_tear:0.60 | 13 | 202 | 0.60000000 | 0.00000000 | 0.26215868 | 0.04121153 | 0.43069307 | 0.07425743 | 0.36138614 | 0.13366337 |
| internal_hole:0.30 | 13 | 202 | 0.30000000 | 0.00000000 | 0.33535903 | 0.23176968 | 0.20297030 | 0.00990099 | 0.66831683 | 0.11881188 |
| internal_hole:0.60 | 13 | 202 | 0.60000000 | 0.00000000 | 0.07596630 | 0.00000000 | 0.50990099 | 0.17821782 | 0.29702970 | 0.01485149 |
| strip_loss:0.30 | 13 | 202 | 0.30000000 | 0.00000000 | 0.74046115 | 1.00000000 | 0.15841584 | 0.00495050 | 0.26237624 | 0.57425743 |
| strip_loss:0.60 | 13 | 202 | 0.60000000 | 0.00000000 | 0.34984158 | 0.19145772 | 0.39603960 | 0.00990099 | 0.40594059 | 0.18811881 |

## artificial_fragment_experiment_v0_3

| Family:severity | Tasks | Regions | Page loss | Severity error | Mean region survival | Median | Fully removed rate | Mostly removed | Partial | Almost complete / mostly surviving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| connected_piece_loss:0.30 | 11 | 151 | 0.30000000 | 0.00000000 | 0.45611468 | 0.40812206 | 0.11920530 | 0.01324503 | 0.74172185 | 0.12582781 |
| connected_piece_loss:0.60 | 11 | 151 | 0.60000000 | 0.00000000 | 0.16881179 | 0.07010650 | 0.38410596 | 0.08609272 | 0.48344371 | 0.04635762 |
| corner_loss:0.30 | 11 | 151 | 0.30000000 | 0.00000000 | 0.72632420 | 1.00000000 | 0.05960265 | 0.00662252 | 0.40397351 | 0.52980132 |
| corner_loss:0.60 | 11 | 151 | 0.60000000 | 0.00000000 | 0.23870421 | 0.12128998 | 0.23178808 | 0.01986755 | 0.64900662 | 0.09933775 |
| edge_loss:0.30 | 11 | 151 | 0.30000000 | 0.00000000 | 0.82008604 | 0.88300915 | 0.04635762 | 0.00000000 | 0.48344371 | 0.47019868 |
| edge_loss:0.60 | 11 | 151 | 0.60000000 | 0.00000000 | 0.28609975 | 0.08972227 | 0.39072848 | 0.03311258 | 0.43708609 | 0.13907285 |
| edge_tear:0.30 | 11 | 151 | 0.30000000 | 0.00000000 | 0.79333142 | 0.91939583 | 0.06622517 | 0.00000000 | 0.49006623 | 0.44370861 |
| edge_tear:0.60 | 11 | 151 | 0.60000000 | 0.00000000 | 0.25073024 | 0.01244493 | 0.45695364 | 0.07947020 | 0.34437086 | 0.11920530 |
| internal_hole:0.30 | 11 | 151 | 0.30000000 | 0.00000000 | 0.35847641 | 0.24492351 | 0.18543046 | 0.00000000 | 0.68211921 | 0.13245033 |
| internal_hole:0.60 | 11 | 151 | 0.60000000 | 0.00000000 | 0.07823705 | 0.00000000 | 0.50331126 | 0.15894040 | 0.33112583 | 0.00662252 |
| strip_loss:0.30 | 11 | 151 | 0.30000000 | 0.00000000 | 0.78648922 | 1.00000000 | 0.13245033 | 0.00662252 | 0.19867550 | 0.66225166 |
| strip_loss:0.60 | 11 | 151 | 0.60000000 | 0.00000000 | 0.42022267 | 0.42199659 | 0.43708609 | 0.00000000 | 0.31125828 | 0.25165563 |

## artificial_fragment_experiment_v0_2

| Family:severity | Tasks | Regions | Page loss | Severity error | Mean region survival | Median | Fully removed rate | Mostly removed | Partial | Almost complete / mostly surviving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| irregular:0.30 | 11 | 151 | 0.29996516 | 0.00010748 | 0.94376613 | 1.00000000 | 0.01324503 | 0.00000000 | 0.22516556 | 0.76158940 |
| irregular:0.60 | 11 | 151 | 0.60001855 | 0.00004535 | 0.63887768 | 0.77409315 | 0.19867550 | 0.01986755 | 0.58940397 | 0.19205298 |
| rectangular:0.30 | 11 | 151 | 0.29989462 | 0.00010538 | 0.93867427 | 1.00000000 | 0.01986755 | 0.00000000 | 0.19867550 | 0.78145695 |
| rectangular:0.60 | 11 | 151 | 0.59987949 | 0.00012051 | 0.70436523 | 0.87644705 | 0.13907285 | 0.00000000 | 0.54304636 | 0.31788079 |

Descriptive matched-page comparison at nominal severity. v0.2 and v0.3 orientation/shape assignments differ. Repeated region observations are not independent samples; no historical likelihood or causal content-recovery claim.

JSON includes count/mean/median/population SD/min/max by experiment, family, severity, manuscript, page and class, plus each family/severity/class combination.
